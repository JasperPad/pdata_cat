# PS5 Scraper v2.0 多区域架构改造方案

> **版本**: v2.0 Draft  
> **日期**: 2026-04-24  
> **状态**: Phase A 完成 → 待进入 Phase B TDD 开发  
> **作者**: Hermes Agent  

---

## 一、现状分析总结

### 1.1 项目规模

| 类别 | 数量 | 行数 |
|------|------|------|
| 源码文件 (.py) | 16 | ~4,934 |
| 测试文件 | 11 | ~3,215 |
| 配置/文档 | 8 | ~2,100 |
| **合计** | **35** | **~10,249** |

### 1.2 核心依赖关系图

```
cli.py (Typer 入口)
 └── pipelines.py (采集编排)
      ├── config.py (配置管理)
      ├── psstore_client.py (API 客户端) ← base.py (HTTP 基础)
      ├── psstore_parser.py (响应解析)
      ├── concurrent.py (并发采集引擎)
      │    └── repositories.py (数据访问层)
      │         └── database.py (SQLite 管理)
      └── progress.py (断点续采)
```

### 1.3 当前硬编码/单区域点（需改造）

| 文件 | 行号 | 硬编码内容 | 改造方向 |
|------|------|-----------|---------|
| `psstore_client.py` | L99 | `"currency": "HKD"` | 参数化 currency |
| `psstore_client.py` | L37 | `locale="zh-hant-hk"` 默认值 | 已是参数 ✅（只需传新值）|
| `config.py` | L25 | `_DEFAULT_LOCALE = "zh-hant-hk"` | 增加 regions 定义 |
| `config.py` | L108-109 | 单一 `locale` 字段 | 保留为默认区域，新增 `regions` 字典 |
| `database.py` | L52-76 | Schema v1 无 region 列 | 升级 Schema v2，加 region 列 |
| `repositories.py` | L87-116 | upsert 不含 region | 增加 region 字段处理 |
| `models/game.py` | L30-46 | Game 模型无 region | 可选增加 region 字段 |
| `pipelines.py` | L40-149 | 单区域采集逻辑 | 新增多区域编排方法 |
| `cli.py` | L90-96 | collect 无 --region | 增加 --region / --all-regions |
| `settings.yaml` | L7 | 单一 locale | 增加 regions 段 |

---

## 二、架构设计

### 2.1 设计原则

1. **向后兼容** — 不指定 `--region` 时默认行为与 v1.0 完全一致（港服）
2. **最小侵入** — 尽量通过扩展而非修改现有逻辑
3. **跨区域去重** — 用 `npTitleId`（即 `Game.id`）作为统一去重键
4. **独立进度** — 每个区域的采集进度独立跟踪，互不干扰
5. **单一数据库** — 所有区域数据存入同一 SQLite 数据库，用 `region` 列区分

### 2.2 区域模型设计

```python
# models/region.py (新建)
class Region(BaseModel):
    """PS Store 区域定义."""
    code: str                    # 区域代码: "hk", "us", "jp" 等
    locale: str                  # API locale: "zh-hant-hk", "en-us"
    currency: str                # 货币代码: "HKD", "USD", "JPY"
    name: str                    # 显示名称: "港服", "美服", "日服"
    language: str = ""           # 语言代码（可选）
    enabled: bool = True         # 是否启用
    priority: int = 0            # 优先级（数字越小越优先）
```

### 2.3 预定义区域列表（基于调研报告）

```python
REGIONS: dict[str, Region] = {
    "us":  Region(code="us",  locale="en-us",     currency="USD", name="美服",   priority=1),
    "jp":  Region(code="jp",  locale="ja-jp",     currency="JPY", name="日服",   priority=2),
    "uk":  Region(code="uk",  locale="en-gb",     currency="GBP", name="英服",   priority=3),
    "de":  Region(code="de",  locale="de-de",     currency="EUR", name="德服",   priority=4),
    "kr":  Region(code="kr",  locale="ko-kr",     currency="KRW", name="韩服",   priority=5),
    "tw":  Region(code="tw",  locale="zh-hant-tw",currency="TWD", name="台服",   priority=6),
    "br":  Region(code="br",  locale="pt-br",     currency="BRL", name="巴西服", priority=7),
    "hk":  Region(code="hk",  locale="zh-hant-hk",currency="HKD", name="港服",   priority=10),  # 默认
    "cn":  Region(code="cn",  locale="zh-cn",     currency="CNY", name="国服",   enabled=False), # 仅35款
    # 跳过空区域: th-th(0), id-id(0), vi-vn(报错)
}
```

### 2.4 数据库 Schema 变更（v1 → v2）

```sql
-- Schema v2: 新增 region 列
ALTER TABLE games ADD COLUMN region TEXT DEFAULT 'hk';
CREATE INDEX IF NOT EXISTS idx_games_region ON games(region);
CREATE UNIQUE INDEX IF NOT EXISTS idx_games_id_region ON games(id, region);

-- Schema version 更新
INSERT INTO schema_version (version) VALUES (2);
```

**变更策略**：
- 已有数据的 `region` 列默认值为 `'hk'`（向后兼容）
- 新增复合唯一索引 `(id, region)` 支持同游戏多区域存储
- 保留原 `id PRIMARY KEY` 不变（避免破坏现有查询）

### 2.5 Game 模型变更

```python
class Game(BaseModel):
    # ... 现有字段不变 ...
    region: str = "hk"          # ← 新增：区域代码，默认港服
```

**影响范围**：
- `repositories.py` — upsert/get/_row_to_game 需同步更新
- `psstore_parser.py` — parse_product 时注入 region
- `concurrent.py` — 传递 region 到 game

---

## 三、文件级改造清单

### 3.1 新建文件

| 文件 | 用途 | 预估行数 |
|------|------|---------|
| `src/ps5_scraper/models/region.py` | Region Pydantic 模型 + 预定义区域常量 | ~80 |
| `src/ps5_scraper/collectors/multi_region_pipeline.py` | 多区域编排器（循环区域+聚合结果） | ~120 |

### 3.2 改造文件（按依赖顺序）

#### ① `models/game.py` (+3 行)
- `region: str = "hk"` 字段添加到 Game 模型

#### ② `models/__init__.py` (+2 行)
- 导出 Region 模型

#### ③ `config.py` (+60 行)
- 新增 `Region` import 和 `REGIONS` 默认字典
- `Settings` 新增 `regions: dict[str, dict]` 字段
- `_build_settings_dict()` 解析 YAML 的 `regions` 段
- `get_regions()` 方法返回启用区域列表
- `get_region(code)` 方法返回单个区域配置
- `get_psstore_client()` 重载：接受可选 `region` 参数

#### ④ `api/psstore_client.py` (+15 行)
- 构造函数新增 `currency: str = "HKD"` 参数
- `_build_graphql_body()` 使用 `self.currency` 替代硬编码 "HKD"

#### ⑤ `storage/database.py` (+20 行)
- `SCHEMA_VERSION = 2`
- `CREATE_GAMES_TABLE` DDL 新增 `region TEXT DEFAULT 'hk'`
- `CREATE_INDEXES` 新增 `idx_games_region` 和 `idx_games_id_region`
- `initialize()` 中增加 schema 迁移逻辑（v1→v2 自动加列）

#### ⑥ `storage/repositories.py` (+30 行)
- `upsert()` SQL 增加 `region` 列
- `_row_to_game()` 映射 region 字段（位置变化！）
- `get_by_region()` 新方法：按区域过滤
- `get_regions()` 新方法：列出已有区域

#### ⑦ `api/psstore_parser.py` (+5 行)
- `parse_product()` 接受可选 `region="hk"` 参数
- 构造 Game 时传入 region

#### ⑧ `collectors/concurrent.py` (+10 行)
- 构造函数新增 `region: str = "hk"`
- `_process_page()` 传递 region 到 parser
- 统计信息增加 region 标识

#### ⑨ `collectors/pipelines.py` (+80 行)
- `run_full_collection()` 新增 `region: str = "hk"` 参数
- 传递 region 到 client / collector / parser 链路
- **新增** `run_multi_region_collection(regions: list[str])` 方法
- 聚合多区域统计结果

#### ⑩ `cli.py` (+50 行)
- `collect_cmd` 新增 `--region` 选项（支持 "all" 或区域代码如 "us,jp,hk"）
- `status_cmd` 显示各区域统计
- help 文案更新（去掉"港服"限定词）

#### ⑪ `config/settings.yaml` (+25 行)
- 新增 `regions:` 段，定义所有可用区域

### 3.3 测试文件改动

| 测试文件 | 改动类型 | 说明 |
|---------|---------|------|
| `test_models.py` | 修改 | Game 模型测试加 region 断言；新增 Region 模型测试 |
| `test_config.py` | 修改 | regions 配置加载测试；get_region() 测试 |
| `test_psstore_client.py` | 修改 | currency 参数化测试 |
| `test_database.py` | 修改 | Schema v2 迁移测试；region 列验证 |
| `test_repositories.py` | 修改 | region upsert/get 过滤测试 |
| `test_psstore_parser.py` | 修改 | region 注入测试 |
| `test_concurrent_collector.py` | 修改 | region 传递测试 |
| `test_pipeline.py` | 修改 | 多区域编排测试（核心新增） |
| `test_cli.py` | 修改 | --region/--all-regions 选项测试 |
| **新建** `test_region_model.py` | 新增 | Region 模型单元测试 |
| **新建** `test_multi_region_pipeline.py` | 新增 | 多区域集成测试 |

---

## 四、数据流图（改造后）

### 4.1 单区域采集（向后兼容）

```
CLI: ps5-scraper collect --region hk
  → Settings(region="hk")
    → PSStoreClient(locale="zh-hant-hk", currency="HKD")
    → ConcurrentCollector(region="hk")
      → fetch_category_games() → parse_product(region="hk") → Game(region="hk")
        → Repository.upsert(game)  → DB: games(id, ..., region='hk')
```

### 4.2 多区域采集（新增）

```
CLI: ps5-scraper collect --region all
  → Settings.load_all_enabled_regions()
    → FOR EACH region IN ["us", "jp", "uk", "de", "kr", "tw", "br", "hk"]:
        → PSStoreClient(locale=region.locale, currency=region.currency)
        → ConcurrentCollector(region=region.code)
          → [fetch → parse → store] 循环
    → AGGREGATE stats across regions
    → RETURN {us: {...}, jp: {...}, total_games: 13000, ...}
```

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| API 速率限制 | 多区域请求可能触发封禁 | 全局 rate limiter 共享；建议串行区域+区域内并发 |
| Schema 迁移失败 | 旧 DB 无法升级 | 迁移前备份；迁移失败回滚到 v1 兼容模式 |
| 游戏去重冲突 | 同一游戏多区域价格不同 | 复合键 (id, region) 允许共存；不自动合并 |
| 内存占用 | 全区域 12K+ 游戏 | SQLite WAL 模式已支持；批量提交 |
| 测试回归 | 188 个现有测试可能 break | 先改测试再改实现（TDD）；每步跑全量测试 |

---

## 六、执行计划（Phase B-F 时间线）

| 阶段 | 内容 | 预计改动文件数 | 验证标准 |
|------|------|--------------|---------|
| **B: TDD 开发** | Models→Config→Client→DB→Repo→Parser→Collector→Pipeline→CLI | 13 | 全量测试通过 |
| **C: 优化** | DRY 重构、防御性编程、性能调优 | 5 | 无代码坏味道 |
| **D: 审计** | 安全扫描 + 独立评审 + 自动修复 | 全部 | 0 CRITICAL/HIGH |
| **E: 文档** | README/API/CHANGELOG/WORKLOG 更新 | 4 | 文档覆盖率 100% |
| **F: 验证** | 全量测试 + Git commit + 可选小规模采集验证 | - | 200+ 测试通过 |

---

*文档结束。下一步：进入 Phase B — 按 TDD 方式从 Models 层开始逐层改造。*
