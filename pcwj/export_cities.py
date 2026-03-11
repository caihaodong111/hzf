import argparse
import csv
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


COMMON_JS_URL = "https://szzdjc.cnemc.cn:8070/GJZ/Scripts/Publish/Common.js?v2.1"
MUNICIPALITIES = {"北京市", "天津市", "上海市", "重庆市"}


@dataclass(frozen=True)
class CityRow:
    province_name: str
    province_code: str
    city_name: str
    city_code: str


def curl_get(url: str) -> bytes:
    proc = subprocess.run(
        ["curl", "-sS", "-L", url],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout


def extract_area_info(common_js_text: str) -> list[dict]:
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
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse `_AreaInfo` JSON: {exc}") from exc


def build_city_rows(area_info: list[dict]) -> list[CityRow]:
    rows: list[CityRow] = []
    for province in area_info:
        province_name = str(province.get("AreaName", "")).strip()
        province_code = str(province.get("AreaID", "")).strip()
        children = province.get("children") or []

        if province_name in MUNICIPALITIES:
            rows.append(
                CityRow(
                    province_name=province_name,
                    province_code=province_code,
                    city_name=province_name,
                    city_code=province_code,
                )
            )
            continue

        for child in children:
            city_name = str(child.get("AreaName", "")).strip()
            city_code = str(child.get("AreaID", "")).strip()
            if not city_name or not city_code:
                continue
            rows.append(
                CityRow(
                    province_name=province_name,
                    province_code=province_code,
                    city_name=city_name,
                    city_code=city_code,
                )
            )
    return rows


def write_csv(rows: list[CityRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["province_name", "province_code", "city_name", "city_code"])
        for row in rows:
            writer.writerow([row.province_name, row.province_code, row.city_name, row.city_code])


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CNEMC area city list to CSV.")
    parser.add_argument("--out", default="cnemc_data/cities.csv", help="Output CSV path")
    parser.add_argument(
        "--common-js",
        default="cnemc_data/Common.js",
        help="Path to cached Common.js (will be downloaded if missing).",
    )
    parser.add_argument("--refresh", action="store_true", help="Re-download Common.js")
    args = parser.parse_args()

    common_js_path = Path(args.common_js)
    if args.refresh or not common_js_path.exists():
        common_js_path.parent.mkdir(parents=True, exist_ok=True)
        common_js_path.write_bytes(curl_get(COMMON_JS_URL))

    common_js_text = common_js_path.read_text(encoding="utf-8-sig", errors="replace")
    area_info = extract_area_info(common_js_text)
    rows = build_city_rows(area_info)
    write_csv(rows, Path(args.out))


if __name__ == "__main__":
    main()
