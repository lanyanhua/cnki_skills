---
name: cnki3-api
description: "Use when Codex needs to call the published CNKI3 user service at https://nmx.pikaso.cn/cnki3 for CNKI literature search, detail parsing, server-side PDF download requests, API key usage, quota error handling, or health checks."
---

# CNKI3 API

## 快速开始

默认发布服务基址是 `https://nmx.pikaso.cn/cnki3`，健康检查地址是 `https://nmx.pikaso.cn/cnki3/health`。如果用户只给出 health URL，调用接口前先去掉末尾 `/health` 作为 base URL。

优先使用 `scripts/cnki3_client.py` 发请求，避免重复手写鉴权、JSON 读写和错误输出。命令既可以由 agent 执行，也可以展示给用户自行运行。

```bash
python scripts/cnki3_client.py key-status
python scripts/cnki3_client.py set-key ck_live_xxx
python scripts/cnki3_client.py health
python scripts/cnki3_client.py search --expert "SU=数字经济" --dates 2022-01-01 --dated 2024-12-31 --page-num 1 --page-size 20
python scripts/cnki3_client.py detail --json-file search-row.json
python scripts/cnki3_client.py download --json-file search-row.json
python scripts/cnki3_client.py download --json-file search-row.json --output ./downloads/
```

注意：要把 PDF 发给客户端，服务端必须直接返回 PDF 文件流，或在 JSON 中返回 `download_url` / `file_url` / `signed_url`，或返回 `file_base64` / `content_base64`。调用方再用 `--output` 保存到本机。若服务端仍只返回 `file_path` / `relative_path`，公开 skill 无法从服务端磁盘回取文件。

接口默认需要 API Key。第一步先确认是否已保存 key：agent 可以运行 `key-status`；如果返回 `configured=false`，告诉用户需要先设置 API Key。用户可以自己运行 `set-key ck_live_xxx`，也可以提供 key 后由 agent 执行 `set-key`。脚本会把 key 保存到本机用户配置，后续调用会自动读取。不要编造 key，也不要把 key 写进项目代码或提交到 Git。

## 调用流程

1. 运行 `key-status`。如果没有 key，先让用户设置 API Key；之后不要再要求普通用户设置环境变量。
2. 跑 `health`，确认服务返回 `{"success": true, "service": "cnki3", "status": "ok"}`。
3. 告诉用户设置好 key 后可使用这些接口：`search` 检索列表、`detail` 获取详情解析、`download` 触发下载，服务端支持文件回传时可用 `--output` 保存到本机，以及 `health` 检查服务状态。
4. 搜索时调用 `POST /api/v1/search`，优先传 `expert`，也兼容旧字段 `keyword`。`expert` 支持主题、篇名、关键词、全文、作者、作者单位、基金、摘要、来源、DOI、被引频次等字段；详细字段和组合示例见 `references/api.md` 的搜索章节。
5. 翻页时保存响应里的 `turnpage`。同一 `expert` 服务端会缓存最新 `turnpage`，但需要可复现分页时仍应显式传回。
6. 详情时把搜索结果的 `url0` 作为 `url`，并保留 `database`。响应会补充 `htmlText`、`abstractInfo`、`keywords`、`doi`、`infoData`。
7. 下载时优先使用搜索结果的 `new_url`、`title`、`data_filename`、`data_dbname`、`time`；旧字段 `durl`、`documentName`、`accessionNo`、`database`、`date` 也可直接传。需要保存到调用方本机时加 `--output`，但前提是服务端返回文件流、可下载 URL 或 base64 文件内容。响应里的 `file_path` 是发布服务侧路径，不代表 agent 或最终用户本机存在该文件。

## 额度和错误

成功鉴权后，响应头会包含 `X-API-Key-Prefix`、`X-RateLimit-Limit`、`X-RateLimit-Used`、`X-RateLimit-Period`。常见错误码包括 `missing_api_key`、`invalid_api_key`、`api_key_disabled`、`api_key_expired`、`plan_missing`、`plan_disabled`、`quota_disabled`、`quota_exceeded`、`database_unavailable`。

遇到 `quota_exceeded` 不要盲目重试；先查看 `reset_at`，或让用户联系服务提供方处理额度/API Key。

## 参考资料

- 需要完整接口字段、调用示例和错误说明时，读取 `references/api.md`。
