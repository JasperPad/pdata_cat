# PS5 HK Scraper 🎮

> PlayStation Store 港服图片链接采集工具 — 提取 PS5 游戏的完整图片资源链接（封面、截图、横幅、Logo 等）

**版本**: v1.0.0 | **测试**: ✅ 188/188 通过 | **License**: MIT

---

## 📌 核心特性

| 特性 | 说明 |
|------|------|
| 🖼️ **9 种图片角色** | MASTER / GAMEHUB_COVER_ART / BANNER×2 / LOGO / SCREENSHOT×N / EDITION_KEY_ART / BACKGROUND / PREVIEW |
| 💰 **价格数据** | 原价、折扣价、折扣百分比、PS Plus 会员加折 |
| 🗄️ **SQLite 持久化** | WAL 模式 + 自动 Schema 迁移 + 级联删除 |
| ⚡ **并发采集** | ThreadPoolExecutor + Semaphore 限速控制 |
| 🔄 **断点续采** | SQLite 进度跟踪，中断后可从断点恢复 |
| 🛠️ **CLI 工具** | collect / export / status / images 四个命令 |
| 🔒 **安全审计通过** | 0 安全问题 + 独立评审 23 项全修复 |

---

## 🏗️ 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI (Typer)                          │
│   collect │ export │ status │ images                         │
└───────────┬───────────────┬───────────┬─────────────────────┘
            │               │           │
    ┌───────▼───────┐       │     ┌─────▼──────┐
    │  Pipeline     │       │     │ Repository │
    │  (编排层)      │       │     │  (CRUD)    │
    └───────┬───────┘       │     └─────┬──────┘
            │               │           │
    ┌───────▼───────┐       │     ┌─────▼──────┐
    │  Concurrent   │       │     │ Database   │
    │  Collector    │───────┼────▶│ Manager    │
    │  (并发采集)    │       │     │  (WAL)     │
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

# 2️⃣ 开始采集所有 PS5 港服游戏图片链接
ps5-scraper collect --workers 4

# 3️⃣ 导出为 JSON
ps5-scraper export --output games.json
```

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
| `locale` | `PS5_LOCALE` | str | `zh-hant-hk` | 地区语言代码 |

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

**示例：**

```bash
# 标准采集（4 线程）
ps5-scraper collect

# 高并发采集
ps5-scraper collect --workers 8

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

**示例：**

```bash
# 导出为 JSON
ps5-scraper export -o my_games.json

# 导出含图片的完整数据
ps5-scraper export --with-images
```

### `status` — 查看状态

```bash
ps5-scraper status [OPTIONS]
```

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--verbose` | `-v` | flag | `false` | 显示详细信息 |

**输出示例：**
```
📊 Collection Status
═══════════════════════════════════════
  Total Games:    7,047
  Collected:      3,252 (46.2%)
  Remaining:      3,795
  Last Page:      163
  Images Total:   48,934
  DB Size:        12.4 MB
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

**示例：**

```bash
# 查看 God of War 的所有图片
ps5-scraper images "God of War"

# 只看封面图
ps5-scraper images "Spider-Man" --role MASTER

# JSON 输出
ps5-scraper images "Horizon" --json
```

---

## 📂 项目结构

```
ps5-hk-scraper/
├── docs/                       # 📝 文档
│   ├── README.md              # 本文件 — 用户指南
│   ├── api.md                 # 开发者参考
│   ├── CHANGELOG.md           # 变更日志
│   └── WORKLOG.md             # 工作日志
├── src/ps5_scraper/            # 🔧 源码
│   ├── __init__.py            # 版本号 v1.0.0
│   ├── cli.py                 # Typer CLI 入口
│   ├── config.py              # Pydantic Settings
│   ├── api/                   # API 层
│   │   ├── base.py            # BaseAPIClient
│   │   ├── psstore_client.py  # PS Store 客户端
│   │   └── psstore_parser.py  # 响应解析器 ⭐
│   ├── models/                # 数据模型
│   │   └── game.py            # Pydantic v2 模型
│   ├── storage/               # 存储层
│   │   ├── database.py        # DatabaseManager
│   │   └── repositories.py    # GameRepository
│   └── collectors/            # 采集层
│       ├── concurrent.py      # ConcurrentCollector
│       ├── progress.py        # ProgressTracker
│       └── pipelines.py       # CollectionPipeline
├── tests/                      # 🧪 测试
│   ├── test_models.py
│   ├── test_api/
│   ├── test_storage/
│   ├── test_collectors/
│   └── conftest.py
├── config.yaml                 # 配置文件
├── pyproject.toml              # 项目元数据
└── README.md                   # 项目首页
```

---

## 🧪 测试

```bash
# 运行全部测试
pytest

# 运行带覆盖率
pytest --cov=ps5_scraper --cov-report=term-missing

# 运行特定模块测试
pytest tests/test_models.py -v

# 当前结果: 188 passed, 0 failed ✅
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
