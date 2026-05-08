---
name: cnki3-api
description: "Use when Codex needs to call or maintain the published CNKI3 service at https://nmx.pikaso.cn/cnki3 for CNKI literature search, detail parsing, PDF download, API key quota handling, admin plan/key management, health checks, or workflows derived from /Users/lyh/IdeaProjects/qikan_reptile/new/cnki3."
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
python scripts/cnki3_client.py --admin-token "$CNKI3_ADMIN_TOKEN" admin bootstrap
```

业务接口默认需要 API Key。先从用户、环境变量 `CNKI3_API_KEY`、或现有安全配置中取得 key；不要编造 key。管理接口可能需要 `CNKI3_ADMIN_TOKEN`，用 `X-Admin-Token` 传递。

## 调用流程

1. 先跑 `health`，确认服务返回 `{"success": true, "service": "cnki3", "status": "ok"}`。
2. 搜索时调用 `POST /api/v1/search`，优先传 `expert`，也兼容旧字段 `keyword`。常见表达式：主题 `SU=关键词`，期刊 `LY=期刊名`。
3. 翻页时保存响应里的 `turnpage`。同一 `expert` 服务端会缓存最新 `turnpage`，但需要可复现分页时仍应显式传回。
4. 详情时把搜索结果的 `url0` 作为 `url`，并保留 `database`。响应会补充 `htmlText`、`abstractInfo`、`keywords`、`doi`、`infoData`。
5. 下载时优先使用搜索结果的 `new_url`、`title`、`data_filename`、`data_dbname`、`time`；旧字段 `durl`、`documentName`、`accessionNo`、`database`、`date` 也可直接传。

## 额度和错误

成功鉴权后，响应头会包含 `X-API-Key-Prefix`、`X-RateLimit-Limit`、`X-RateLimit-Used`、`X-RateLimit-Period`。常见错误码包括 `missing_api_key`、`invalid_api_key`、`api_key_disabled`、`api_key_expired`、`plan_missing`、`plan_disabled`、`quota_disabled`、`quota_exceeded`、`database_unavailable`。

注意：鉴权在业务 handler 前消耗额度并记录访问日志。遇到 `quota_exceeded` 不要盲目重试；先查看 `reset_at` 或切换有效套餐/API Key。

## 参考资料

- 需要完整接口字段、curl 示例和管理接口时，读取 `references/api.md`。
- 需要理解原项目的爬取、同步、拆分、并发和维护约束时，读取 `references/workflows.md`。

## 维护约束

如果修改 `/Users/lyh/IdeaProjects/qikan_reptile/new/cnki3` 源码，同一业务流程中多个步骤会修改同一张表或同一条主记录时，优先合并成一次更新。确实需要多次写库时，必须用中文注释说明写入时点差异、并发影响和不能合并的原因。
