"""CLI entry point for ps5-hk-scraper using typer and rich.

Provides four commands:
- collect: Start data collection for a category
- export: Export database data to JSON/CSV
- status: Show database statistics
- images: Query image links for games (v1.0 core feature)
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ps5_scraper import __version__
from ps5_scraper.collectors.pipelines import CollectionPipeline
from ps5_scraper.config import Settings
from ps5_scraper.models.game import Game, GameImage
from ps5_scraper.models.region import REGIONS
from ps5_scraper.storage.database import DatabaseManager
from ps5_scraper.storage.repositories import GameRepository

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="ps5-scraper",
    help="PS5 多区域数据采集工具 — PlayStation Store 图片链接采集 + SQLite 持久化",
    add_completion=False,
)
console = Console()

# Global option defaults
_opt_config: str | None = None
_opt_verbose: bool = False
_opt_output: str | None = None


def _get_settings(config_path: str | None = None) -> Settings:
    """Load settings from config file."""
    return Settings(config_file=config_path or "config/settings.yaml")


# ─── Callback (global options) ────────────────────────────


@app.callback()
def main(
    ctx: typer.Context,
    config: str | None = typer.Option(None, "--config", "-c", help="配置文件路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出模式"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件路径"),
) -> None:
    """Global options for ps5-scraper."""
    global _opt_config, _opt_verbose, _opt_output  # noqa: PLW0603
    _opt_config = config
    _opt_verbose = verbose
    _opt_output = output

    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
        )

    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["output"] = output


# ─── collect command ───────────────────────────────────────


@app.command("collect")
def collect_cmd(
    category: str = typer.Option("ps5_games", "--category", "-c", help="分类选择 (ps5_games/deals/free_games)"),
    full: bool = typer.Option(False, "--full", help="忽略断点续采，全量重采"),
    workers: int = typer.Option(4, "--workers", "-w", help="并发线程数"),
    output: str | None = typer.Option(None, "--output", "-o", help="数据库输出路径"),
    region: str | None = typer.Option(None, "--region", "-r", help="指定区域代码 (HK/US/JP/TW/...)，默认 HK"),
    all_regions: bool = typer.Option(False, "--all-regions", help="采集所有可用区域"),
) -> None:
    """开始采集 PS5 Store 数据.

    支持单区域或多区域采集，支持断点续采，中断后重新运行可从上次位置继续。

    示例:
      ps5-scraper collect                    # 采集港服（默认）
      ps5-scraper collect --region US        # 采集美服
      ps5-scraper collect --region JP --full  # 全量重采日服
      ps5-scraper collect --all-regions      # 采集所有区域
    """
    # Validate single-region option (case-insensitive input)
    if region and not all_regions:
        from ps5_scraper.models.region import get_region as _validate_region
        normalized = region.upper().strip()
        if not _validate_region(normalized):
            console.print(f"[red]无效区域代码: {region}[/red]")
            console.print(f"[dim]可用区域: {', '.join(sorted(REGIONS.keys()))}[/dim]")
            raise typer.Exit(1)
        # Store normalized uppercase value
        region = normalized

    settings = _get_settings(_opt_config)

    # Override db path if specified
    if output:
        settings.db_path = output

    # Override max_workers if specified
    if workers != 4:
        settings.max_workers = workers

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        pipeline = CollectionPipeline(settings)

        try:
            if all_regions:
                # Multi-region mode: collect all enabled regions (deduplicated, sorted)
                from ps5_scraper.models.region import get_enabled_regions
                region_list = [r.code for r in get_enabled_regions()]
                task = progress.add_task(f"正在采集 {len(region_list)} 个区域数据...", total=None)
                result = asyncio.run(pipeline.run_multi_region_collection(
                    regions=region_list,
                    category_key=category,
                    full_mode=full,
                ))
            else:
                # Single-region mode
                target_region = region or "HK"
                task = progress.add_task(f"正在采集 {target_region} 区域 {category} 数据...", total=None)
                result = asyncio.run(pipeline.run_full_collection(
                    category, full_mode=full, region=target_region,
                ))

            progress.update(task, description=f"✅ 采集完成!")
        except Exception as exc:
            progress.update(task, description=f"❌ 采集失败: {exc}")
            console.print(f"[red]采集出错: {exc}[/red]")
            raise typer.Exit(1) from exc

    # Display results (DRY: unified display helper)
    is_multi = all_regions and "regions_collected" in result
    _display_collection_result(result, region=region or "HK", multi_region=is_multi)

    if result.get("errors"):
        console.print("[red]错误列表:[/red]")
        for err in result["errors"]:
            console.print(f"  • {err}")


def _display_collection_result(
    result: dict[str, Any],
    *,
    region: str = "HK",
    multi_region: bool = False,
) -> None:
    """Unified collection result panel display.

    Args:
        result: Collection pipeline result dict.
        region: Region code for single-region display.
        multi_region: If True, show regions_collected instead of region code.
    """
    success = result.get("success", False)

    # Build common lines
    lines = [
        f"[bold]分类:[/bold] {result.get('category', 'N/A')}",
    ]
    if multi_region:
        lines.append(f"[bold]区域数:[/bold] {result.get('regions_collected', 0)}")
    else:
        lines.append(f"[bold]区域:[/bold] {region}")
    lines.extend([
        f"[bold]获取:[/bold] {result.get('total_fetched', 0)} 条",
        f"[bold]存储:[/bold] {result.get('total_stored', 0)} 条",
        f"[bold]图片:[/bold] {result.get('total_images', 0)} 张",
        f"[bold]耗时:[/bold] {result.get('duration_seconds', 0):.1f}s",
        f"[bold]状态:[/bold] {'[green]成功[/green]' if success else '[yellow]有错误[/yellow]'}",
    ])

    title_prefix = "多区域采集结果" if multi_region else "采集结果"
    title = f"[bold green]{title_prefix}[/bold green]" if success else f"[bold yellow]{title_prefix}[/bold yellow]"
    border = "green" if success else "yellow"

    console.print(Panel("\n".join(lines), title=title, border_style=border))


# ─── export command ───────────────────────────────────────


@app.command("export")
def export_cmd(
    fmt: str = typer.Option("json", "--format", "-f", help="导出格式: json/csv (默认 json)"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件路径"),
    images_only: bool = typer.Option(False, "--images-only", help="仅导出图片链接"),
) -> None:
    """导出数据库中的游戏数据.

    支持 JSON 和 CSV 格式导出。
    """
    settings = _get_settings(_opt_config)

    with DatabaseManager(db_path=settings.db_path) as db:
        repo = GameRepository(db)
        games = repo.get_all()

        if not games:
            console.print("[yellow]数据库中没有游戏数据，请先使用 collect 命令获取数据[/yellow]")
            raise typer.Exit(0)

        if images_only:
            data = _extract_all_images(games)
        else:
            data = [g.model_dump() for g in games]

        formatted = _format_export(data, fmt)

        if output:
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            Path(output).write_text(formatted, encoding="utf-8")
            console.print(f"[green]已导出 {len(data)} 条记录到[/green] {output}")
        else:
            console.print(formatted)


def _format_export(data: list[dict[str, Any]], fmt: str) -> str:
    """Format data to the requested export format."""
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    elif fmt == "csv":
        if not data:
            return ""
        fieldnames = list(data[0].keys())
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()
    else:
        raise ValueError(f"不支持的导出格式: {fmt} (支持: json, csv)")


def _extract_all_images(games: list[Game]) -> list[dict[str, Any]]:
    """Extract all images from a list of games into flat records."""
    records = []
    for game in games:
        for img in game.images:
            records.append({
                "game_id": game.id,
                "game_name": game.name,
                "image_role": img.role,
                "image_type": img.type,
                "image_url": img.url,
                "image_width": img.width,
                "image_height": img.height,
            })
    return records


# ─── status command ───────────────────────────────────────


@app.command("status")
def status_cmd() -> None:
    """显示数据库状态统计.

    包括游戏总数、图片链接总数、最近更新时间等。
    """
    settings = _get_settings(_opt_config)

    with DatabaseManager(db_path=settings.db_path) as db:
        repo = GameRepository(db)
        game_count = repo.get_count()
        games = repo.get_all(limit=1)  # Just to check if DB is accessible

        # Count total images across all games
        total_images = 0
        last_updated = 0
        if game_count > 0:
            all_games = repo.get_all(limit=game_count)
            total_images = sum(len(g.images) for g in all_games)
            if all_games:
                last_updated = max(g.last_updated for g in all_games)

    table = Table(title="PS5 数据库状态")
    table.add_column("指标", style="cyan")
    table.add_column("值", style="green")

    table.add_row("游戏总数", str(game_count))
    table.add_row("图片链接总数", str(total_images))

    if last_updated:
        from datetime import datetime
        dt = datetime.fromtimestamp(last_updated)
        table.add_row("最近更新时间", dt.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        table.add_row("最近更新时间", "—")

    table.add_row("数据库路径", settings.db_path)

    console.print(table)


# ─── images command (v1.0 core feature) ───────────────────


@app.command("images")
def images_cmd(
    game_id: str | None = typer.Option(None, "--game-id", help="指定游戏 ID"),
    role: str | None = typer.Option(None, "--role", help="按角色过滤 (MASTER/SCREENSHOT/GAMEHUB_COVER_ART/...)"),
    type_filter: str | None = typer.Option(None, "--type", help="按类型过滤 (IMAGE/VIDEO)"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
) -> None:
    """查询游戏图片链接 ⭐ v1.0 核心功能.

    可以查询任意游戏的图片链接列表，支持按角色和类型过滤。

    示例:
      ps5-scraper images --game-id HP0002-PPSA08784_00-GOYOTHEGAME0000
      ps5-scraper images --role MASTER --type IMAGE
      ps5-scraper images --game-id <id> --json
    """
    settings = _get_settings(_opt_config)

    with DatabaseManager(db_path=settings.db_path) as db:
        repo = GameRepository(db)

        if game_id:
            # Query specific game's images
            game = repo.get_by_id(game_id)
            if not game:
                console.print(f"[red]未找到游戏 ID: {game_id}[/red]")
                raise typer.Exit(0)

            images = repo.get_images(game_id)

            # Apply filters
            if role:
                images = [img for img in images if img.role.upper() == role.upper()]
            if type_filter:
                images = [img for img in images if img.type.upper() == type_filter.upper()]

            if json_output:
                _print_images_json(images)
            else:
                _display_game_images(game, images)
        else:
            # List all games with image counts
            games = repo.get_all(limit=100)
            if not games:
                console.print("[yellow]数据库中没有游戏数据[/yellow]")
                raise typer.Exit(0)

            if json_output:
                _print_images_json_summary(games)
            else:
                _display_all_games_image_summary(games)


def _print_images_json(images: list[GameImage]) -> None:
    """Print images as JSON to stdout."""
    data = [
        {
            "role": img.role,
            "type": img.type,
            "url": img.url,
            "width": img.width,
            "height": img.height,
        }
        for img in images
    ]
    console.print_json(json.dumps(data, ensure_ascii=False))


def _print_images_json_summary(games: list[Game]) -> None:
    """Print summary of all games' images as JSON."""
    data = []
    for game in games:
        data.append({
            "id": game.id,
            "name": game.name,
            "image_count": len(game.images),
            "roles": list(set(img.role for img in game.images)),
        })
    console.print_json(json.dumps(data, ensure_ascii=False))


def _display_game_images(game: Game, images: list[GameImage]) -> None:
    """Display a single game's images in a rich table."""
    console.print(Panel(
        f"[bold cyan]{game.name}[/bold cyan]\n"
        f"[dim]ID: {game.id}[/dim]",
        title=f"🎮 图片链接 ({len(images)} 张)",
        border_style="cyan",
    ))

    if not images:
        console.print("[yellow]没有匹配的图片[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("角色", style="cyan", width=24)
    table.add_column("类型", style="magenta", width=8)
    table.add_column("URL", style="green", max_width=60)
    table.add_column("尺寸", style="dim", width=12)

    for img in images:
        size_str = f"{img.width or '?'}x{img.height or '?'}"
        table.add_row(img.role, img.type, img.url, size_str)

    console.print(table)


def _display_all_games_image_summary(games: list[Game]) -> None:
    """Display a summary of all games with their image counts."""
    table = Table(title=f"游戏图片概览 ({len(games)} 个游戏)")
    table.add_column("游戏 ID", style="cyan", max_width=36)
    table.add_column("名称", style="green", max_width=30)
    table.add_column("图片数", style="magenta")
    table.add_column("角色类型", style="dim")

    for game in games:
        roles = ", ".join(set(img.role for img in game.images)) if game.images else "—"
        table.add_row(game.id, game.name, str(len(game.images)), roles)

    console.print(table)


# ─── version command ──────────────────────────────────────


@app.command("version")
def version_cmd() -> None:
    """显示版本信息."""
    console.print(f"ps5-hk-scraper v{__version__}")


if __name__ == "__main__":
    app()
