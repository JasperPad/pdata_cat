# PS5 HK Scraper — 开发者参考 (API Reference)

> 数据模型、接口签名、异常层级与代码示例

**版本**: v1.0.0 | **最后更新**: 2026-04-24

---

## 目录

- [数据模型](#数据模型)
  - [Game](#game)
  - [GamePrice](#gameprice)
  - [GameImage](#gameimage)
  - [CategoryResponse](#categoryresponse)
- [API Client 层](#api-client-层)
  - [BaseAPIClient](#baseapiclient)
  - [PSStoreClient](#psstoreclient)
  - [PSStoreParser](#psstoreparser)
- [Storage 层](#storage-层)
  - [DatabaseManager](#databasemanager)
  - [GameRepository](#gamerepository)
- [Collector 层](#collector-层)
  - [ConcurrentCollector](#concurrentcollector)
  - [ProgressTracker](#progresstracker)
  - [CollectionPipeline](#collectionpipeline)
- [CLI 命令参数表](#cli-命令参数表)
- [异常层级](#异常层级)

---

## 数据模型

所有模型基于 **Pydantic v2 BaseModel**，支持序列化/反序列化、字段校验。

### Game

游戏主实体，包含基本信息、价格和图片列表。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| `id` | `str` | ✅ | — | 游戏唯一 ID（Sony 内部 ID，如 `hp00000000001`） |
| `name` | `str` | ✅ | — | 游戏名称 |
| `locale` | `str` | ✅ | `"zh-hant-hk"` | 地区语言代码 |
| `platform` | `str` | ✅ | `"ps5"` | 平台标识 |
| `price` | `GamePrice \| None` | ❌ | `None` | 价格信息 |
| `images` | `list[GameImage]` | ❌ | `[]` | 图片链接列表 |
| `url` | `str \| None` | ❌ | `None` | PS Store 商品页 URL |
| `description` | `str \| None` | ❌ | `None` | 游戏简介 |
| `provider` | `str` | ❌ | `"ps-store"` | 数据来源 |
| `collected_at` | `datetime` | ❌ | _(auto)_ | 采集时间戳（自动生成） |

**示例：**

```python
from ps5_scraper.models.game import Game, GamePrice, GameImage

game = Game(
    id="hp00000000001",
    name="God of War Ragnarök",
    locale="zh-hant-hk",
    platform="ps5",
    price=GamePrice(
        base_price=468.00,
        discount_price=234.00,
        discount_percentage=50,
        plus_price=None,
        currency="HKD"
    ),
    images=[
        GameImage(role="MASTER", url="https://.../master.png", width=1280, height=720),
        GameImage(role="SCREENSHOT", url="https://.../ss01.jpg", width=1920, height=1080),
    ]
)

# 序列化为 dict / JSON
print(game.model_dump())
print(game.model_dump_json())
```

---

### GamePrice

价格信息模型。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| `base_price` | `float \| None` | ❌ | `None` | 原价（港币） |
| `discount_price` | `float \| None` | ❌ | `None` | 折后价 |
| `discount_percentage` | `int \| None` | ❌ | `None` | 折扣百分比 (0-100) |
| `plus_price` | `float \| None` | ❌ | `None` | PS Plus 会员价 |
| `currency` | `str` | ❌ | `"HKD"` | 货币代码 |

---

### GameImage

图片资源模型。每张图片有一个 **角色 (role)** 标识其用途。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| `role` | `str` | ✅ | — | 图片角色（见下方枚举） |
| `url` | `str` | ✅ | — | 图片完整 URL |
| `width` | `int \| None` | ❌ | `None` | 宽度 (px) |
| `height` | `int \| None` | ❌ | `None` | 高度 (px) |
| `format` | `str \| None` | ❌ | _(推断)_ | 文件格式 (png/jpg/mp4) |
| `position` | `int \| None` | ❌ | `None` | 排序位置（同角色多图时使用） |

#### 图片角色 (role) 枚举

| Role | 用途 | 典型尺寸 | 数量 |
|------|------|----------|:----:|
| `MASTER` | 首页封面缩略图 | ~386×217 | 1 |
| `GAMEHUB_COVER_ART` | 详情页主封面大图 | ~1280×720 | 1 |
| `FOUR_BY_THREE_BANNER` | 横幅 (4:3) | ~960×720 | 1 |
| `PORTRAIT_BANNER` | 竖版海报 | ~720×1280 | 1 |
| `LOGO` | 游戏标志 | 不定 | 1 |
| `SCREENSHOT` | 实机截图 | ~1920×1080 | N |
| `EDITION_KEY_ART` | 版本封面（如 Deluxe/GOTY） | 不定 | N |
| `BACKGROUND` | 详情页背景大图 | ~1920×1080 | 1 |
| `PREVIEW` | 预告视频 MP4 | 不定 | N |

```python
from ps5_scraper.models.game import ImageRole

# 筛选特定角色的图片
covers = [img for img in game.images if img.role == "MASTER"]
screenshots = [img for img in game.images if img.role == "SCREENSHOT"]
```

---

### CategoryResponse

分类列表响应（分页容器）。

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| `total_count` | `int` | ✅ | — | 该分类下游戏总数 |
| `page_offset` | `int` | ✅ | `0` | 当前页偏移量 |
| `page_size` | `int` | ✅ | `20` | 每页数量 |
| `games` | `list[Game]` | ✅ | `[]` | 当前页的游戏列表 |
| `has_more` | `bool` | ✅ | _(计算)_ | 是否有下一页 |

---

## API Client 层

### BaseAPIClient

基础 HTTP 客户端，提供限速和重试能力。

```python
class BaseAPIClient:
    """带限速和重试的 HTTP 客户端基类"""

    def __init__(
        self,
        base_url: str = ...,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit_rpm: int = 60,
    ): ...

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict: ...
    """发送 HTTP 请求，自动处理限速和重试"""

    async def get(self, endpoint: str, **kwargs) -> dict: ...
    async def post(self, endpoint: str, **kwargs) -> dict: ...

    async def close(self) -> None: ...
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc) -> None: ...
```

**使用示例：**

```python
import asyncio
from ps5_scraper.api.base import BaseAPIClient

async def example():
    async with BaseAPIClient(base_url="https://api.example.com") as client:
        result = await client.post("/graphql", json={"query": "..."})
        print(result)

asyncio.run(example())
```

#### 限速机制

- 使用 **令牌桶算法** 实现 RPM 限制
- 默认 60 RPM（即每秒最多 1 次）
- 超出限制时自动 `await` 直到可用

#### 重试策略

- 最大重试次数: `max_retries`（默认 3）
- 延迟策略: **Exponential Backoff** + Jitter
  - 第 1 次: `retry_delay * 1` 秒
  - 第 2 次: `retry_delay * 2` 秒
  - 第 3 次: `retry_delay * 4` 秒
- 仅对以下状态码重试: `429`, `500`, `502`, `503`, `504`

---

### PSStoreClient

PlayStation Store GraphQL API 客户端。

```python
class PSStoreClient(BaseAPIClient):
    """PS Store GraphQL API 客户端"""

    def __init__(self, settings: Settings | None = None): ...

    async def fetch_category_games(
        self,
        category_id: str,
        page_offset: int = 0,
        page_size: int = 20,
        locale: str = "zh-hant-hk",
    ) -> CategoryResponse: ...
    """获取指定分类下的游戏列表（分页）"""

    async def fetch_game_detail(self, game_id: str) -> Game: ...
    """获取单款游戏的详细信息"""
```

**使用示例：**

```python
import asyncio
from ps5_scraper.api.psstore_client import PSStoreClient

PS5_CATEGORY_ID = "4cbf39e2-5749-4970-ba81-93a489e4570c"

async def main():
    client = PSStoreClient()

    # 获取第一页 PS5 游戏
    response = await client.fetch_category_games(
        category_id=PS5_CATEGORY_ID,
        page_offset=0,
        page_size=20,
    )
    print(f"总计 {response.total_count} 款游戏")
    for game in response.games:
        print(f"  - {game.name} ({len(game.images)} 张图片)")

    await client.close()

asyncio.run(main())
```

#### GraphQL Persisted Queries

PS Store API 使用预编译的 GraphQL 查询，通过 hash 标识：

```python
# 内置的 persisted query hash
CATEGORY_GAMES_HASH = "a8b9e6c2d4f1..."  # 实际值在源码中
GAME_DETAIL_HASH = "b7c8d9e0f2a3..."
```

> ⚠️ Hash 可能轮换，失效时会抛出 `PSStoreHashExpiredError`

---

### PSStoreParser

GraphQL 响应解析器，负责从原始 JSON 中提取结构化数据。

```python
class PSStoreParser:
    """PS Store GraphQL 响应解析器"""

    @staticmethod
    def parse_category_response(data: dict) -> CategoryResponse: ...
    """解析分类列表响应"""

    @staticmethod
    def parse_game_detail(data: dict) -> Game: ...
    """解析游戏详情响应"""

    @staticmethod
    def extract_images(media_list: list) -> list[GameImage]: ...
    """从 media 列表中提取图片链接（核心方法）⭐"""

    @staticmethod
    def parse_price(price_data: dict) -> GamePrice | None: ...
    """解析价格数据"""
```

**图片提取逻辑（核心）：**

```python
from ps5_scraper.api.psstore_parser import PSStoreParser

# 输入: API 返回的原始 media 列表
raw_media = [
    {"role": "MASTER", "url": "https://...", "width": 1280, "height": 720},
    {"role": "SCREENSHOT", "url": "https://...", "width": 1920, "height": 1080},
    # ... 更多媒体项
]

images = PSStoreParser.extract_images(raw_media)
# => [GameImage(role='MASTER', ...), GameImage(role='SCREENSHOT', ...), ...]
```

**角色映射规则：**

| API 原始 role | 映射后 role | 处理逻辑 |
|---------------|-------------|----------|
| `master` | `MASTER` | 直接映射 |
| `gamehubCoverArt` | `GAMEHUB_COVER_ART` | camelCase → UPPER_SNAKE |
| `fourByThreeBanner` | `FOUR_BY_THREE_BANNER` | 同上 |
| `portraitBanner` | `PORTRAIT_BANNER` | 同上 |
| `logo` | `LOGO` | 同上 |
| `screenshot` | `SCREENSHOT` | 同上，多张时设置 position |
| `editionKeyArt` | `EDITION_KEY_ART` | 同上 |
| `background` | `BACKGROUND` | 同上 |
| `preview` | `PREVIEW` | 同上，format 设为 mp4 |

---

## Storage 层

### DatabaseManager

SQLite 数据库管理器，负责连接管理和 Schema 迁移。

```python
class DatabaseManager:
    """SQLite 数据库管理器（WAL 模式）"""

    def __init__(self, db_path: str = "data/games.db"): ...

    @property
    def connection(self) -> sqlite3.Connection: ...
    """获取数据库连接（线程安全）"""

    def initialize(self) -> None: ...
    """初始化数据库（创建表 + 启用 WAL）"""

    def migrate(self) -> list[str]: ...
    """执行 Schema 迁移，返回执行的 SQL 列表"""

    def close(self) -> None: ...
    """关闭数据库连接"""

    def __enter__(self) -> Self: ...
    def __exit__(self, *exc) -> None: ...
```

**Schema 定义：**

```sql
-- games 表
CREATE TABLE IF NOT EXISTS games (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    locale      TEXT NOT NULL DEFAULT 'zh-hant-hk',
    platform    TEXT NOT NULL DEFAULT 'ps5',
    url         TEXT,
    description TEXT,
    provider    TEXT NOT NULL DEFAULT 'ps-store',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 价格字段（内联以便查询）
    base_price          REAL,
    discount_price      REAL,
    discount_percentage INTEGER,
    plus_price          REAL,
    currency            TEXT DEFAULT 'HKD'
);

-- images 表
CREATE TABLE IF NOT EXISTS images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    url         TEXT NOT NULL,
    width       INTEGER,
    height      INTEGER,
    format      TEXT,
    position    INTEGER DEFAULT 0,
    UNIQUE(game_id, role, url, position)
);

-- progress 表（断点续采）
CREATE TABLE IF NOT EXISTS progress (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**WAL 模式优势：**
- 读写不阻塞（采集时可同时查询）
- 更好的并发性能
- 断电/崩溃时数据完整性更高

---

### GameRepository

游戏数据 CRUD 操作层。

```python
class GameRepository:
    """游戏数据仓库（CRUD + 图片管理）"""

    def __init__(self, db: DatabaseManager): ...

    # ── Game CRUD ──
    def upsert_game(self, game: Game) -> bool: ...
    """插入或更新游戏（按主键 id）"""

    def get_game(self, game_id: str) -> Game | None: ...
    """根据 ID 获取游戏"""

    def get_all_games(self, limit: int = 100, offset: int = 0) -> list[Game]: ...
    """获取游戏列表（分页）"""

    def search_games(self, query: str, limit: int = 20) -> list[Game]: ...
    """模糊搜索游戏名称"""

    def delete_game(self, game_id: str) -> bool: ...
    """删除游戏（级联删除关联图片）"""

    def count_games(self) -> int: ...
    """统计游戏总数"""

    # ── Image 管理 ──
    def get_game_images(self, game_id: str, role: str | None = None) -> list[GameImage]: ...
    """获取游戏图片，可按角色过滤"""

    def add_images(self, game_id: str, images: list[GameImage]) -> int: ...
    """批量添加图片（跳过已存在的）"""

    def delete_images(self, game_id: str, role: str | None = None) -> int: ...
    """删除图片，可按角色过滤"""

    def count_images(self, game_id: str | None = None) -> int: ...
    """统计图片数量"""

    # ── 批量操作 ──
    def export_all(self) -> list[dict]: ...
    """导出全部游戏为字典列表"""

    # ── 进度跟踪 ──
    def get_progress(self, key: str) -> str | None: ...
    def set_progress(self, key: str, value: str) -> None: ...
    def clear_progress(self, key: str) -> None: ...
```

**使用示例：**

```python
from ps5_scraper.config import Settings
from ps5_scraper.storage.database import DatabaseManager
from ps5_scraper.storage.repositories import GameRepository

settings = Settings()
db = DatabaseManager(settings.storage.db_path)
db.initialize()

repo = GameRepository(db)

# 插入游戏
repo.upsert_game(game)

# 搜索
results = repo.search_games("God of War")

# 获取图片
images = repo.get_game_images(results[0].id, role="SCREENSHOT")

# 统计
total = repo.count_games()
print(f"共 {total} 款游戏, {repo.count_images()} 张图片")

db.close()
```

---

## Collector 层

### ConcurrentCollector

并发采集器，使用 ThreadPoolExecutor 进行并发请求。

```python
class ConcurrentCollector:
    """并发采集器"""

    def __init__(
        self,
        client: PSStoreClient,
        repository: GameRepository,
        workers: int = 4,
        page_size: int = 20,
    ): ...

    async def collect_all(
        self,
        category_id: str,
        on_page_complete: Callable[[int, list[Game]], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> CollectionStats: ...
    """
    采集指定分类下的所有游戏
    
    Args:
        category_id: PS Store 分类 ID
        on_page_complete: 每页完成回调 (page_num, games)
        on_error: 错误回调
    
    Returns:
        CollectionStats (total_pages, total_games, total_images, errors, duration)
    """

    async def collect_page(
        self,
        category_id: str,
        page_offset: int,
    ) -> CategoryResponse: ...
    """采集单页"""
```

**CollectionStats 数据类：**

```python
@dataclass
class CollectionStats:
    total_pages: int      # 总页数
    total_games: int      # 成功采集游戏数
    total_images: int     # 总图片数
    errors: int           # 错误数
    duration: float       # 耗时(秒)
    pages_per_second: float  # 每秒页数
```

---

### ProgressTracker

断点续采进度跟踪器。

```python
class ProgressTracker:
    """SQLite 进度跟踪器（支持断点续采）"""

    def __init__(self, repository: GameRepository): ...

    def save_checkpoint(self, category_id: str, page_offset: int, total: int) -> None: ...
    """保存当前进度检查点"""

    def load_checkpoint(self, category_id: str) -> Checkpoint | None: ...
    """加载最近检查点"""

    def clear_checkpoint(self, category_id: str) -> None: ...
    """清除检查点"""

    def is_completed(self, category_id: str) -> bool: ...
    """判断是否已完成采集"""

@dataclass
class Checkpoint:
    category_id: str
    last_page_offset: int
    total_count: int
    updated_at: datetime
```

**断点续采流程：**

```
开始采集
    │
    ▼
┌─ 有 checkpoint? ──Yes──▶ 从 last_page_offset 继续
│                      No
▼
│ 从第 0 页开始
│
▼
每完成一页 → save_checkpoint(page_offset)
│
▼
遇到错误 → 记录 checkpoint → 可下次 --resume 恢复
│
▼
全部完成 → clear_checkpoint()
```

---

### CollectionPipeline

编排层，串联 Client → Parser → Repository → Progress。

```python
class CollectionPipeline:
    """采集流水线（编排层）"""

    def __init__(
        self,
        settings: Settings | None = None,
        on_progress: Callable[[PipelineProgress], None] | None = None,
    ): ...

    async def run(
        self,
        category_id: str | None = None,
        resume: bool = False,
        workers: int = 4,
    ) -> PipelineResult: ...
    """
    执行完整的采集流程
    
    Args:
        category_id: 分类 ID（默认 PS5 港服）
        resume: 是否从断点恢复
        workers: 并发数
    
    Returns:
        PipelineResult
    """

    async def dry_run(self, category_id: str | None = None) -> DryRunResult: ...
    """预览模式：仅获取第一页，不写入数据库"""

@dataclass
class PipelineProgress:
    current_page: int
    total_pages: int
    games_collected: int
    images_collected: int
    elapsed_seconds: float

@dataclass
class PipelineResult:
    stats: CollectionStats
    games: list[Game]
    duration: float
```

**使用示例：**

```python
import asyncio
from ps5_scraper.collectors.pipelines import CollectionPipeline

async def main():
    pipeline = CollectionPipeline()

    # 带进度回调
    def on_progress(p):
        print(f"页面 {p.current_page}/{p.total_pages} | "
              f"游戏 {p.games_collected} | "
              f"图片 {p.images_collected}")

    result = await pipeline.run(
        resume=True,
        workers=4,
        on_progress=on_progress,
    )

    print(f"✅ 完成! {result.stats.total_games} 款游戏, "
          f"{result.stats.total_images} 张图片, "
          f"耗时 {result.duration:.1f}s")

asyncio.run(main())
```

---

## CLI 命令参数表

### 全局选项

| 参数 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| `--config` | — | `config.yaml` | 配置文件路径 |
| `--verbose` / `-v` | — | `false` | 详细输出 |
| `--help` / `-h` | — | — | 显示帮助 |

### collect 子命令

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `-w, --workers` | int | `4` | 并发线程数 (1-16) |
| `-p, --page-size` | int | `20` | 每页数量 (10-100) |
| `-r, --resume` | flag | `false` | 断点续采 |
| `--dry-run` | flag | `false` | 预览模式 |

### export 子命令

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `-o, --output` | str | `games.json` | 输出路径 |
| `-f, --format` | str | `json` | 格式: json / csv |
| `--with-images` | flag | `false` | 包含图片详情 |

### status 子命令

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `-v, --verbose` | flag | `false` | 详细信息 |

### images 子命令

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `GAME_NAME` | positional | _(必填)_ | 游戏名称 |
| `-r, --role` | str | `all` | 过滤角色 |
| `--json` | flag | `false` | JSON 格式输出 |

---

## 异常层级

```
Exception
 └── APIClientError                    # API 客户端基础异常
      ├── RateLimitError               # 触发速率限制 (HTTP 429)
      │    └── message: str
      │    └── retry_after: int | None
      │
      ├── PSStoreAPIError              # PS Store API 业务错误
      │    ├── status_code: int
      │    └── response: dict | None
      │    │
      │    └── PSStoreHashExpiredError # GraphQL hash 已过期 ⚠️
      │         └── hash: str
      │         └── suggestion: str
      │
      └── NetworkError                 # 网络连接错误
           ├── request: httpx.Request
           └── original_error: Exception | None

ParseError                             # 响应解析异常（独立层级）
 ├── field: str                       # 解析失败的字段
 ├── raw_data: dict | None            # 原始数据
 └── message: str
```

### 异常处理最佳实践

```python
from ps5_scraper.api.base import (
    APIClientError,
    RateLimitError,
    NetworkError,
)
from ps5_scraper.api.psstore_client import PSStoreHashExpiredError
from ps5_scraper.api.psstore_parser import ParseError

try:
    games = await client.fetch_category_games(category_id)
except PSStoreHashExpiredError as e:
    print(f"⚠️ API Hash 已过期: {e.hash}")
    print(f"建议: {e.suggestion}")
    # 需要更新源码中的 hash 值
except RateLimitError as e:
    print(f"🐌 限速中, 请等待 {e.retry_after}s...")
except ParseError as e:
    print(f"❌ 解析失败 [{e.field}]: {e.message}")
except NetworkError as e:
    print(f"🔌 网络错误: {e.original_error}")
except APIClientError as e:
    print(f"❌ API 错误: {e}")
```

### 各异常触发场景

| 异常 | HTTP 状态码 | 触发条件 | 建议 |
|------|:-----------:|----------|------|
| `RateLimitError` | 429 | 请求过快 | 降低 `rate_limit_rpm` 或增加 `workers` 的反向调节 |
| `PSStoreHashExpiredError` | 200 (业务错误) | Sony 轮换了 hash | 更新 `psstore_client.py` 中的 hash 常量 |
| `NetworkError` | N/A | DNS/连接超时 | 检查网络，查看 `timeout` 设置 |
| `ParseError` | N/A | API 返回格式变更 | 检查是否需要更新 parser 适配新格式 |
| `PSStoreAPIError` | 5xx | 服务端错误 | 自动重试，通常短暂恢复 |

---

## 完整集成示例

```python
"""完整示例：采集 PS5 游戏并导出含截图的 JSON"""
import asyncio
import json
from ps5_scraper.config import Settings
from ps5_scraper.api.psstore_client import PSStoreClient
from ps5_scraper.api.psstore_parser import PSStoreParser
from ps5_scraper.storage.database import DatabaseManager
from ps5_scraper.storage.repositories import GameRepository
from ps5_scraper.models.game import Game

PS5_ID = "4cbf39e2-5749-4970-ba81-93a489e4570c"

async def collect_and_export():
    # 1. 初始化
    settings = Settings()
    db = DatabaseManager(settings.storage.db_path)
    db.initialize()
    repo = GameRepository(db)

    # 2. 采集
    async with PSStoreClient(settings) as client:
        offset = 0
        while True:
            raw = await client._request("post", "", json={
                "variables": {
                    "id": PS5_ID,
                    "offset": offset,
                    "pageSize": settings.collector.page_size,
                    "locale": settings.locale,
                },
                "extensions": {"persistedQuery": {...}},
            })
            response = PSStoreParser.parse_category_response(raw)

            for game in response.games:
                repo.upsert_game(game)
                repo.add_images(game.id, game.images)
                print(f"  ✓ {game.name} ({len(game.images)} images)")

            if not response.has_more:
                break
            offset += response.page_size

    # 3. 导出
    all_games = repo.export_all()
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(all_games, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ Done! {repo.count_games()} games, {repo.count_images()} images")
    db.close()

asyncio.run(collect_and_export())
```
