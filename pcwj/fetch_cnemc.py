import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def _safe_filename(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    base = parsed.path.strip("/").replace("/", "_") or "root"
    if parsed.query:
        q_hash = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:10]
        base = f"{base}_{q_hash}"
    ext = ".json" if "json" in content_type.lower() else ".txt"
    return f"{base}{ext}"


def _should_capture(url: str, host_filter: str | None) -> bool:
    if not host_filter:
        return True
    return urlparse(url).netloc == host_filter


def capture_site_data(
    url: str,
    out_dir: Path,
    host_filter: str | None,
    wait_ms: int,
    headless: bool,
    timeout_ms: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    responses_dir = out_dir / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    endpoints = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-http2"],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_navigation_timeout(timeout_ms)
        page.set_default_timeout(timeout_ms)

        def handle_response(response):
            req = response.request
            url = response.url
            if not _should_capture(url, host_filter):
                return
            if response.status != 200:
                return
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type.lower() and "text" not in content_type.lower():
                return

            try:
                body = response.text()
            except Exception:
                return

            filename = _safe_filename(url, content_type)
            target = responses_dir / filename
            if "json" in content_type.lower():
                try:
                    data = json.loads(body)
                    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    target.write_text(body, encoding="utf-8")
            else:
                target.write_text(body, encoding="utf-8")

            endpoints[url] = {
                "method": req.method,
                "status": response.status,
                "content_type": content_type,
                "saved_as": str(target.relative_to(out_dir)),
            }

        page.on("response", handle_response)
        last_error = None
        for wait_until in ("domcontentloaded", "load"):
            try:
                page.goto(url, wait_until=wait_until)
                page.wait_for_timeout(wait_ms)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error

        browser.close()

    (out_dir / "endpoints.json").write_text(
        json.dumps(endpoints, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "endpoints.txt").write_text(
        "\n".join(sorted(endpoints.keys())), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture data responses from szzdjc.cnemc.cn site using Playwright."
    )
    parser.add_argument(
        "--url",
        default="https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/Main.html",
    )
    parser.add_argument("--out", default="cnemc_data", help="Output directory")
    parser.add_argument(
        "--host",
        default="szzdjc.cnemc.cn:8070",
        help="Only capture responses from this host (empty to capture all).",
    )
    parser.add_argument("--wait-ms", type=int, default=15000, help="Extra wait after load")
    parser.add_argument("--timeout-ms", type=int, default=60000, help="Navigation timeout")
    parser.add_argument("--headed", action="store_true", help="Run with browser UI")
    args = parser.parse_args()

    host_filter = args.host or None
    capture_site_data(
        args.url,
        Path(args.out),
        host_filter,
        args.wait_ms,
        not args.headed,
        args.timeout_ms,
    )


if __name__ == "__main__":
    main()
