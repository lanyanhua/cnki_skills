---
name: cnki3-api
description: "Use when Codex needs to call the published CNKI3 user service at https://nmx.pikaso.cn/cnki3 for CNKI literature search, detail parsing, PDF download, API key usage, quota error handling, or health checks."
---

# CNKI3 API

## 快速开始

默认发布服务基址是 `https://nmx.pikaso.cn/cnki3`，健康检查地址是 `https://nmx.pikaso.cn/cnki3/health`。如果用户只给出 health URL，调用接口前先去掉末尾 `/health` 作为 base URL。

优先使用 `scripts/cnki3_client.py` 发请求，避免重复手写鉴权、JSON 读写和错误输出：

```bash
python scripts/cnki3_client.py health
python scripts/cnki3_client.py --api-key "$CNKI3_API_KEY" search --expert "SU=数字经济" --dates 2022-01-01 --dated 2024-12-31 --page-num 1 --page-size 20
python scripts/cnki3_client.py --api-key "$CNKI3_API_KEY" detail --json-file search-row.json
python scripts/cnki3_client.py --api-key "$CNKI3_API_KEY" download --json-file search-row.json
```

接口默认需要 API Key。先从用户、环境变量 `CNKI3_API_KEY`、或现有安全配置中取得 key；不要编造 key，也不要把 key 写进代码或提交到 Git。

## 调用流程

1. 先跑 `health`，确认服务返回 `{"success": true, "service": "cnki3", "status": "ok"}`。
2. 搜索时调用 `POST /api/v1/search`，优先传 `expert`，也兼容旧字段 `keyword`。常见表达式：主题 `SU=关键词`，期刊 `LY=期刊名`。
3. 翻页时保存响应里的 `turnpage`。同一 `expert` 服务端会缓存最新 `turnpage`，但需要可复现分页时仍应显式传回。
4. 详情时把搜索结果的 `url0` 作为 `url`，并保留 `database`。响应会补充 `htmlText`、`abstractInfo`、`keywords`、`doi`、`infoData`。
5. 下载时优先使用搜索结果的 `new_url`、`title`、`data_filename`、`data_dbname`、`time`；旧字段 `durl`、`documentName`、`accessionNo`、`database`、`date` 也可直接传。

## 额度和错误

成功鉴权后，响应头会包含 `X-API-Key-Prefix`、`X-RateLimit-Limit`、`X-RateLimit-Used`、`X-RateLimit-Period`。常见错误码包括 `missing_api_key`、`invalid_api_key`、`api_key_disabled`、`api_key_expired`、`plan_missing`、`plan_disabled`、`quota_disabled`、`quota_exceeded`、`database_unavailable`。

遇到 `quota_exceeded` 不要盲目重试；先查看 `reset_at`，或让用户联系服务提供方处理额度/API Key。

## 参考资料

- 需要完整接口字段、调用示例和错误说明时，读取 `references/api.md`。
