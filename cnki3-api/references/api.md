# CNKI3 接口参考

## 服务地址

- 默认 base URL: `https://nmx.pikaso.cn/cnki3`
- 健康检查: `GET /health`
- 管理页面: `GET /admin`
- 业务接口: `POST /api/v1/search`、`POST /api/v1/detail`、`POST /api/v1/download`

如果外部只给出 `https://nmx.pikaso.cn/cnki3/health`，去掉 `/health` 后再拼业务路径。

## 鉴权

业务接口默认开启 API Key 鉴权。任选一种传法：

```bash
X-API-Key: ck_live_xxx
Authorization: Bearer ck_live_xxx
```

源码也兼容 query/body 里的 `api_key` 或 `apiKey`，但调用时优先用 header。服务端会在进入业务处理前移除 body 内的 `api_key`/`apiKey`，避免透传给下载或详情逻辑。

管理接口 `/admin/api/*` 在配置 `CNKI_ADMIN_TOKEN` 时需要：

```bash
X-Admin-Token: admin-secret
```

## 搜索

`POST /api/v1/search`

请求字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `expert` | 是 | 专家检索表达式，如 `SU=数字经济`、`LY=经济研究`；兼容旧字段 `keyword` |
| `dates` | 否 | 起始发表日期；兼容 `dateStart`、`startDate`、`start_date` |
| `dated` | 否 | 截止发表日期；兼容 `dateEnd`、`endDate`、`end_date` |
| `pageNum` | 否 | 页码，默认 `1`；兼容 `page_num` |
| `pageSize` | 否 | 每页数量，默认 `20`；兼容 `page_size` |
| `sortField` | 否 | 排序字段，默认 `PT` |
| `turnpage` | 否 | CNKI 翻页令牌；不传时服务按 `expert` 读取缓存 |

示例：

```json
{
  "expert": "SU=数字经济",
  "dates": "2022-01-01",
  "dated": "2024-12-31",
  "pageNum": 1,
  "pageSize": 20,
  "sortField": "PT"
}
```

响应字段：

- `success`: 布尔值。
- `total`: 总记录数；未解析到时为 `0`。
- `pageNum` / `pageSize`: 当前分页。
- `turnpage`: 后续同一检索翻页可复用。
- `data`: 搜索结果列表。常用字段包括 `title`、`author`、`source`、`time`、`data_dbname`、`data_filename`、`url0`、`url1`、`new_url`、`database`、`quoteCnt`、`downloadCnt`。

服务端遇到 CNKI “暂无数据”页面时仍返回 `success=true`、`total=0`、`data=[]`。

## 详情

`POST /api/v1/detail`

请求字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `url` | 是 | 详情页 URL；兼容搜索结果的 `url0` |
| `database` | 否 | 数据库类型；外文期刊会走不同解析分支 |

`url` 支持 `//kns.cnki.net/...` 或相对路径，服务端会归一化到 `https://kns.cnki.net/`。

响应中的 `data` 会保留原始记录并补充：

- `htmlText`: 详情正文 HTML 片段。
- `abstractInfo`: 摘要或正文快照。
- `keywords`: 关键词。
- `doi`: DOI。
- `infoData`: 其他字段的 JSON 字符串。

遇到安全验证页、空详情或 “知网节超时验证” 时通常返回 `success=false`。

## 下载

`POST /api/v1/download`

请求字段：

| 新字段 | 旧字段兼容 | 说明 |
| --- | --- | --- |
| `new_url` | `durl` | 下载入口，必填其一 |
| `title` | `documentName` | 文件标题 |
| `data_filename` | `accessionNo` | 文献 accession 编号 |
| `data_dbname` | `database` | 下载目录或数据库分组 |
| `time` | `date` | 用于推导年份目录 |

响应：

```json
{
  "success": true,
  "file_path": "/app/downloads/CJFQ/2024/文章标题_XXXX202401001.pdf",
  "relative_path": "CJFQ/2024/文章标题_XXXX202401001.pdf"
}
```

下载逻辑复用 `cnki2.ettsg`，并受环境变量 `CNKI_DOWNLOAD_DIR`、`CNKI_ETTSG_USERNAME`、`CNKI_ETTSG_PASSWORD`、`CNKI_ETTSG_BASE_URL` 影响。

## 管理接口

- `GET /admin/api/bootstrap`: 返回套餐、API Key、用量、日志聚合。
- `GET /admin/api/plans`: 列出套餐。
- `POST /admin/api/plans`: 新增套餐。
- `PATCH /admin/api/plans/<id>`: 更新套餐。
- `GET /admin/api/api-keys`: 列出 API Key。
- `POST /admin/api/api-keys`: 创建 API Key，响应只在创建时返回明文 `api_key`。
- `PATCH /admin/api/api-keys/<id>`: 更新 API Key。
- `GET /admin/api/access-logs?limit=100`: 查看访问日志，`limit` 范围 `1..500`。
- `GET /admin/api/usage?limit=200`: 查看用量计数，`limit` 范围 `1..500`。

套餐字段：

- `search_limit` / `detail_limit` / `download_limit`: `-1` 表示不限量，`0` 表示禁用该接口。
- `period_seconds`: 额度窗口秒数，必须大于 `0`。
- `active`: 是否启用。

API Key 字段：

- `plan_id`: 绑定套餐。
- `expires_at`: ISO 日期时间，可空。
- `active`: 是否启用。
- `note`: 备注。

## 运行环境变量

- `PORT`: 服务端口，默认 `18852`。
- `CNKI_TURNPAGE_CACHE_TTL`: turnpage 缓存秒数，默认 `3600`。
- `CNKI_TURNPAGE_CACHE_SIZE`: turnpage 缓存 expert 数量，默认 `500`。
- `CNKI_SEARCH_PREFER_CURL`: 搜索是否优先使用 `curl_cffi`，默认 `false`。
- `CNKI_DOWNLOAD_DIR`: 下载文件目录，默认 `/app/downloads`。
- `CNKI_AUTH_ENABLED`: 是否开启 API Key 鉴权，默认 `true`。
- `CNKI_MYSQL_HOST` / `CNKI_MYSQL_PORT` / `CNKI_MYSQL_USER` / `CNKI_MYSQL_PASSWORD` / `CNKI_MYSQL_DATABASE`: 鉴权库配置。
- `CNKI_ADMIN_TOKEN`: 管理接口 token。
- `CNKI_MYSQL_CONNECT_TIMEOUT` / `CNKI_MYSQL_READ_TIMEOUT` / `CNKI_MYSQL_WRITE_TIMEOUT`: MySQL 超时秒数。

## 错误和限额

常见 JSON 错误格式：

```json
{
  "success": false,
  "error": "接口调用次数已用完",
  "code": "quota_exceeded",
  "quota_limit": 1,
  "used_count": 1,
  "reset_at": "2026-05-09 00:00:00"
}
```

鉴权成功的业务响应会带限额响应头：

- `X-API-Key-Prefix`
- `X-RateLimit-Limit`
- `X-RateLimit-Used`
- `X-RateLimit-Period`

出现 `quota_exceeded`、`quota_disabled`、`api_key_disabled`、`api_key_expired` 时不要重试同一个请求，先处理套餐或 key。
