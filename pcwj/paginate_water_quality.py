import argparse
import csv
import html
import json
import math
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlencode

PUBLISH_ENDPOINT = "https://szzdjc.cnemc.cn:8070/GJZ/Ajax/Publish.ashx"
COMMON_JS_URL = "https://szzdjc.cnemc.cn:8070/GJZ/Scripts/Publish/Common.js?v2.1"
MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}

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


def curl_bytes(url: str) -> bytes:
    proc = subprocess.run(
        ["curl", "-sS", "-L", url],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout


def curl_post_json(url: str, form: Dict[str, str]) -> Dict[str, Any]:
    body = urlencode(form)
    proc = subprocess.run(
        [
            "curl",
            "-sS",
            "-X",
            "POST",
            url,
            "-H",
            "Content-Type: application/x-www-form-urlencoded; charset=UTF-8",
            "--data",
            body,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    data, err = load_json_response(proc.stdout.decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Failed to parse API JSON. {err or ''}".strip())
    return data


def extract_area_info(common_js_text: str) -> List[Dict[str, Any]]:
    marker = "var _AreaInfo"
    start = common_js_text.find(marker)
    if start < 0:
        raise RuntimeError("Failed to locate `_AreaInfo` in Common.js.")

    bracket_start = common_js_text.find("[", start)
    if bracket_start < 0:
        raise RuntimeError("Failed to locate `_AreaInfo` array start in Common.js.")

    depth = 0
    in_string = False
    escape = False
    end = -1
    for i in range(bracket_start, len(common_js_text)):
        ch = common_js_text[i]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "[":
            depth += 1
            continue
        if ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end < 0:
        raise RuntimeError("Failed to find end of `_AreaInfo` array in Common.js.")

    payload = common_js_text[bracket_start:end]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse `_AreaInfo` JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise RuntimeError("Unexpected `_AreaInfo` format; expected list.")
    return parsed


def iter_city_entries(area_info: List[Dict[str, Any]]) -> List[Tuple[str, str, str, str]]:
    entries: List[Tuple[str, str, str, str]] = []
    for province in area_info:
        province_name = str(province.get("AreaName", "")).strip()
        province_code = str(province.get("AreaID", "")).strip()
        children = province.get("children") or []

        if province_name in MUNICIPALITIES:
            for child in children:
                district_name = str(child.get("AreaName", "")).strip()
                district_code = str(child.get("AreaID", "")).strip()
                if not district_name or not district_code:
                    continue
                entries.append((province_name, province_code, district_name, district_code))
            continue

        for child in children:
            city_name = str(child.get("AreaName", "")).strip()
            city_code = str(child.get("AreaID", "")).strip()
            if not city_name or not city_code:
                continue
            entries.append((province_name, province_code, city_name, city_code))
    return entries


def enrich_headers_with_city(headers: List[str]) -> List[str]:
    if headers and headers[0] == "省份":
        return [headers[0], "城市", *headers[1:]]
    return ["城市", *headers]


def enrich_row_with_city(row: List[str], city_name: str) -> List[str]:
    if row and row[0] and len(row) >= 1:
        return [row[0], city_name, *row[1:]]
    return [city_name, *row]


def export_csv_from_response_text(response_text: str, out_path: Path) -> None:
    data, err = load_json_response(response_text)
    if not isinstance(data, dict):
        raise RuntimeError(f"Failed to parse response JSON. {err or ''}".strip())

    headers = clean_headers(data.get("thead", []))
    rows = [clean_row(r) for r in data.get("tbody", [])]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(headers)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paginate water quality data and export CSV.")
    parser.add_argument(
        "--url",
        default="https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/Main.html",
    )
    parser.add_argument("--out", default="cnemc_data/water_quality.csv")
    parser.add_argument(
        "--from-file",
        default="",
        help="Export CSV from a saved Publish.ashx response file (offline mode).",
    )
    parser.add_argument(
        "--with-city",
        action="store_true",
        help="Fetch per-city data and add a 城市 column (uses curl; slower but adds city).",
    )
    parser.add_argument(
        "--common-js",
        default="cnemc_data/Common.js",
        help="Cached Common.js path for city list (downloaded if missing).",
    )
    parser.add_argument("--refresh-common-js", action="store_true", help="Re-download Common.js")
    parser.add_argument("--sleep-ms", type=int, default=50, help="Sleep between city requests")
    parser.add_argument("--max-cities", type=int, default=0, help="0 means no limit")
    parser.add_argument("--wait-ms", type=int, default=8000)
    parser.add_argument("--headed", action="store_true", help="Run with browser UI")
    parser.add_argument("--max-pages", type=int, default=0, help="0 means no limit")
    args = parser.parse_args()

    out_path = Path(args.out)
    if args.with_city and args.from_file:
        raise SystemExit("--with-city cannot be used together with --from-file.")

    if args.with_city:
        common_js_path = Path(args.common_js)
        if args.refresh_common_js or not common_js_path.exists():
            common_js_path.parent.mkdir(parents=True, exist_ok=True)
            common_js_path.write_bytes(curl_bytes(COMMON_JS_URL))
        common_js_text = common_js_path.read_text(encoding="utf-8-sig", errors="replace")
        area_info = extract_area_info(common_js_text)
        cities = iter_city_entries(area_info)
        if args.max_cities > 0:
            cities = cities[: args.max_cities]

        headers: List[str] = []
        all_rows: List[List[str]] = []
        for idx, (province_name, _province_code, city_name, city_code) in enumerate(cities, start=1):
            data = curl_post_json(
                PUBLISH_ENDPOINT,
                {
                    "action": "getRealDatas",
                    "AreaID": city_code,
                    "RiverID": "",
                    "MNName": "",
                    "PageIndex": "1",
                    "PageSize": "9999",
                },
            )
            if not headers:
                base_headers = clean_headers(data.get("thead", []))
                headers = enrich_headers_with_city(base_headers)
            tbody = data.get("tbody", [])
            if isinstance(tbody, list) and tbody:
                for r in tbody:
                    all_rows.append(enrich_row_with_city(clean_row(r), city_name))
            if args.sleep_ms > 0 and idx < len(cities):
                time.sleep(args.sleep_ms / 1000.0)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(all_rows)
        return

    if args.from_file:
        response_path = Path(args.from_file)
        export_csv_from_response_text(response_path.read_text(encoding="utf-8"), out_path)
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
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
        page.set_default_navigation_timeout(60000)
        page.set_default_timeout(60000)

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
        last_error = None
        for wait_until in ("domcontentloaded", "load"):
            try:
                page.goto(args.url, wait_until=wait_until)
                page.wait_for_timeout(args.wait_ms)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error

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
