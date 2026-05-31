#!/usr/bin/env python3
"""CLI helper for the published CNKI3 API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
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


def saved_api_key_status() -> dict[str, Any]:
    api_key = load_saved_api_key()
    path = config_path()
    return {
        "success": True,
        "configured": bool(api_key),
        "config_path": str(path),
    }


def resolve_api_key(cli_api_key: str | None) -> str:
    return str(cli_api_key or os.getenv("CNKI3_API_KEY") or load_saved_api_key() or "").strip()


def put_if_present(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None and value != "":
        payload[key] = value


def parse_body(raw_body: bytes, headers: dict[str, str]) -> Any:
    charset = "utf-8"
    content_type = ""
    for key, value in headers.items():
        if key.lower() == "content-type":
            content_type = value
            break
    if "charset=" in content_type:
        charset = content_type.rsplit("charset=", 1)[-1].split(";", 1)[0].strip()
    text = raw_body.decode(charset or "utf-8", errors="replace")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def header_value(headers: dict[str, str], name: str) -> str:
    wanted = name.lower()
    for key, value in headers.items():
        if key.lower() == wanted:
            return value
    return ""


def request_raw(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout: float = 60,
    accept: str = "application/json",
) -> tuple[int, dict[str, str], bytes]:
    if not path.startswith("/"):
        path = "/" + path
    url = normalize_base_url(base_url) + path
    headers = {"Accept": accept}
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
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as error:
        response_headers = dict(error.headers.items())
        return error.code, response_headers, error.read()
    except urllib.error.URLError as error:
        return 599, {}, json.dumps(
            {"success": False, "error": str(error.reason), "code": "network_error"},
            ensure_ascii=False,
        ).encode("utf-8")


def request_url_raw(
    *,
    url: str,
    api_key: str | None = None,
    timeout: float = 60,
    accept: str = "application/pdf, application/octet-stream, application/json",
) -> tuple[int, dict[str, str], bytes]:
    headers = {"Accept": accept}
    if api_key:
        headers["X-API-Key"] = api_key
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_headers = dict(response.headers.items())
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as error:
        response_headers = dict(error.headers.items())
        return error.code, response_headers, error.read()
    except urllib.error.URLError as error:
        return 599, {}, json.dumps(
            {"success": False, "error": str(error.reason), "code": "network_error"},
            ensure_ascii=False,
        ).encode("utf-8")


def request_json(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    api_key: str | None = None,
    timeout: float = 60,
) -> tuple[int, dict[str, str], Any]:
    status, headers, raw_body = request_raw(
        base_url=base_url,
        method=method,
        path=path,
        payload=payload,
        api_key=api_key,
        timeout=timeout,
    )
    return status, headers, parse_body(raw_body, headers)


def looks_like_json(headers: dict[str, str], raw_body: bytes) -> bool:
    content_type = header_value(headers, "Content-Type").lower()
    body_start = raw_body.lstrip()[:1]
    return "json" in content_type or body_start in {b"{", b"["}


def parse_json_if_present(raw_body: bytes, headers: dict[str, str]) -> Any:
    if not looks_like_json(headers, raw_body):
        return None
    return parse_body(raw_body, headers)


def content_disposition_filename(headers: dict[str, str]) -> str:
    value = header_value(headers, "Content-Disposition")
    for part in value.split(";"):
        key, separator, raw = part.strip().partition("=")
        if not separator:
            continue
        if key.lower() == "filename*":
            encoded = raw.strip().strip('"')
            if "''" in encoded:
                encoded = encoded.split("''", 1)[1]
            return urllib.parse.unquote(encoded).strip()
        if key.lower() == "filename":
            return urllib.parse.unquote(raw.strip().strip('"')).strip()
    return ""


def safe_filename(value: str, fallback: str = "download.pdf") -> str:
    filename = str(value or "").strip().replace("\x00", "")
    for char in ("/", "\\"):
        filename = filename.replace(char, "_")
    filename = filename.strip(" .")
    if not filename:
        filename = fallback
    return filename


def resolve_output_path(output: str, filename: str) -> Path:
    path = Path(output).expanduser()
    if str(output).endswith(("/", "\\")) or (path.exists() and path.is_dir()):
        path = path / safe_filename(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_download_bytes(raw_body: bytes, headers: dict[str, str], output: str, filename: str = "") -> dict[str, Any]:
    resolved_filename = filename or content_disposition_filename(headers) or "download.pdf"
    path = resolve_output_path(output, resolved_filename)
    with open(path, "wb") as handle:
        handle.write(raw_body)
    return {
        "success": True,
        "saved_path": str(path),
        "bytes": len(raw_body),
        "content_type": header_value(headers, "Content-Type"),
    }


def resolve_download_url(base_url: str, value: str) -> str:
    return urllib.parse.urljoin(normalize_base_url(base_url) + "/", value.strip())


def should_send_api_key(url: str, base_url: str) -> bool:
    parsed_url = urllib.parse.urlparse(url)
    parsed_base = urllib.parse.urlparse(normalize_base_url(base_url))
    return bool(parsed_url.netloc and parsed_url.netloc == parsed_base.netloc)


def output_download_file(
    *,
    base_url: str,
    payload: dict[str, Any],
    api_key: str,
    timeout: float,
    output: str,
) -> int:
    status, headers, raw_body = request_raw(
        base_url=base_url,
        method="POST",
        path="/api/v1/download",
        payload=payload,
        api_key=api_key,
        timeout=timeout,
        accept="application/pdf, application/octet-stream, application/json",
    )
    parsed_body = parse_json_if_present(raw_body, headers)
    if status >= 400:
        body = parsed_body if parsed_body is not None else parse_body(raw_body, headers)
        return output_response(status, headers, body, include_meta=True)

    if parsed_body is None:
        result = save_download_bytes(raw_body, headers, output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not isinstance(parsed_body, dict):
        return output_response(status, headers, parsed_body, include_meta=True)

    inline_base64 = parsed_body.get("file_base64") or parsed_body.get("content_base64")
    if inline_base64:
        try:
            file_bytes = base64.b64decode(str(inline_base64), validate=True)
        except Exception as error:
            print(
                json.dumps(
                    {"success": False, "code": "invalid_base64_file", "error": str(error), "body": parsed_body},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
        filename = str(parsed_body.get("filename") or parsed_body.get("file_name") or "")
        result = save_download_bytes(file_bytes, headers, output, filename=filename)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    download_url = str(
        parsed_body.get("download_url")
        or parsed_body.get("file_url")
        or parsed_body.get("signed_url")
        or ""
    ).strip()
    if download_url:
        resolved_url = resolve_download_url(base_url, download_url)
        url_api_key = api_key if should_send_api_key(resolved_url, base_url) else None
        file_status, file_headers, file_body = request_url_raw(
            url=resolved_url,
            api_key=url_api_key,
            timeout=timeout,
        )
        file_parsed_body = parse_json_if_present(file_body, file_headers)
        if file_status >= 400 or file_parsed_body is not None:
            return output_response(
                file_status,
                file_headers,
                file_parsed_body if file_parsed_body is not None else parse_body(file_body, file_headers),
                include_meta=True,
            )
        filename = str(parsed_body.get("filename") or parsed_body.get("file_name") or "")
        result = save_download_bytes(file_body, file_headers, output, filename=filename)
        result["source_url"] = resolved_url
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(
        json.dumps(
            {
                "success": False,
                "code": "server_side_path_only",
                "error": "服务端只返回了文件路径，没有返回 PDF 文件流、临时下载 URL 或 base64 文件内容。需要服务端开放流式下载、临时下载 URL 或文件回取接口。",
                "body": parsed_body,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1


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
    subparsers.add_parser("key-status", help="检查本机是否已保存 API Key")
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

    download = subparsers.add_parser("download", help="POST /api/v1/download；服务端支持文件回传时可用 --output 保存")
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
    download.add_argument("-o", "--output", help="保存服务端返回或回取到的 PDF；可传文件路径或目录")
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

    if args.command == "key-status":
        print(json.dumps(saved_api_key_status(), ensure_ascii=False, indent=2))
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

    if args.command == "download" and args.output:
        return output_download_file(
            base_url=args.base_url,
            payload=payload,
            api_key=api_key,
            timeout=args.timeout,
            output=args.output,
        )

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
