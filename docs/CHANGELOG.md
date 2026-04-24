# Changelog

> ps5-hk-scraper 重要变更记录

文件格式参考 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

---

## 版本时间线

| 版本 | 日期 | 类型 | 说明 |
|------|:----:|:----:|------|
| **v2.0.0** | 2026-04-24 | 🌍 多区域架构 | 21 区域支持 + Schema v2 + CLI 多区域参数 |
| **v1.0.0** | 2026-04-24 | 🎉 首次发布 | 完整的 PS5 港服图片链接采集工具 |

---

## [2.0.0] — 2026-04-24 (Multi-Region Architecture)

### Added ✨

**多区域核心**
- `Region` Pydantic 模型 — 定义区域代码/名称/语言/货币/启用状态
- `REGIONS` 字典 — 21 个预定义 PS Store 区域配置
- `get_region(code)` / `get_enabled_regions()` 工厂函数
- 大小写不敏感的区域代码查找（输入 `hk` / `HK` 均可）
- Game 模型新增 `region: str = "HK"` 字段
- Config `get_psstore_client(region=)` 工厂方法 — 自动解析 locale + currency
- PSStoreClient 支持 `currency` 参数化构造
- Database Schema v2 迁移 — 新增 `region TEXT DEFAULT 'HK'` 列 + 索引
- GameRepository 新增 `get_by_region()` / `get_count_by_region()` 方法
- PSStoreParser 支持注入 region 到解析结果
- ConcurrentCollector 支持传递 region 参数
- CollectionPipeline 新增 `run_multi_region_collection()` 多区域编排方法

**CLI 增强**
- `--region CODE` 参数 — 指定单个采集区域（大小写不敏感）
- `--all-regions` 标志 — 采集所有启用区域
- `--full` 标志 — 全量重采（清除进度后重新采集）
- 输入校验 — 无效区域代码自动报错并显示可用列表
- 统一结果展示面板 `_display_result_panel()` (DRY 重构)

**优化改进**
- models/__init__.py 统一导出接口
- PRAGMA 白名单校验（防御 SQL 注入）
- merge_data 将 region 加入 always_update 字段集
- Pipeline 空区域列表 guard（返回错误而非崩溃）
- --all-regions 使用 get_enabled_regions() 过滤禁用区域
- status 命令标题改为通用 "PS5 数据库状态"

### Changed 🔄

- **Breaking**: DB Schema v1 → v2 自动迁移（region 列 + 索引）
- Region 代码统一使用大写格式 (`"HK"` 而非 `"hk"`)
- REGIONS 字典 key 从小写改为大写（ISO 标准）
- 默认行为不变：未指定 `--region` 时仍为港服 (HK)
- collect 命令默认单区域模式，需显式 `--all-regions` 才启用多区域

### Security 🔒

- ✅ 安全扫描通过: 0 问题
  - 无硬编码密钥或凭证
  - SQL 参数化查询 + PRAGMA 白名单
  - 无命令注入风险
  - 无危险函数调用
- ✅ 独立代码评审完成: 14 项发现
  - 3 HIGH 已修复（Region大小写统一、空列表guard、禁用区域过滤）
  - 3 MEDIUM 已修复（CLI输入归一化、merge_data region更新、status标题）
  - 8 LOW 已记录（文档建议）

### Technical 🛠️

**技术栈**

| 类别 | 技术 | 版本 | 用途 |
|------|------|:----:|------|
| 语言 | Python | ≥3.11 | 运行时 |
| 数据校验 | Pydantic | v2.x | 数据模型、配置管理 |
| HTTP 客户端 | httpx | ≥0.24 | 异步 HTTP 请求 |
| CLI 框架 | Typer | ≥0.9 | 命令行界面 |
| 终端输出 | Rich | ≥13.0 | 美化表格/进度条/状态显示 |
| 数据库 | SQLite3 | 内置 | 本地持久化存储 (Schema v2) |
| 测试框架 | pytest | ≥7.0 | 单元测试/集成测试 |
| Mock 框架 | respx | ≥0.20 | httpx 异步 mock |

**项目统计**

| 指标 | v1.0.0 | v2.0.0 | 变化 |
|------|:------:|:------:|:----:|
| 源码文件 | 17 个 | 18 个 (+1) | +region.py |
| 源码行数 | 2,380 行 | ~3,200 行 | +35% |
| 测试文件 | 11 个 | 12 个 (+1) | +test_region_model.py |
| 测试用例 | 188 个 | 232 个 | +44 |
| Git 提交 | 13 次 | ~20+ 次 | +多区域改造 |
| 支持区域 | 1 (HK) | 21 | ×21 |

---

## [1.0.0] — 2026-04-24

### Added ✨

**数据模型**
- `Game` 模型 — 游戏主实体，含 id/name/locale/platforms/price/images 等字段
- `GamePrice` 模型 — 价格信息（原价/折扣价/折扣百分比/会员价/货币）
- `GameImage` 模型 — 图片资源（role/url/width/height/format/position）
- `CategoryResponse` 模型 — 分页容器（total_count/games/has_more）
- 支持 9 种图片角色: MASTER, GAMEHUB_COVER_ART, FOUR_BY_THREE_BANNER, PORTRAIT_BANNER, LOGO, SCREENSHOT, EDITION_KEY_ART, BACKGROUND, PREVIEW

**API 层**
- `BaseAPIClient` — 通用 HTTP 客户端，内置限速和重试机制
- `PSStoreClient` — PlayStation Store GraphQL API 客户端
- `PSStoreParser` — GraphQL 响应解析器

**存储层**
- `DatabaseManager` — SQLite WAL 模式数据库管理器
- `GameRepository` — 数据仓库 CRUD 层

**采集层**
- `ConcurrentCollector` — ThreadPoolExecutor 并发采集器
- `ProgressTracker` — 断点续采进度跟踪
- `CollectionPipeline` — 编排流水线

**CLI 工具**
- `ps5-scraper collect` / `export` / `status` / `images`

**配置系统**
- Pydantic Settings v2 + YAML 配置 + 环境变量覆盖

### Security 🔒

- ✅ 安全扫描通过: 0 问题
- ✅ 独立代码评审: 23 项发现全修复/记录

---

## [Unreleased]

### 计划中 (Roadmap)

#### v2.1.0 — 跨区域去重与合并
- [ ] 基于 `npTitleId` 的跨区域游戏去重
- [ ] 同游戏多区域价格对比表
- [ ] 区域独占游戏检测

#### v2.2.0 — 图片下载功能
- [ ] `ImageDownloader` — 批量下载图片到本地磁盘
- [ ] 支持按角色/区域选择性下载
- [ ] 并发下载 + 断点续传
- [ ] CLI 命令: `ps5-scraper download`

#### v3.0.0 — Web UI
- [ ] FastAPI Web 服务
- [ ] 图片浏览画廊（按区域筛选）
- [ ] REST API 端点

---

## 贡献指南

欢迎 Issue 和 Pull Request！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 运行测试确保全绿 (`pytest`)
4. Commit (遵循 Conventional Commits)
5. Push 到分支 (`git push origin feature/amazing-feature`)
6. 开启 Pull Request

---

[2.0.0]: https://github.com/user/ps5-hk-scraper/releases/tag/v2.0.0
[1.0.0]: https://github.com/user/ps5-hk-scraper/releases/tag/v1.0.0
