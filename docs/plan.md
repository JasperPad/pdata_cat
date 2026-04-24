# PS5 港服数据采集器 (ps5-hk-scraper) 实现计划

> **版本**: v1.0.0
> **日期**: 2026-04-24
> **状态**: 开发中
> **目标**: 采集 PS5 港服游戏数据，**优先抓取图片链接**（不下载图片文件），存入 SQLite 持久化

---

## 项目目标

从 PlayStation Store Hong Kong（港服）官方 GraphQL API 采集 PS5 游戏的：
1. **基本信息** — 名称、ID、类型、发行商、发售日期、评分、年龄分级
2. **价格/折扣** — 原价、折扣价、折扣百分比、是否免费、会员加折
3. **图片链接** — 封面图(MASTER)、详情主图(GAMEHUB_COVER_ART)、横幅(FOUR_BY_THREE_BANNER)、竖版海报(PORTRAIT_BANNER)、Logo、实机截图(SCREENSHOT) ×N
4. **分类/标签** — 类型(genre)、平台(platforms)、游戏类型(classification)

> ⚠️ **v1.0 范围**: 仅抓取图片 CDN 链接并存储，**不下载图片文件**。后续版本支持批量下载。

---

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│                    CLI (Typer + Rich)                │
│         ps5-scraper collect / export / status        │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Collector Pipeline                      │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────┐  │
│  │ Concurrent   │→ │ Progress      │→ │ Image    │  │
│  │ Collector     │  │ Tracker       │  │ Link     │  │
│  │ (线程池+信号量) │  │ (断点续采)     │  │ Extractor│  │
│  └──────────────┘  └───────────────┘  └──────────┘  │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              API Layer                               │
│  ┌──────────────────────────────────────────────┐   │
│  │ PSStoreGraphQLClient                          │   │
│  │ - categoryGridRetrieve (列表分页)              │   │
│  │ - 内置限速 + 重试 + CSRF 绕过                  │   │
│  └──────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────┐   │
│  │ PSStoreParser                                 │   │
│  │ - 响应解析 → Pydantic 模型                    │   │
│  │ - 图片链接提取与标准化                        │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│              Storage Layer                           │
│  ┌──────────────┐  ┌───────────────┐                │
│  │ DatabaseMgr  │  │ Repository    │                │
│  │ (SQLite WAL) │  │ (CRUD)        │                │
│  └──────────────┘  └───────────────┘                │
└─────────────────────────────────────────────────────┘
```

---

## 模块职责表

| 模块 | 文件 | 职责 |
|------|------|------|
| Models | `models/game.py` | Pydantic 数据模型：Game, GamePrice, GameImage, CategoryResponse |
| API Base | `api/base.py` | 基础 HTTP 客户端：限速、重试、错误处理 |
| API Client | `api/psstore_client.py` | PlayStation Store GraphQL API 调用封装 |
| Parser | `api/psstore_parser.py` | GraphQL 响应 → Pydantic 模型转换 + 图片链接提取 |
| Config | `config.py` | YAML 配置加载 + 环境变量覆盖 |
| Storage DB | `storage/database.py` | SQLite 连接管理 + Schema 定义 + 自动迁移 |
| Storage Repo | `storage/repositories.py` | CRUD 操作：upsert game / query images |
| Collector | `collectors/concurrent.py` | 并发采集引擎（ThreadPoolExecutor + Semaphore） |
| Collector | `collectors/progress.py` | 进度持久化（断点续采） |
| Collector | `collectors/pipelines.py` | 采集管道编排：fetch → parse → store |
| CLI | `cli.py` | Typer CLI 入口：collect/export/status |

---

## 数据模型定义

### Game（核心模型）

```python
class Game(BaseModel):
    """PS5 港服游戏."""
    id: str                              # 产品 ID: HP9000-PPSA13198_00-XXXXXXXXX
    name: str                            # 游戏标题（繁体中文）
    platforms: list[str]                 # ["PS5"] 或 ["PS4", "PS5"]
    classification: str                  # 正式版遊戲 / DLC / 遊戲組合包 / 高級版
    release_date: str = ""               # 发售日期 YYYY-MM-DD
    provider_name: str = ""              # 发行商
    top_genre: str = ""                  # 主类型
    age_rating_label: str = ""           # 年龄分级
    star_rating_score: float = 0.0       # 评分 (0-5)
    star_rating_total: int = 0           # 评价人数
    price: GamePrice | None = None       # 价格信息
    images: list[GameImage] = []         # 图片链接列表（v1.0 核心）
    sku_count: int = 0                   # SKU 数量
    last_updated: int = 0                # Unix timestamp
```

### GamePrice（价格模型）

```python
class GamePrice(BaseModel):
    base_price: str = ""          # "HK$708.00"
    discounted_price: str = ""    # "HK$389.40"
    discount_text: str = ""       # "-45%"
    is_free: bool = False
    is_exclusive: bool = False
    service_branding: list[str] = []
    upsell_text: str = ""
```

### GameImage（图片模型 — v1.0 核心）

```python
class GameImage(BaseModel):
    role: str                     # MASTER / GAMEHUB_COVER_ART / FOUR_BY_THREE_BANNER /
                                  # PORTRAIT_BANNER / LOGO / SCREENSHOT /
                                  # EDITION_KEY_ART / BACKGROUND / PREVIEW
    type: str                     # IMAGE 或 VIDEO
    url: str                      # CDN 直链 URL
    width: int | None = None      # 图片宽度（可选）
    height: int | None = None     # 图片高度（可选）
```

---

## SQLite Schema 设计

```sql
CREATE TABLE games (
    id TEXT PRIMARY KEY,                   -- 产品 ID
    name TEXT NOT NULL,
    platforms TEXT DEFAULT '[]',            -- JSON array
    classification TEXT DEFAULT '',
    release_date TEXT DEFAULT '',
    provider_name TEXT DEFAULT '',
    top_genre TEXT DEFAULT '',
    age_rating_label TEXT DEFAULT '',
    star_rating_score REAL DEFAULT 0.0,
    star_rating_total INTEGER DEFAULT 0,
    -- 价格字段
    base_price TEXT DEFAULT '',
    discounted_price TEXT DEFAULT '',
    discount_text TEXT DEFAULT '',
    is_free INTEGER DEFAULT 0,
    is_exclusive INTEGER DEFAULT 0,
    service_branding TEXT DEFAULT '[]',
    upsell_text TEXT DEFAULT '',
    -- 元数据
    sku_count INTEGER DEFAULT 0,
    last_updated INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE game_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                     -- MASTER / SCREENSHOT / ...
    image_type TEXT NOT NULL,               -- IMAGE / VIDEO
    url TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    UNIQUE(game_id, role, url)              -- 防重复
);

CREATE INDEX idx_game_images_game_id ON game_images(game_id);
CREATE INDEX idx_games_last_updated ON games(last_updated);
CREATE INDEX idx_games_classification ON games(classification);
```

Schema Version: 1（初始版本）

---

## 技术决策记录 (ADR)

### ADR-001: 使用 httpx 同步客户端而非异步

**决策**: v1.0 使用 httpx 同步 Client。
**理由**:
- 并发通过 ThreadPoolExecutor 实现（复用 steam-cn-scraper 成熟方案）
- 同步代码更易调试和测试
- 后续可升级为 async 如需更高吞吐

### ADR-002: 仅抓图片链接，不下载文件

**决策**: v1.0 只存储 CDN URL，不下载图片到本地。
**理由**:
- 用户明确要求"先抓图片链接，以后再抓图片"
- 减少存储和网络开销
- URL 可随时用于后续批量下载
- 图片链接本身是结构化数据的一部分

### ADR-003: CSRF 绕过策略 — 浏览器环境 fetch()

**决策**: 通过模拟浏览器 headers 绕过 Sony 的 CSRF 防护。
**实现**:
- 设置正确的 headers: `x-psn-store-locale-override`, `x-apollo-operation-name`
- Content-Type: application/json
- User-Agent 模拟浏览器
- 如果仍被拦截，备选方案：Playwright 无头浏览器

### ADR-004: Hash 签名硬编码 + 过期检测

**决策**: sha256Hash 硬编码在配置中，API 调用时检测返回是否包含错误。
**缓解**:
- 列表接口 Hash 已实测有效
- 返回 `"Unknown operation"` 时抛出明确异常
- 提供命令行工具手动更新 Hash

---

## 外部依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| httpx | ≥0.27.0 | HTTP 客户端（替代 requests） |
| pydantic | ≥2.5.0 | 数据验证和序列化 |
| typer | ≥0.9.0 | CLI 框架 |
| rich | ≥13.0.0 | 终端美化输出 |
| pyyaml | ≥6.0 | 配置文件解析 |

### 外部 API

| API | 端点 | 认证 |
|-----|------|------|
| PS Store GraphQL | https://web.np.playstation.com/api/graphql/v1/op | 无需登录 |

---

## 测试策略

### 单元测试 (tests/unit/)
- **Models**: Pydantic 模型验证（合法/非法数据）
- **Parser**: JSON → Model 转换（各种边界情况）
- **Storage**: CRUD 操作、Schema 迁移
- **Config**: YAML 加载、环境变量覆盖

### 集成测试 (tests/integration/)
- **API Client**: 使用 respx mock HTTP 响应
- **Pipeline**: 端到端流程（mock API → parse → store）

### 测试工具
- pytest + pytest-cov（覆盖率 ≥80%）
- respx（HTTP mocking）
- pytest-asyncio（async 支持）

---

## 开发任务分解

### Batch 1: 核心基础设施 (TDD)
1. [x] 项目脚手架 + pyproject.toml
2. [ ] Models — Game / GamePrice / GameImage
3. [ ] API Base — BaseAPIClient (限速+重试)
4. [ ] PSStore Client — GraphQL 调用封装
5. [ ] PSStore Parser — 响应解析 + 图片链接提取
6. [ ] Storage — Database Manager + Schema
7. [ ] Storage — Repository (CRUD)

### Batch 2: 功能层 (TDD)
8. [ ] Config — YAML 配置
9. [ ] Concurrent Collector — 并发引擎
10. [ ] Progress Tracker — 断点续采
11. [ ] Pipeline — 采集编排
12. [ ] CLI — Typer 应用入口

### Batch 3: 审计 + 文档
13. [ ] 安全扫描
14. [ ] 独立代码评审
15. [ ] 自动修复
16. [ ] README + API 文档 + CHANGELOG + WORKLOG
17. [ ] 最终验证

---

## Git 规范

使用 Conventional Commits:
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档变更
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具链
