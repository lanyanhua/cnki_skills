# CNKI3 接口参考

## 服务地址

- 默认 base URL: `https://nmx.pikaso.cn/cnki3`
- 健康检查: `GET /health`
- 用户接口: `POST /api/v1/search`、`POST /api/v1/detail`、`POST /api/v1/download`

如果外部只给出 `https://nmx.pikaso.cn/cnki3/health`，去掉 `/health` 后再拼业务路径。

## 鉴权

业务接口默认开启 API Key 鉴权。任选一种传法：

```bash
X-API-Key: ck_live_xxx
Authorization: Bearer ck_live_xxx
```

源码也兼容 query/body 里的 `api_key` 或 `apiKey`，但调用时优先用 header。服务端会在进入业务处理前移除 body 内的 `api_key`/`apiKey`，避免透传给下载或详情逻辑。

## 搜索

`POST /api/v1/search`

请求字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `expert` | 是 | CNKI 专家检索表达式；兼容旧字段 `keyword`。字段、运算符和示例见下方 `expert 表达式` |
| `dates` | 否 | 起始发表日期；兼容 `dateStart`、`startDate`、`start_date` |
| `dated` | 否 | 截止发表日期；兼容 `dateEnd`、`endDate`、`end_date` |
| `pageNum` | 否 | 页码，默认 `1`；兼容 `page_num` |
| `pageSize` | 否 | 每页数量，默认 `20`；兼容 `page_size` |
| `sortField` | 否 | 排序字段，默认 `PT` |
| `turnpage` | 否 | CNKI 翻页令牌；不传时服务按 `expert` 读取缓存 |

### expert 表达式

`expert` 原样传给 CNKI 专家检索。一般写成 `字段=检索词` 或用多个条件组合；检索词建议使用单引号包裹，简单词也可直接写，例如 `SU=数字经济`。

可检索字段：

| 字段 | 含义 |
| --- | --- |
| `SU` | 主题 |
| `TKA` | 篇关摘 |
| `KY` | 关键词 |
| `TI` | 篇名 |
| `FT` | 全文 |
| `AU` | 作者 |
| `FI` | 第一作者 |
| `RP` | 通讯作者 |
| `AF` | 作者单位 |
| `FU` | 基金 |
| `AB` | 摘要 |
| `CO` | 小标题 |
| `RF` | 参考文献 |
| `CLC` | 分类号 |
| `LY` | 文献来源 |
| `DOI` | DOI |
| `CF` | 被引频次 |

常用组合写法：

- `and` 或 `*`: 同时满足多个条件。
- `+`: 或，满足任一条件。
- `-`: 排除某个条件。
- `%`: 模糊匹配，常用于作者姓氏等场景。
- `(...)`: 分组，控制组合优先级。

示例：

1. `TI='生态' and KY='生态文明' and (AU % '陈' + '王')`

   检索篇名包括“生态”、关键词包括“生态文明”，并且作者为“陈”姓和“王”姓的所有文章。

2. `SU='北京' * '奥运' and FT='环境保护'`

   检索主题包括“北京”及“奥运”，并且全文中包括“环境保护”的信息。

3. `SU=('经济发展' + '可持续发展') * '转变' - '泡沫'`

   检索“经济发展”或“可持续发展”有关“转变”的信息，并去除与“泡沫”有关的部分内容。

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

## 运行环境变量

- `CNKI3_BASE_URL`: 覆盖默认发布地址。
- `CNKI3_API_KEY`: 用户 API Key。
- `CNKI3_TIMEOUT`: CLI 请求超时秒数，默认 `60`。

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

出现 `quota_exceeded`、`quota_disabled`、`api_key_disabled`、`api_key_expired` 时不要重试同一个请求，先让用户更换有效 API Key 或联系服务提供方处理额度。
