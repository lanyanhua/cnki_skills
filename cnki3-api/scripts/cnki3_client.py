#!/usr/bin/env python3
"""CLI helper for the published CNKI3 API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://nmx.pikaso.cn/cnki3"
RATE_LIMIT_HEADERS = {
    "X-API-Key-Prefix",
    "X-RateLimit-Limit",
    "X-RateLimit-Used",
    "X-RateLimit-Period",
    "X-Request-ID",
}


def config_path() -> Path:
    return Path.home() / ".cnki3" / "config.json"


def normalize_base_url(base_url: str | None) -> str:
    value = (base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    if value.endswith("/health"):
        value = value[: -len("/health")]
    return value.rstrip("/")


def load_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    if not text.strip():
        return {}
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise SystemExit("JSON input must be an object.")
    return payload


def load_saved_api_key() -> str:
    path = config_path()
    if not path.exists():
        return ""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("api_key") or "").strip()


def save_api_key(api_key: str) -> Path:
    api_key = str(api_key or "").strip()
    if not api_key:
        raise SystemExit("API Key 不能为空。")
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"api_key": api_key}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(path, 0o600)
    return path


def clear_saved_api_key() -> Path:
    path = config_path()
    if path.exists():
        path.unlink()
    return path


def resolve_api_key(cli_api_key: str | None) -> str:
    return str(cli_api_key or os.getenv("CNKI3_API_KEY") or load_saved_api_key() or "").strip()


def put_if_present(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None and value != "":
        payload[key] = value


def parse_body(raw_body: bytes, headers: dict[str, str]) -> Any:
    charset = "utf-8"
    content_type = headers.get("Content-Type", "")
    if "charset=" in content_type:
        charset = content_type.rsplit("charset=", 1)[-1].split(";", 1)[0].strip()
    text = raw_body.decode(charset or "utf-8", errors="replace")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def request_json(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout: float = 60,
) -> tuple[int, dict[str, str], Any]:
    if not path.startswith("/"):
        path = "/" + path
    url = normalize_base_url(base_url) + path
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key

    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_headers = dict(response.headers.items())
            return response.status, response_headers, parse_body(response.read(), response_headers)
    except urllib.error.HTTPError as error:
        response_headers = dict(error.headers.items())
        return error.code, response_headers, parse_body(error.read(), response_headers)
    except urllib.error.URLError as error:
        return 599, {}, {"success": False, "error": str(error.reason), "code": "network_error"}


def output_response(status: int, headers: dict[str, str], body: Any, *, include_meta: bool) -> int:
    if include_meta or status >= 400:
        selected_headers = {name: value for name, value in headers.items() if name in RATE_LIMIT_HEADERS}
        result: Any = {"status_code": status, "headers": selected_headers, "body": body}
    else:
        result = body
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status < 400 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="调用 CNKI3 用户接口。")
    parser.add_argument("--base-url", default=os.getenv("CNKI3_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", help="只在本次命令中使用这个 API Key")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("CNKI3_TIMEOUT", "60")))
    parser.add_argument("--meta", action="store_true", help="输出状态码和响应头")

    subparsers = parser.add_subparsers(dest="command", required=True)
    set_key = subparsers.add_parser("set-key", help="保存 API Key，只需运行一次")
    set_key.add_argument("api_key")
    subparsers.add_parser("clear-key", help="删除本机保存的 API Key")
    subparsers.add_parser("health", help="GET /health")

    search = subparsers.add_parser("search", help="POST /api/v1/search")
    search.add_argument("--json-file")
    search.add_argument("--expert")
    search.add_argument("--keyword")
    search.add_argument("--dates")
    search.add_argument("--dated")
    search.add_argument("--page-num", type=int)
    search.add_argument("--page-size", type=int)
    search.add_argument("--sort-field")
    search.add_argument("--turnpage")

    detail = subparsers.add_parser("detail", help="POST /api/v1/detail")
    detail.add_argument("--json-file")
    detail.add_argument("--url")
    detail.add_argument("--database")

    download = subparsers.add_parser("download", help="POST /api/v1/download")
    download.add_argument("--json-file")
    download.add_argument("--new-url")
    download.add_argument("--durl")
    download.add_argument("--title")
    download.add_argument("--document-name")
    download.add_argument("--data-filename")
    download.add_argument("--accession-no")
    download.add_argument("--data-dbname")
    download.add_argument("--database")
    download.add_argument("--time")
    download.add_argument("--date")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "set-key":
        path = save_api_key(args.api_key)
        print(
            json.dumps(
                {"success": True, "message": "API Key 已保存。", "config_path": str(path)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "clear-key":
        path = clear_saved_api_key()
        print(
            json.dumps(
                {"success": True, "message": "API Key 已删除。", "config_path": str(path)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "health":
        status, headers, body = request_json(
            base_url=args.base_url,
            method="GET",
            path="/health",
            timeout=args.timeout,
        )
        return output_response(status, headers, body, include_meta=args.meta)

    if args.command == "search":
        payload = load_json(args.json_file)
        put_if_present(payload, "expert", args.expert)
        put_if_present(payload, "keyword", args.keyword)
        put_if_present(payload, "dates", args.dates)
        put_if_present(payload, "dated", args.dated)
        put_if_present(payload, "pageNum", args.page_num)
        put_if_present(payload, "pageSize", args.page_size)
        put_if_present(payload, "sortField", args.sort_field)
        put_if_present(payload, "turnpage", args.turnpage)
        if not payload.get("expert") and not payload.get("keyword"):
            parser.error("search requires --expert, --keyword, or a JSON file containing one of them")
        path = "/api/v1/search"
        method = "POST"
        api_key = resolve_api_key(args.api_key)
    elif args.command == "detail":
        payload = load_json(args.json_file)
        put_if_present(payload, "url", args.url)
        put_if_present(payload, "database", args.database)
        if not payload.get("url") and not payload.get("url0"):
            parser.error("detail requires --url or a JSON file containing url/url0")
        path = "/api/v1/detail"
        method = "POST"
        api_key = resolve_api_key(args.api_key)
    elif args.command == "download":
        payload = load_json(args.json_file)
        put_if_present(payload, "new_url", args.new_url)
        put_if_present(payload, "durl", args.durl)
        put_if_present(payload, "title", args.title)
        put_if_present(payload, "documentName", args.document_name)
        put_if_present(payload, "data_filename", args.data_filename)
        put_if_present(payload, "accessionNo", args.accession_no)
        put_if_present(payload, "data_dbname", args.data_dbname)
        put_if_present(payload, "database", args.database)
        put_if_present(payload, "time", args.time)
        put_if_present(payload, "date", args.date)
        if not payload.get("new_url") and not payload.get("durl"):
            parser.error("download requires --new-url, --durl, or a JSON file containing one of them")
        path = "/api/v1/download"
        method = "POST"
        api_key = resolve_api_key(args.api_key)
    else:
        parser.error(f"unknown command: {args.command}")

    if not api_key:
        parser.error("未设置 API Key。请先运行一次: python scripts/cnki3_client.py set-key ck_live_xxx")

    status, headers, body = request_json(
        base_url=args.base_url,
        method=method,
        path=path,
        payload=payload,
        api_key=api_key,
        timeout=args.timeout,
    )
    return output_response(status, headers, body, include_meta=args.meta)


if __name__ == "__main__":
    raise SystemExit(main())
