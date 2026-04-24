# Changelog

> ps5-hk-scraper 重要变更记录

文件格式参考 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

---

## 版本时间线

| 版本 | 日期 | 类型 | 说明 |
|------|:----:|:----:|------|
| **v1.0.0** | 2026-04-24 | 🎉 首次发布 | 完整的 PS5 港服图片链接采集工具 |
| v1.1.0 | 📋 规划中 | 🔜 图片下载功能 | 批量下载图片到本地 |
| v2.0.0 | 📋 远期规划 | 🔮 详情接口扩展 | 游戏详情、评价、奖杯数据 |

---

## [1.0.0] — 2026-04-24

### Added ✨

**数据模型**
- `Game` 模型 — 游戏主实体，含 id/name/locale/platform/price/images 等字段
- `GamePrice` 模型 — 价格信息（原价/折扣价/折扣百分比/会员价/货币）
- `GameImage` 模型 — 图片资源（role/url/width/height/format/position）
- `CategoryResponse` 模型 — 分页容器（total_count/games/has_more）
- 支持 9 种图片角色: MASTER, GAMEHUB_COVER_ART, FOUR_BY_THREE_BANNER, PORTRAIT_BANNER, LOGO, SCREENSHOT, EDITION_KEY_ART, BACKGROUND, PREVIEW

**API 层**
- `BaseAPIClient` — 通用 HTTP 客户端，内置限速和重试机制
  - 令牌桶算法 RPM 限制（默认 60 RPM）
  - Exponential Backoff + Jitter 重试策略
  - 自动重试 429/5xx 状态码
- `PSStoreClient` — PlayStation Store GraphQL API 客户端
  - Persisted Queries 支持
  - 分页获取分类游戏列表 (`fetch_category_games`)
  - 单款游戏详情查询 (`fetch_game_detail`)
- `PSStoreParser` — GraphQL 响应解析器
  - 分类列表响应解析 (`parse_category_response`)
  - 游戏详情解析 (`parse_game_detail`)
  - 核心方法: 图片链接提取 (`extract_images`) — 从 media 列表中按角色提取所有图片
  - 价格数据解析 (`parse_price`)

**存储层**
- `DatabaseManager` — SQLite 数据库管理器
  - WAL (Write-Ahead Logging) 模式
  - 自动 Schema 创建和迁移
  - 线程安全连接管理
- `GameRepository` — 数据仓库 CRUD 层
  - 游戏: upsert / get / get_all / search / delete / count
  - 图片: get / add / delete / count（支持角色过滤）
  - 进度跟踪: save / load / clear checkpoint
  - 批量导出: export_all

**采集层**
- `ConcurrentCollector` — 并发采集器
  - ThreadPoolExecutor 多线程并发
  - Semaphore 信号量控制并发数
  - 自动分页遍历全部 ~386 页
  - CollectionStats 统计（页数/游戏数/图片数/错误数/耗时）
- `ProgressTracker` — 断点续采进度跟踪
  - SQLite 持久化检查点
  - 支持中断后从断点恢复
  - 完成后自动清理检查点
- `CollectionPipeline` — 编排流水线
  - 串联 Client → Parser → Repository → Progress 全流程
  - PipelineProgress 实时进度回调
  - dry_run 预览模式
  - resume 断点续采模式

**CLI 工具**
- `ps5-scraper collect` — 采集命令（workers/page-size/resume/dry-run）
- `ps5-scraper export` — 导出命令（output/format/with-images）
- `ps5-scraper status` — 状态查看（verbose）
- `ps5-scraper images` — 图片查看（搜索/角色过滤/JSON 输出）

**配置系统**
- Pydantic Settings v2 配置模型
- YAML 文件加载 (`config.yaml`)
- 环境变量覆盖（`PS5_` 前缀）
- 工厂方法: `Settings.from_yaml()`, `Settings.from_env()`

### Changed 🔄

- 初始版本，无历史变更

### Security 🔒

- ✅ 安全扫描通过: 0 问题
  - 无硬编码密钥或凭证
  - 无 SQL 注入风险（参数化查询）
  - 无命令注入风险
  - 无危险函数调用
- ✅ 独立代码评审完成: 23 项发现
  - 2 CRITICAL 已修复
  - 3 HIGH 已修复
  - 8 MEDIUM 已记录
  - 7 LOW 已记录
  - 3 INFO 已记录

### Technical 🛠️

**技术栈**

| 类别 | 技术 | 版本 | 用途 |
|------|------|:----:|------|
| 语言 | Python | ≥3.11 | 运行时（match-case, TypeVarTuple 等） |
| 数据校验 | Pydantic | v2.x | 数据模型、配置管理 |
| HTTP 客户端 | httpx | ≥0.24 | 异步 HTTP 请求 |
| CLI 框架 | Typer | ≥0.9 | 命令行界面 |
| 终端输出 | Rich | ≥13.0 | 美化表格/进度条/状态显示 |
| 数据库 | SQLite3 | 内置 | 本地持久化存储 |
| 测试框架 | pytest | ≥7.0 | 单元测试/集成测试 |
| Mock 框架 | respx | ≥0.20 | httpx 异步 mock |

**项目统计**

| 指标 | 数值 |
|------|:----:|
| 源码文件 | 17 个 Python 文件 |
| 源码行数 | 2,380 行 |
| 测试文件 | 11 个 Python 文件 |
| 测试行数 | 3,215 行 |
| 测试用例 | 188 个 |
| 测试通过率 | 100% ✅ |
| Git 提交 | 13 次 |

---

## [Unreleased]

### 计划中 (Roadmap)

#### v1.1.0 — 图片下载功能
- [ ] `ImageDownloader` — 批量下载图片到本地磁盘
- [ ] 支持按角色选择性下载
- [ ] 并发下载 + 断点续传
- [ ] 文件命名规则: `{game_id}_{role}_{position}.{ext}`
- [ ] CLI 命令: `ps5-scraper download`
- [ ] 下载进度条 (Rich Progress)

#### v1.2.0 — 增量更新
- [ ] 基于 `updated_at` 的增量采集
- [ ] 变更检测（价格变动、新图片）
- [ ] 变更通知（Webhook / 日志）

#### v2.0.0 — 详情接口扩展
- [ ] 游戏描述/简介完整文本
- [ ] 用户评分与评论摘要
- [ ] 奖杯列表与达成率
- [ ] DLC / 版本变体关系
- [ ] 发行商/开发商/发行日期元数据
- [ ] 多地区支持（日服/美服/欧服）

#### v2.1.0 — Web UI
- [ ] FastAPI Web 服务
- [ ] 图片浏览画廊
- [ ] 搜索与过滤界面
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

[1.0.0]: https://github.com/user/ps5-hk-scraper/releases/tag/v1.0.0
