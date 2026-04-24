# PS5 Store Scraper 🎮

> PlayStation Store **多区域**图片链接采集工具 — 提取 PS5 游戏的完整图片资源链接（封面、截图、横幅、Logo 等），支持 21 个 PS Store 区域

**版本**: v2.0.0 | **测试**: ✅ 232/232 通过 | **License**: MIT

---

## 📌 核心特性

| 特性 | 说明 |
|------|------|
| 🌍 **21 区域支持** | HK/US/JP/UK/DE/KR/TW/BR/CN 等 21 个 PS Store 区域 |
| 🖼️ **9 种图片角色** | MASTER / GAMEHUB_COVER_ART / BANNER×2 / LOGO / SCREENSHOT×N / EDITION_KEY_ART / BACKGROUND / PREVIEW |
| 💰 **价格数据** | 原价、折扣价、折扣百分比、PS Plus 会员加折，自动适配各区域货币 |
| 🗄️ **SQLite 持久化** | WAL 模式 + Schema v2 自动迁移 + region 分区索引 |
| ⚡ **并发采集** | ThreadPoolExecutor + Semaphore 限速控制 |
| 🔄 **断点续采** | SQLite 进度跟踪，中断后可从断点恢复 |
| 🛠️ **CLI 工具** | collect / export / status / images 四命令 + `--region` / `--all-regions` 参数 |
| 🔒 **安全审计通过** | 0 安全问题 + 独立评审 14 项全修复 |

---

## 🏗️ 架构图 (v2.0 多区域)

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                          │
│   collect [--region XX] │ export │ status │ images          │
│   --all-regions                                                 │
└───────────┬───────────────┬───────────┬─────────────────────┘
            │               │           │
    ┌───────▼───────┐       │     ┌─────▼──────┐
    │  Pipeline     │       │     │ Repository │
    │  (多区域编排)   │       │     │  (CRUD+区域) │
    └───────┬───────┘       │     └─────┬──────┘
            │               │           │
    ┌───────▼───────┐       │     ┌─────▼──────┐
    │  Concurrent   │       │     │ Database   │
    │  Collector    │───────┼────▶│ Manager    │
    │  (并发采集)    │       │     │  (Schema v2)│
    └───────┬───────┘       │     └────────────┘
            │               │
    ┌───────▼───────┐       │
    │  Progress     │       │
    │  Tracker      │       │
    │  (断点续采)    │       │
    └───────┬───────┘       │
            │               │
    ┌───────▼───────────────▼───┐
    │        PS Store Client     │
    │  BaseAPIClient (限速+重试)  │
    │  PSStoreClient (GraphQL)   │
    │  ├─ locale: {region.locale}│
    │  └─ currency: {region.currency}│
    │  PSStoreParser (解析+提取)  │
    └───────────┬────────────────┘
                │
        ────────▼────────
         PS Store GraphQL API
         https://web.np.playstation.com/api/graphql/v1/op
```

---

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone <repo-url>
cd ps5-hk-scraper

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .
```

### 三步使用

```bash
# 1️⃣ 查看当前状态（首次使用会自动初始化数据库）
ps5-scraper status

# 2️⃣ 采集指定区域（默认港服）
ps5-scraper collect --workers 4

# 3️⃣ 导出为 JSON
ps5-scraper export --output games.json
```

### 多区域采集

```bash
# 采集美服
ps5-scraper collect --region US

# 采集日服
ps5-scraper collect --region JP

# 采集所有启用区域
ps5-scraper collect --all-regions

# 全量重采所有区域
ps5-scraper collect --all-regions --full
```

### 支持的区域代码

| 代码 | 区域 | 货币 | 游戏数(约) |
|------|------|------|-----------|
| US | 🇺🇸 美服 | USD | ~9,149 |
| JP | 🇯🇵 日服 | JPY | ~7,370 |
| HK | 🇭🇰 港服 | HKD | ~7,048 |
| UK | 🇬🇧 英服 | GBP | ~7,200 |
| DE | 🇩🇪 德服 | EUR | ~7,150 |
| KR | 🇰🇷 韩服 | KRW | ~6,481 |
| TW | 🇹🇼 台服 | TWD | ~6,108 |
| BR | 🇧🇷 巴西服 | BRL | ~4,500 |
| CN | 🇨🇳 国服 | CNY | ~35 |
| ... | 共 21 个区域 | — | — |

> 完整列表见 `src/ps5_scraper/models/region.py` 中 `REGIONS` 字典。

### 查看某游戏的图片

```bash
ps5-scraper images "God of War Ragnarök"
```

---

## ⚙️ 配置参考

配置文件路径: `config.yaml`（项目根目录）或环境变量覆盖。

| 配置字段 | 环境变量 | 类型 | 默认值 | 说明 |
|----------|----------|------|--------|------|
| `api.base_url` | `PS5_API_BASE_URL` | str | `https://web.np.playstation.com/api/graphql/v1/op` | PS Store GraphQL 端点 |
| `api.timeout` | `PS5_API_TIMEOUT` | int | `30` | HTTP 请求超时(秒) |
| `api.max_retries` | `PS5_MAX_RETRIES` | int | `3` | 最大重试次数 |
| `api.retry_delay` | `PS5_RETRY_DELAY` | float | `1.0` | 重试基础延迟(秒) |
| `api.rate_limit_rpm` | `PS5_RATE_LIMIT_RPM` | int | `60` | 每分钟最大请求数 |
| `collector.workers` | `PS5_WORKERS` | int | `4` | 并发线程数 |
| `collector.page_size` | `PS5_PAGE_SIZE` | int | `20` | 每页游戏数量 |
| `storage.db_path` | `PS5_DB_PATH` | str | `data/games.db` | SQLite 数据库路径 |
| `locale` | `PS5_LOCALE` | str | `zh-hant-hk` | 地区语言代码（默认港服） |

### config.yaml 示例

```yaml
api:
  base_url: "https://web.np.playstation.com/api/graphql/v1/op"
  timeout: 30
  max_retries: 3
  retry_delay: 1.0
  rate_limit_rpm: 60

collector:
  workers: 4
  page_size: 20

storage:
  db_path: "data/games.db"

locale: "zh-hant-hk"
```

---

## 📋 CLI 命令参考

### `collect` — 采集游戏数据

```bash
ps5-scraper collect [OPTIONS]
```

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--workers` | `-w` | int | `4` | 并发线程数 |
| `--page-size` | `-p` | int | `20` | 每页数量 |
| `--resume` | `-r` | flag | `false` | 从上次中断处继续 |
| `--dry-run` | flag | `false` | 仅显示计划不执行 |
| `--full` | flag | `false` | 全量重采（忽略进度） |
| `--region` | str | `HK` | 指定区域代码（大小写不敏感） |
| `--all-regions` | flag | `false` | 采集所有启用区域 |

**示例：**

```bash
# 标准采集港服（4 线程）
ps5-scraper collect

# 采集美服
ps5-scraper collect --region US

# 采集日服全量
ps5-scraper collect --region JP --full

# 多区域高并发采集
ps5-scraper collect --all-regions --workers 4

# 断点续采
ps5-scraper collect --resume

# 预览模式（不实际请求 API）
ps5-scraper collect --dry-run
```

### `export` — 导出数据

```bash
ps5-scraper export [OPTIONS]
```

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--output` | `-o` | str | `games.json` | 输出文件路径 |
| `--format` | `-f` | str | `json` | 导出格式 (json/csv) |
| `--with-images` | flag | `false` | 包含图片链接详情 |
| `--region` | str | _(全部)_ | 按区域过滤导出 |

### `status` — 查看状态

```bash
ps5-scraper status [OPTIONS]
```

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--verbose` | `-v` | flag | `false` | 显示详细信息 |

**输出示例：**
```
📊 PS5 数据库状态
═══════════════════════════════════════
  Total Games:    15,234
  Regions:        3 (HK, US, JP)
  Images Total:   229,456
  DB Size:        45.2 MB
```

### `images` — 查看游戏图片

```bash
ps5-scraper images GAME_NAME [OPTIONS]
```

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `GAME_NAME` | positional | str | _(必填)_ | 游戏名称（支持模糊搜索） |
| `--role` | `-r` | str | `all` | 过滤图片角色 |
| `--json` | flag | `false` | JSON 格式输出 |

---

## 📂 项目结构 (v2.0)

```
ps5-hk-scraper/
├── docs/                              # 📝 文档
│   ├── README.md                      # 本文件 — 用户指南
│   ├── api.md                         # 开发者参考
│   ├── CHANGELOG.md                   # 变更日志
│   ├── WORKLOG.md                     # 工作日志
│   ├── MULTI_REGION_RESEARCH_REPORT.md # 多区域调研报告
│   └── V2_MULTI_REGION_ARCHITECTURE.md # 架构设计文档
├── src/ps5_scraper/                    # 🔧 源码
│   ├── __init__.py                   # 版本号
│   ├── cli.py                        # Typer CLI 入口 (多区域参数)
│   ├── config.py                     # Pydantic Settings (多区域工厂方法)
│   ├── models/                       # 数据模型
│   │   ├── __init__.py              # 统一导出
│   │   ├── game.py                  # Game/GamePrice/GameImage 模型 (+region)
│   │   └── region.py               # ⭐ Region 模型 + 21 区域定义
│   ├── api/                          # API 层
│   │   ├── base.py                  # BaseAPIClient
│   │   ├── psstore_client.py        # PS Store 客户端 (+currency参数)
│   │   └── psstore_parser.py        # 响应解析器 (+region注入)
│   ├── storage/                      # 存储层
│   │   ├── database.py              # DatabaseManager (Schema v2)
│   │   └── repositories.py          # GameRepository (region分区CRUD)
│   └── collectors/                   # 采集层
│       ├── concurrent.py             # ConcurrentCollector (region传递)
│       ├── progress.py              # ProgressTracker
│       └── pipelines.py             # CollectionPipeline (多区域编排)
├── tests/                             # 🧪 测试 (232 个用例)
│   ├── unit/
│   │   ├── test_models.py           # Game 模型测试 (+region)
│   │   ├── test_region_model.py     # ⭐ Region 模型测试 (21 用例)
│   │   ├── test_config.py           # Config 测试 (+多区域工厂)
│   │   ├── test_psstore_client.py   # Client 测试 (+currency)
│   │   ├── test_database.py         # DB 测试 (Schema v2 迁移)
│   │   ├── test_repositories.py     # Repo 测试 (region CRUD)
│   │   ├── test_psstore_parser.py   # Parser 测试 (+region注入)
│   │   ├── test_concurrent_collector.py # Collector 测试 (region传递)
│   │   ├── test_pipeline.py         # Pipeline 测试 (多区域编排)
│   │   └── test_cli.py              # CLI 测试 (--region/--all-regions)
├── config.yaml                        # 配置文件
├── pyproject.toml                     # 项目元数据
└── README.md                          # 项目首页
```

---

## 🧪 测试

```bash
# 运行全部测试
pytest

# 运行带覆盖率
pytest --cov=ps5_scraper --cov-report=term-missing

# 运行特定模块测试
pytest tests/unit/test_region_model.py -v

# 当前结果: 232 passed, 0 failed ✅
```

---

## ⚠️ 安全注意事项

### Hash 轮换风险

> PS Store API 使用 **GraphQL Persisted Queries**，请求中包含一个 `hash` 字段标识查询。
> 该 hash 可能定期轮换（通常数周至数月），一旦轮换将导致 API 返回错误。

- 工具会检测 hash 失效并抛出 `PSStoreHashExpiredError`
- 遇到该错误时需要更新 `psstore_client.py` 中的 hash 值
- 建议关注项目 Issues 获取更新通知

### CSRF / Rate Limiting

- 内置 **Rate Limiter**: 60 RPM（每分钟 60 次请求）默认限制
- 自动 **Exponential Backoff**: 重试间隔递增避免触发封禁
- 请勿擅自提高 `rate_limit_rpm`，可能导致 IP 被 Sony 封禁
- **多区域采集时注意总 QPS 控制**

### 数据安全

- 本地 SQLite 存储，**无外部数据传输**
- 无需登录凭证或 API Key
- 数据库文件权限建议设为 `600`

### 合规使用

- 仅用于个人学习和研究目的
- 请遵守 Sony PlayStation Network 服务条款
- 不要用于商业用途或大规模自动化爬取

---

## 📄 License

MIT License © 2026

详见 [LICENSE](../LICENSE) 文件。
