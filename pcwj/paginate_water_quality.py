import argparse
import csv
import html
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlencode

from playwright.sync_api import sync_playwright


PAGE_KEYS = [
    "page",
    "pageIndex",
    "pageindex",
    "pageNo",
    "pageNum",
    "current",
    "PageIndex",
    "Page",
]
SIZE_KEYS = [
    "rows",
    "row",
    "pageSize",
    "pagesize",
    "page_size",
    "size",
    "limit",
    "PageSize",
]


def strip_html(text: str) -> str:
    text = text.replace("<br/>", " ").replace("<br />", " ").replace("<br>", " ")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def parse_post_data(headers: Dict[str, str], post_data: str) -> Dict[str, str]:
    content_type = headers.get("content-type", "")
    if post_data.strip().startswith("{") or "application/json" in content_type:
        try:
            data = json.loads(post_data)
            return {str(k): str(v) for k, v in data.items()}
        except Exception:
            return {}
    if "=" in post_data:
        parsed = parse_qs(post_data, keep_blank_values=True)
        return {k: v[-1] if v else "" for k, v in parsed.items()}
    return {}


def find_key_by_value(data: Dict[str, str], candidates: List[str], target: int) -> str | None:
    for key in candidates:
        if key in data:
            try:
                if int(float(data[key])) == target:
                    return key
            except Exception:
                continue
    return None


def clean_headers(thead: List[str]) -> List[str]:
    return [strip_html(h) for h in thead]


def clean_row(row: List[Any]) -> List[str]:
    cleaned = []
    for item in row:
        if item is None:
            cleaned.append("")
            continue
        cleaned.append(strip_html(str(item)))
    return cleaned


def pick_headers_for_request(req_headers: Dict[str, str], referer: str) -> Dict[str, str]:
    headers = {}
    if "user-agent" in req_headers:
        headers["user-agent"] = req_headers["user-agent"]
    if "content-type" in req_headers:
        headers["content-type"] = req_headers["content-type"]
    else:
        headers["content-type"] = "application/x-www-form-urlencoded; charset=UTF-8"
    headers["x-requested-with"] = "XMLHttpRequest"
    headers["referer"] = referer
    return headers


def load_json_response(text: str) -> Tuple[Dict[str, Any] | None, str | None]:
    try:
        return json.loads(text), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def build_post_body(fields: Dict[str, str], content_type: str) -> str:
    if "application/json" in content_type.lower():
        return json.dumps(fields, ensure_ascii=False)
    return urlencode(fields)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paginate water quality data and export CSV.")
    parser.add_argument(
        "--url",
        default="https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/Main.html",
    )
    parser.add_argument("--out", default="cnemc_data/water_quality.csv")
    parser.add_argument("--wait-ms", type=int, default=8000)
    parser.add_argument("--headed", action="store_true", help="Run with browser UI")
    parser.add_argument("--max-pages", type=int, default=0, help="0 means no limit")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        found = {
            "data": None,
            "req_headers": None,
            "post_data": None,
            "api_url": None,
            "raw_text": None,
        }
        last_publish_text = None

        def handle_response(resp):
            nonlocal last_publish_text
            if "GJZ/Ajax/Publish.ashx" not in resp.url:
                return
            try:
                text = resp.text()
            except Exception:
                return
            last_publish_text = text
            data, _ = load_json_response(text)
            if isinstance(data, dict) and "tbody" in data and found["data"] is None:
                req = resp.request
                found["data"] = data
                found["req_headers"] = req.headers
                found["post_data"] = req.post_data or ""
                found["api_url"] = req.url
                found["raw_text"] = text

        page.on("response", handle_response)
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_timeout(args.wait_ms)

        if not isinstance(found["data"], dict) or "tbody" not in found["data"]:
            debug_path = Path("cnemc_data/first_response.txt")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(last_publish_text or "", encoding="utf-8")
            raise RuntimeError(
                "Unexpected response format; missing tbody. "
                f"Saved last Publish.ashx response to {debug_path}."
            )

        first_data = found["data"]
        req_headers = found["req_headers"] or {}
        post_data = found["post_data"] or ""
        api_url = found["api_url"] or ""

        rows_first = first_data.get("tbody", [])
        total_records = int(first_data.get("records", 0))
        rows_per_page = len(rows_first)

        post_fields = parse_post_data(req_headers, post_data)
        page_key = find_key_by_value(post_fields, PAGE_KEYS, 1) or find_key_by_value(
            post_fields, PAGE_KEYS, 0
        )
        size_key = find_key_by_value(post_fields, SIZE_KEYS, rows_per_page)

        if not page_key:
            debug_path = Path("cnemc_data/request_payload.json")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(json.dumps(post_fields, ensure_ascii=False, indent=2), encoding="utf-8")
            raise RuntimeError(
                "Could not determine page parameter key from request. "
                f"Saved request payload to {debug_path}."
            )

        start_page = int(float(post_fields.get(page_key, 1)))
        total_pages = math.ceil(total_records / rows_per_page) if rows_per_page else 0

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        headers = clean_headers(first_data.get("thead", []))
        all_rows = [clean_row(r) for r in rows_first]

        headers_for_request = pick_headers_for_request(req_headers, args.url)
        content_type = headers_for_request.get("content-type", "application/x-www-form-urlencoded; charset=UTF-8")

        debug_request = {
            "api_url": api_url,
            "post_fields": post_fields,
            "page_key": page_key,
            "size_key": size_key,
            "rows_per_page": rows_per_page,
            "total_records": total_records,
            "start_page": start_page,
        }
        debug_path = Path("cnemc_data/first_request.json")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(json.dumps(debug_request, ensure_ascii=False, indent=2), encoding="utf-8")

        max_pages = args.max_pages if args.max_pages > 0 else total_pages
        for page_num in range(start_page + 1, max_pages + 1):
            post_fields[page_key] = str(page_num)
            if size_key:
                post_fields[size_key] = str(rows_per_page)
            body = build_post_body(post_fields, content_type)
            resp_info = page.evaluate(
                """async ({ url, body, contentType }) => {
                    const resp = await fetch(url, {
                        method: "POST",
                        headers: {
                            "Content-Type": contentType,
                            "X-Requested-With": "XMLHttpRequest"
                        },
                        body,
                        credentials: "include"
                    });
                    const text = await resp.text();
                    return { status: resp.status, text };
                }""",
                {"url": api_url, "body": body, "contentType": content_type},
            )
            if resp_info.get("status") != 200:
                break
            raw_page_text = resp_info.get("text", "")
            try:
                page_data = json.loads(raw_page_text)
            except Exception:
                debug_path = Path(f"cnemc_data/page_{page_num}_response.txt")
                debug_path.write_text(raw_page_text, encoding="utf-8")
                raise RuntimeError(
                    f"Failed to parse JSON on page {page_num}. "
                    f"Saved raw response to {debug_path}."
                )
            page_rows = page_data.get("tbody", [])
            if not page_rows:
                break
            all_rows.extend(clean_row(r) for r in page_rows)

        browser.close()

        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(all_rows)


if __name__ == "__main__":
    main()
