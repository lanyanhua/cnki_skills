# CNKI3 原项目工作流参考

## 源码地图

- `server.py`: Flask 服务，提供健康检查、搜索、详情、下载、管理页面和管理 API。
- `auth_db.py`: MySQL 建库建表、套餐、API Key、限额窗口、访问日志。
- `cnki/client.py`: CNKI 请求客户端，负责 session 复用、代理刷新、grid 请求、详情请求。
- `cnki/session.py`: CNKI session 预热，顺序是首页、`top.js`、`IpLoginFlushPo`。
- `cnki/headers.py`: 统一构造首页、登录、grid、详情请求头。
- `cnki/parsers.py`: 解析 grid 总数、turnpage、搜索结果、详情字段。
- `workflows/add_search.py`: 从 CSV/抽样 Excel 补齐期刊文献数量。
- `workflows/journal_sync.py`: 把 CSV 期刊同步到后端任务队列。
- `workflows/detail_fetch.py`: 串行从后端任务队列抓取列表和详情并回写文献。
- `workflows/detail_fetch_threaded.py`: 单页内并发抓详情，每个线程独立 CNKI session。

## 服务端行为

- `/api/v1/search` 使用全局 `search_lock` 串行访问 CNKI grid，避免同一 session 并发污染。
- `/api/v1/detail` 使用全局 `detail_lock` 串行抓详情，详情默认 `prefer_curl=True`。
- `/api/v1/download` 使用 `download_lock` 包住 `cnki2.ettsg` session，失败后会重新初始化并再试一次。
- `TurnpageCache` 按 `expert` 缓存 `turnpage`，TTL 默认 1 小时，最大 500 个 expert。
- `after_request` 会给每次受保护 API 写访问日志；即使业务失败，只要通过了路由动作识别也会记录。

## 鉴权和数据库

启动后首次管理/API 访问会自动创建数据库和以下表：

- `cnki_api_plans`
- `cnki_api_keys`
- `cnki_api_usage_counters`
- `cnki_api_access_logs`

`authenticate_and_consume` 会在同一事务内：

1. 读取 API Key 和套餐。
2. 校验 key 状态、过期时间、套餐状态、接口限额。
3. 用 `INSERT ... ON DUPLICATE KEY UPDATE` 消耗当前窗口额度。
4. 更新 `cnki_api_keys.last_used_at`。

如果同一业务改动继续维护这段代码，优先把同表/同主记录的写入合并为一次 SQL 或一次事务内的清晰步骤。确实不能合并时，按项目要求加中文注释说明时点差异、并发影响和不能合并的原因。

## 搜索和详情解析

grid 请求依赖旧项目的 `cnki2.utils.gridQueryStr` 拼查询参数。解析结果中的关键字段：

- `url0`: 详情页地址，后续传给 `/api/v1/detail`。
- `new_url`: 下载入口，后续传给 `/api/v1/download`。
- `data_filename` / `data_dbname`: 下载和去重关键字段。
- `database`: 区分期刊类型，详情解析外文期刊时会走特殊分支。

详情解析会把 `.rowtit`、作者、机构等字段整理到 `infoData`，并单独提取 `abstractInfo`、`keywords`、`doi`。如果 HTML 是安全验证页或主体为空，抛出获取详情失败。

## CSV 补数

`add_search.py` 支持两种模式：

- `fill`: 对 CSV 中数量为空的期刊调用 CNKI 查询总数，并写回 CSV。
- `sum200`: 只统计抽样 Excel 和 CSV 的匹配、已有数量、缺失数量，不请求 CNKI。

默认日期范围是 `2022-01-01` 到 `2024-12-31`。批量补数时复用同一个 `CnkiClient`，避免每本期刊都重新预热 session。

## 期刊同步

`journal_sync.py` 的目标是把期刊任务写入后端 `/cnki/journal/list/put`，不是直接抓详情。

关键规则：

- 按 “刊名 + 时间区间” 调 `/cnki/journal/list/countByJournalName` 做幂等判断。
- `total <= 6000` 时直接入队。
- `total > 6000` 时递归二分日期区间，直到每段数量不超过 6000。
- 顶层和子区间都做存在性判断，防止部分区间已经同步时重复入库。

## 文献抓取

`detail_fetch.py` 主循环：

1. 从 `/cnki/journal/list/get` 领取待处理期刊。
2. 按 grid 页抓搜索结果，解析 `turnpage` 和 `total`。
3. 每条文献先用 `/cnkiLiterature/getByAccessionNo` 判断是否已存在。
4. 不存在时抓详情并调用 `/cnkiLiterature/wosSave11` 保存。
5. 页码推进后调用 `/cnki/journal/list/put` 回写当前期刊进度。

翻页策略保留旧逻辑：如果目标页 `to_page_num` 大于当前页加 5，则下一页跳到 `current_page + 5`，否则加 1。

`detail_fetch_threaded.py` 在单页内用 `ThreadPoolExecutor` 并发处理详情，每个工作线程通过 `ThreadClientManager` 维护自己的 `CnkiClient`。主线程仍串行拉 grid 列表。并发数默认 `5`，可用环境变量 `CNKI_DETAIL_MAX_WORKERS` 调整。

## 常见维护判断

- 搜索请求更轻，可用普通 `requests`；详情页更容易受 TLS/指纹影响，优先用 `curl_cffi`。
- 遇到 CNKI 安全验证页时刷新 session，再由外层重试当前期刊或标记失败。
- 后端队列请求使用无限重试，适配后端短暂重启；CNKI session 获取使用有限重试，失败后跳过或标记任务失败。
- 下载链路依赖 `cnki2.ettsg` 的全局 session 和默认下载目录，修改时注意全局状态和并发锁。
