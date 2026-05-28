"""
Line Charts (Time Series)

Renders week-by-week line charts for the season:
    - Weekly scores       — raw points each gameweek per manager
    - League position     — mini-league rank at end of each gameweek (inverted y)
    - Cumulative points   — running total, the classic season race chart

All three share a common rendering core. Each manager gets:
    - A line with a glow effect (plotted twice: thick+transparent, then crisp)
    - Small dot markers at each gameweek data point
    - A circular avatar at the final data point, acting as the line label
    - A small text annotation of the final value next to the avatar

The charts are intentionally wide (FIGURE_WIDTH) and modestly tall so the
lines have room to breathe horizontally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from ..config import LeagueConfig
from .. import render


# Type aliases — match stats_timeseries output shapes
ManagerName = str
WeeklySeries = Dict[ManagerName, List[Tuple[int, int]]]   # {name: [(gw, value), ...]}
RankSeries   = Dict[ManagerName, List[Tuple[int, int]]]   # {name: [(gw, rank), ...]}


# ---------------------------------------------------------------------------
# Shared line rendering core
# ---------------------------------------------------------------------------

def _render_line_chart(
    title: str,
    series: WeeklySeries,
    config: LeagueConfig,
    output_path: Path,
    ylabel: str,
    invert_y: bool = False,
    y_tick_formatter: Optional[ticker.Formatter] = None,
    final_value_fmt: str = "{v}",
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
    per_point_avatar: bool = False,
    height: float = 9,
    space_end_labels: bool = False,
) -> None:
    """
    Core renderer shared by all three line chart types.

    Args:
        title:             Chart title, shown top-left in accent colour.
        series:            {manager_fpl_name: [(gameweek, value), ...]}
                           Each manager's list must be sorted chronologically.
        config:            League config for display names, colours, avatars.
        output_path:       Destination PNG path.
        ylabel:            Y-axis label.
        invert_y:          When True, the y-axis is inverted so rank 1 sits
                           at the top (used for the league position chart).
        y_tick_formatter:  Optional custom tick formatter for the y-axis.
        final_value_fmt:   Format string for the end-of-line annotation.
                           Use "{v}" as the placeholder for the value,
                           e.g. "{v}pts" or "#{v}".
    """
    if not series:
        return

    # Figure is wider than bar charts — lines need horizontal room
    fig, ax = plt.subplots(figsize=(render.FIGURE_WIDTH, height))
    render.apply_line_style(
        fig, ax, title=title, ylabel=ylabel, subtitle=subtitle, description=description,
    )

    all_gameweeks = sorted({gw for pts in series.values() for gw, _ in pts})
    if not all_gameweeks:
        plt.close(fig)
        return

    ax.set_xticks(all_gameweeks)
    ax.set_xlim(all_gameweeks[0] - 0.5, all_gameweeks[-1] + 1.5)

    # AnnotationBbox artists don't drive autoscaling, so when we render
    # purely with per-point avatars the y-axis collapses to a default
    # 0–1 range. Set the limits explicitly from the data.
    if per_point_avatar:
        all_values = [v for points in series.values() for _, v in points]
        if all_values:
            y_min = min(all_values)
            y_max = max(all_values)
            y_pad = max((y_max - y_min) * 0.05, 1)
            ax.set_ylim(y_min - y_pad, y_max + y_pad)

    if y_tick_formatter:
        ax.yaxis.set_major_formatter(y_tick_formatter)

    if invert_y:
        ax.invert_yaxis()

    # Sort managers so the end-of-period winner is drawn last (ends up on top).
    # Non-inverted axes (points): winner has highest final value → sort ascending
    # so the highest is last. Inverted axes (ranks): winner has lowest rank
    # number → sort descending so rank 1 is last.
    def final_value(item: tuple) -> int:
        _, pts = item
        return pts[-1][1] if pts else 0

    draw_order = sorted(series.items(), key=final_value, reverse=invert_y)

    # Track end-label artists for optional de-collision below.
    end_label_artists: list[tuple[float, "matplotlib.text.Annotation"]] = []

    # For per-point avatars: pre-compute per-gameweek zorder so the highest
    # scorer that week is drawn last (on top) when avatars overlap.
    gw_zorder: dict[int, dict[str, float]] = {}
    if per_point_avatar:
        for gw in all_gameweeks:
            scores_at_gw = [
                (name, v) for name, pts in series.items()
                for g, v in pts if g == gw
            ]
            scores_at_gw.sort(key=lambda nv: nv[1])
            gw_zorder[gw] = {name: 10 + idx for idx, (name, _) in enumerate(scores_at_gw)}

            # Vertical connector spanning that gameweek's lowest to highest
            # score. Ties the week's avatars together and makes the spread of
            # scores legible at a glance. Neutral colour, drawn behind the
            # avatars (zorder < 10), with the same glow treatment as the lines.
            if len(scores_at_gw) >= 2:
                lo, hi = scores_at_gw[0][1], scores_at_gw[-1][1]
                ax.plot(
                    [gw, gw], [lo, hi],
                    color=render.TEXT_SECONDARY,
                    linewidth=render.GLOW_WIDTH,
                    alpha=render.GLOW_ALPHA,
                    zorder=1,
                    solid_capstyle="round",
                )
                ax.plot(
                    [gw, gw], [lo, hi],
                    color=render.TEXT_SECONDARY,
                    linewidth=1.5,
                    alpha=0.45,
                    zorder=2,
                    solid_capstyle="round",
                )

    for fpl_name, data_points in draw_order:
        if not data_points:
            continue

        manager_cfg = config.get_manager(fpl_name)
        colour      = manager_cfg.colour      if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar      = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_LINE,
            border_colour=colour,
            border_ratio=render.AVATAR_BORDER_RATIO_LINE,
        )

        gws    = [gw for gw, _ in data_points]
        values = [v  for _,  v in data_points]

        if per_point_avatar:
            # No connecting line — treat each gameweek as an independent
            # data point. Place an avatar at every (gw, value); the
            # per-gameweek zorder ensures the highest scorer that week
            # sits on top when avatars overlap.
            for gw_i, val_i in zip(gws, values):
                render.place_avatar(
                    ax,
                    x=gw_i,
                    y=val_i,
                    avatar_rgba=avatar,
                    zoom=render.AVATAR_ZOOM_LINE,
                    zorder=gw_zorder[gw_i][fpl_name],
                )
            continue

        # Glow pass — thick, low alpha
        ax.plot(
            gws, values,
            color=colour,
            linewidth=render.GLOW_WIDTH,
            alpha=render.GLOW_ALPHA,
            zorder=2,
            solid_capstyle="round",
        )

        # Crisp line pass
        ax.plot(
            gws, values,
            color=colour,
            linewidth=render.LINE_WIDTH,
            alpha=1.0,
            zorder=3,
            solid_capstyle="round",
        )

        # Dot markers at each data point (filled with background colour for
        # a hollow-centre effect)
        ax.plot(
            gws, values,
            "o",
            color=colour,
            markersize=5,
            markerfacecolor=render.BACKGROUND,
            markeredgewidth=1.5,
            zorder=4,
        )

        # Avatar at the final data point
        final_gw    = gws[-1]
        final_value_v = values[-1]
        render.place_avatar(
            ax,
            x=final_gw,
            y=final_value_v,
            avatar_rgba=avatar,
            zoom=render.AVATAR_ZOOM_LINE,
        )

        # Final value annotation just to the right of the avatar
        # Offset in data units: ~0.6 gameweeks right, nudged up slightly
        ann = ax.annotate(
            final_value_fmt.format(v=final_value_v),
            xy=(final_gw, final_value_v),
            xytext=(final_gw + 0.55, final_value_v),
            va="center",
            ha="left",
            color=colour,
            fontsize=8,
            fontweight="bold",
            zorder=6,
        )
        end_label_artists.append((final_value_v, ann))

    if space_end_labels and end_label_artists:
        # Bump labels apart vertically so close finals don't overlap.
        # Iterate from the bottom up: each label sits at max(its own y, prev + min_gap).
        y_lo, y_hi = ax.get_ylim()
        axis_span = abs(y_hi - y_lo)
        # Minimum vertical gap between end-labels, as a fraction of the y-axis
        # span. Lower = labels sit closer to their avatars; higher = more
        # separation but more disconnected. Tune this to taste.
        min_gap = axis_span * 0.015
        sorted_labels = sorted(end_label_artists, key=lambda p: p[0])
        prev_y = float("-inf")
        for orig_y, ann in sorted_labels:
            target_y = max(orig_y, prev_y + min_gap)
            if target_y != orig_y:
                x, _ = ann.xyann
                ann.xyann = (x, target_y)
            prev_y = target_y

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    # Many per-point AnnotationBbox artists confuse matplotlib's
    # bbox_inches="tight" calculation — it balloons the saved canvas to
    # tens of thousands of pixels. Use the figure's natural size instead.
    render.save_figure(fig, output_path, tight_bbox=not per_point_avatar)


# ---------------------------------------------------------------------------
# Public chart functions
# ---------------------------------------------------------------------------

def render_weekly_scores(
    series: WeeklySeries,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Render a line chart of raw points scored each gameweek per manager.

    Useful for spotting form runs, disasters, and chip weeks. Lines that
    spike dramatically are often chip weeks or captaincy differentials.

    Args:
        series:      Output of calculate_weekly_scores —
                     {fpl_name: [(gameweek, points), ...]}
        config:      League config.
        output_path: Destination PNG path.
    """
    _render_line_chart(
        title="Weekly Scores",
        series=series,
        config=config,
        output_path=output_path,
        ylabel="Points",
        invert_y=False,
        final_value_fmt="{v}pts",
        subtitle=subtitle,
        description=description,
        per_point_avatar=True,
    )


def render_league_position(
    series: RankSeries,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Render a line chart of mini-league position at the end of each gameweek.

    Y-axis is inverted so rank 1 sits at the top. Integer ticks only.
    The number of managers in the league is inferred from the maximum rank
    seen in the data, so the y-axis always spans 1 → league size.

    Args:
        series:      Output of calculate_weekly_rankings —
                     {fpl_name: [(gameweek, rank), ...]}
        config:      League config.
        output_path: Destination PNG path.
    """
    if not series:
        return

    # Y-axis: 1 at top, n_managers at bottom
    all_ranks = [rank for pts in series.values() for _, rank in pts]
    n_managers = max(all_ranks) if all_ranks else 1

    fig, ax = plt.subplots(figsize=(render.FIGURE_WIDTH, 7))
    render.apply_line_style(
        fig, ax,
        title="League Position",
        ylabel="Position",
        subtitle=subtitle,
        description=description,
    )

    all_gameweeks = sorted({gw for pts in series.values() for gw, _ in pts})
    if not all_gameweeks:
        plt.close(fig)
        return

    ax.set_xticks(all_gameweeks)
    ax.set_xlim(all_gameweeks[0] - 0.5, all_gameweeks[-1] + 1.5)

    # Integer ticks, 1 at top
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_ylim(n_managers + 0.5, 0.5)   # inverted: 1 at top

    # Draw managers with worst final position first (they end up behind)
    def final_rank(item: tuple) -> int:
        _, pts = item
        return pts[-1][1] if pts else n_managers + 1

    draw_order = sorted(series.items(), key=final_rank, reverse=True)

    for fpl_name, data_points in draw_order:
        if not data_points:
            continue

        manager_cfg  = config.get_manager(fpl_name)
        colour       = manager_cfg.colour       if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar       = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
            border_colour=colour,
            border_ratio=render.AVATAR_BORDER_RATIO_BAR,
        )

        gws    = [gw   for gw, _ in data_points]
        values = [rank for _,  rank in data_points]

        ax.plot(gws, values, color=colour,
                linewidth=render.GLOW_WIDTH, alpha=render.GLOW_ALPHA,
                zorder=2, solid_capstyle="round")

        ax.plot(gws, values, color=colour,
                linewidth=render.LINE_WIDTH, alpha=1.0,
                zorder=3, solid_capstyle="round")

        ax.plot(gws, values, "o", color=colour,
                markersize=5, markerfacecolor=render.BACKGROUND,
                markeredgewidth=1.5, zorder=4)

        final_gw   = gws[-1]
        final_rank_v = values[-1]
        render.place_avatar(ax, x=final_gw, y=final_rank_v,
                            avatar_rgba=avatar, zoom=render.AVATAR_ZOOM_BAR)

        ax.annotate(
            display_name,
            xy=(final_gw, final_rank_v),
            xytext=(final_gw + 0.9, final_rank_v),
            va="center",
            ha="left",
            color=colour,
            fontsize=10,
            fontweight="bold",
            zorder=6,
        )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


def render_cumulative_points(
    series: WeeklySeries,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Render a running total points race chart — the classic season arc.

    Lines only ever go up, so the visual spread between managers widens
    over the season. The manager leading at GW38 ends up with the highest
    line, providing a clear winner narrative.

    Args:
        series:      Output of calculate_cumulative_points —
                     {fpl_name: [(gameweek, cumulative_points), ...]}
        config:      League config.
        output_path: Destination PNG path.
    """
    _render_line_chart(
        title="Cumulative Points",
        series=series,
        config=config,
        output_path=output_path,
        ylabel="Total Points",
        invert_y=False,
        final_value_fmt="{v}pts",
        subtitle=subtitle,
        description=description,
        height=11,
        space_end_labels=True,
    )


def render_global_standing(
    standing: Dict[ManagerName, Dict[str, float]],
    total_players: int,
    config: LeagueConfig,
    output_path: Path,
    gameweek: Optional[int] = None,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a snapshot of where each league manager sits in the global FPL
    field, as a single vertical "field line" spanning 0–100% of all players.

    The single vertical field line is itself the axis: it runs 0→100% of the
    worldwide field (higher = better) with stub marks at the quartiles, and
    avatars sit directly on it (top scorer drawn last so it wins overlaps).
    Each manager's row reads "x,xxx pts (top x%)  name", the variable-length
    name kept last (right-aligned block) so the name column lines up.
    Quartiles are exact because they are percentiles, not point thresholds.

    Args:
        standing:      Output of calculate_global_standing —
                       {fpl_name: {"overall_rank", "total_points", "percentile"}}.
        total_players: Global FPL entry count, used for the subtitle context.
        config:        League config for display names, colours, avatars.
        output_path:   Destination PNG path.
        gameweek:      Snapshot gameweek (for the subtitle), optional.
        subtitle:      Optional subtitle override; derived when omitted.
    """
    if not standing:
        return

    # x positions are axes fractions: xlim is 0–1, so data x == fraction. The
    # field line sits near the left; the manager rows fill the space rightward.
    line_x   = 0.077  # the field line / avatar column (kept far left so the
                      # joining lines have room to run out to the labels)
    block_x  = 0.56   # right edge of the "x,xxx pts (top x%)" column
    name_x   = 0.62   # left edge of the name column

    fig, ax = plt.subplots(figsize=(4.0, 11))

    if subtitle is None:
        bits = []
        if gameweek is not None:
            bits.append(f"After GW{gameweek}")
        if total_players:
            bits.append(f"{total_players / 1e6:.1f}M players worldwide")
        subtitle = "  ·  ".join(bits) or None

    render.apply_line_style(
        fig, ax,
        title="Global Standing",
        ylabel="",
        subtitle=subtitle,
    )

    # The vertical line IS the axis here, so strip all the usual furniture:
    # no ticks, no grid, no spines.
    ax.set_xlabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.yaxis.grid(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.set_xlim(0, 1)
    ax.set_ylim(-6, 106)

    # The field line — a 0→100 axis the avatars sit on — with the weekly-scores
    # glow treatment (thick transparent pass, then a crisp thin pass).
    for width, alpha, z in ((render.GLOW_WIDTH, render.GLOW_ALPHA, 2), (1.5, 0.55, 3)):
        ax.plot(
            [line_x, line_x], [0, 100],
            color=render.TEXT_SECONDARY, linewidth=width, alpha=alpha,
            zorder=z, solid_capstyle="round",
        )

    # Stub marks at the ends (0/100) and quartiles of the field line.
    stub_half = 0.037
    for y in (0, 25, 50, 75, 100):
        ax.plot(
            [line_x - stub_half, line_x + stub_half], [y, y],
            color=render.TEXT_SECONDARY, linewidth=1.5, alpha=0.7, zorder=4,
            solid_capstyle="round",
        )

    # Draw avatars bottom-to-top so the best-placed manager sits on top, and
    # collect each row's (true position, top %, points, name, colour).
    draw_order = sorted(standing.items(), key=lambda kv: kv[1]["percentile"])
    rows: list[tuple] = []
    for idx, (fpl_name, info) in enumerate(draw_order):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_LINE,
            border_colour=colour,
            border_ratio=render.AVATAR_BORDER_RATIO_LINE,
        )
        render.place_avatar(
            ax,
            x=line_x,
            y=info["percentile"],
            avatar_rgba=avatar,
            zoom=render.AVATAR_ZOOM_LINE,
            zorder=10 + idx,
        )
        rows.append((
            info["percentile"],
            100.0 - info["percentile"],
            int(info["total_points"]),
            display_name,
            colour,
        ))

    # Spread the rows apart so clustered managers (often bunched near the top)
    # stay legible, then draw each as three aligned columns with a faint leader
    # back to the avatar's true position on the line.
    min_gap = 3.0
    placed_y = float("-inf")
    for true_y, top_pct, pts, name, colour in sorted(rows, key=lambda r: r[0]):
        label_y = max(true_y, placed_y + min_gap)
        placed_y = label_y
        ax.plot(
            [line_x, 0.213], [true_y, label_y],
            color=colour, alpha=0.3, linewidth=1.0, zorder=5,
            solid_capstyle="round",
        )
        ax.text(block_x, label_y, f"{pts:,} pts   (top {top_pct:.1f}%)",
                ha="right", va="center",
                color=colour, fontsize=10, fontweight="bold", clip_on=False, zorder=6)
        ax.text(name_x, label_y, name, ha="left", va="center",
                color=colour, fontsize=10, fontweight="bold", clip_on=False, zorder=6)

    plt.tight_layout(rect=[0, 0, 1, 0.92])
    # Avatar-heavy figure — same bbox caveat as the per-point weekly chart.
    render.save_figure(fig, output_path, tight_bbox=False)


# ---------------------------------------------------------------------------
# Convenience: render all three line charts
# ---------------------------------------------------------------------------

def render_all_line_charts(
    timeseries: dict,
    config: LeagueConfig,
    output_dir: Path,
) -> None:
    """
    Render all three line charts from the output of calculate_all_timeseries.

    Output files:
        weekly_scores.png
        league_position.png
        cumulative_points.png

    Args:
        timeseries:  Output of calculate_all_timeseries — dict with keys
                     'weekly_scores', 'weekly_rankings', 'cumulative_points'.
        config:      League config.
        output_dir:  Directory to write PNGs into.
    """
    render_weekly_scores(
        series=timeseries.get("weekly_scores", {}),
        config=config,
        output_path=output_dir / "weekly_scores.png",
    )
    render_league_position(
        series=timeseries.get("weekly_rankings", {}),
        config=config,
        output_path=output_dir / "league_position.png",
    )
    render_cumulative_points(
        series=timeseries.get("cumulative_points", {}),
        config=config,
        output_path=output_dir / "cumulative_points.png",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordinal_suffix(n: int) -> str:
    """Return the ordinal suffix for an integer: 1→'st', 2→'nd', 3→'rd', 4→'th'."""
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
