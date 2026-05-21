"""
Ranked Bar Charts

Renders simple horizontal bar charts for aggregate season stats:
    - Bench points left on bench (ranked, single bar per manager)
    - Transfer costs / hits taken (ranked, single bar per manager)
    - Positional points breakdown — defence, midfield, attack (grouped)
    - Score consistency — standard deviation bar with high/low range markers
    - Gameweek wins, losses, mid-table (stacked bar, fixed total width)

All charts share the same visual language from render.py: dark background,
Outfit font, manager avatar at the bar tip, grey background track.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from ..config import LeagueConfig
from .. import render


# Type aliases
ManagerName = str
RankedData = List[Tuple[ManagerName, int]]  # [(name, value), ...] sorted desc


# ---------------------------------------------------------------------------
# Simple ranked bar chart
# ---------------------------------------------------------------------------

def render_ranked_bar(
    title: str,
    data: RankedData,
    config: LeagueConfig,
    output_path: Path,
    xlabel: str = "Points",
    higher_is_worse: bool = False,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a single horizontal bar per manager, sorted by value.

    Used for bench points and transfer costs. The `higher_is_worse` flag
    inverts the bar colour logic — transfer hits are bad so the bars are
    rendered in a warning tone rather than the manager's own colour.

    Args:
        title:           Chart title shown top-left in accent colour.
        data:            List of (fpl_name, value) tuples, sorted descending.
        config:          League config for display names, colours, avatars.
        output_path:     Destination PNG path.
        xlabel:          X-axis label.
        higher_is_worse: When True, bars are rendered in LOSS_COLOUR rather
                         than the manager's personal colour, since a higher
                         value is a negative outcome.
    """
    if not data:
        return

    n_managers = len(data)
    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(fig, ax, title=title, xlabel=xlabel, subtitle=subtitle)

    max_value = max(v for _, v in data) if data else 1
    x_max = max(max_value * (1 + render.X_PADDING_FRACTION), 10)
    ax.set_xlim(-(x_max * 0.02), x_max)
    ax.set_yticks(list(range(n_managers)))
    ax.set_yticklabels([])
    ax.invert_yaxis()

    for i, (fpl_name, value) in enumerate(data):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
        )

        bar_colour = render.LOSS_COLOUR if higher_is_worse else colour

        # Background track
        render.draw_bar_track(ax, y=i, width=x_max)

        # Bar
        ax.barh(
            i, value,
            height=render.BAR_HEIGHT,
            color=bar_colour,
            zorder=2,
        )

        # Value label — inside if wide enough, otherwise outside
        render.draw_segment_label(
            ax,
            x_centre=value / 2,
            y=i,
            label=str(value),
            segment_width=value,
            x_max=x_max,
        )

        # Avatar at bar tip
        render.place_avatar(ax, x=value, y=i, avatar_rgba=avatar)

        # Manager name
        render.draw_manager_label(ax, y=i, display_name=display_name,
                                  x_offset=-(x_max * 0.02))

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Wins / losses / mid stacked bar
# ---------------------------------------------------------------------------

def render_wins_losses_bar(
    wins_losses: Dict[ManagerName, Dict[str, int]],
    total_gameweeks: int,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a fixed-width stacked bar showing wins, mid-table, and losses
    per manager, sorted by wins descending.

    Each bar spans exactly `total_gameweeks` wide, divided into three
    segments: wins (manager colour), mid (dark muted), losses (red).
    The fixed total width means all bars are the same length, making
    the background track redundant — we use it anyway for visual
    consistency with the other charts.

    Args:
        wins_losses:      Output of calculate_weekly_wins_losses —
                          {fpl_name: {'wins': int, 'losses': int, 'mid': int}}
        total_gameweeks:  Total gameweeks in the analysis, used as bar width.
        config:           League config.
        output_path:      Destination PNG path.
    """
    if not wins_losses:
        return

    # Sort by wins descending, losses ascending as tiebreaker
    sorted_managers = sorted(
        wins_losses.items(),
        key=lambda item: (item[1]["wins"], -item[1]["losses"]),
        reverse=True,
    )

    n_managers = len(sorted_managers)
    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(
        fig, ax,
        title="Gameweek Wins & Losses",
        xlabel="Gameweeks",
        subtitle=subtitle,
    )

    x_max = total_gameweeks * (1 + render.X_PADDING_FRACTION)
    ax.set_xlim(-(x_max * 0.02), x_max)
    ax.set_yticks(list(range(n_managers)))
    ax.set_yticklabels([])
    ax.invert_yaxis()

    # Integer ticks only — gameweeks are whole numbers
    ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))

    for i, (fpl_name, counts) in enumerate(sorted_managers):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
        )

        wins   = counts["wins"]
        mid    = counts["mid"]
        losses = counts["losses"]

        render.draw_bar_track(ax, y=i, width=x_max)

        left = 0.0

        # Wins segment
        if wins > 0:
            ax.barh(i, wins, left=left, height=render.BAR_HEIGHT,
                    color=colour, zorder=2)
            render.draw_segment_label(
                ax, x_centre=left + wins / 2, y=i,
                label=f"{wins}W",
                segment_width=wins, x_max=x_max,
            )
            left += wins

        # Mid segment
        if mid > 0:
            ax.barh(i, mid, left=left, height=render.BAR_HEIGHT,
                    color=render.MID_COLOUR, zorder=2)
            render.draw_segment_label(
                ax, x_centre=left + mid / 2, y=i,
                label=f"{mid}",
                segment_width=mid, x_max=x_max,
            )
            left += mid

        # Losses segment
        if losses > 0:
            ax.barh(i, losses, left=left, height=render.BAR_HEIGHT,
                    color=render.LOSS_COLOUR, zorder=2)
            render.draw_segment_label(
                ax, x_centre=left + losses / 2, y=i,
                label=f"{losses}L",
                segment_width=losses, x_max=x_max,
            )
            left += losses

        # Avatar sits at total_gameweeks (all bars same total width)
        render.place_avatar(ax, x=total_gameweeks, y=i, avatar_rgba=avatar)
        render.draw_manager_label(ax, y=i, display_name=display_name,
                                  x_offset=-(x_max * 0.02))

    # Legend
    legend_handles = [
        mpatches.Patch(color=render.WIN_COLOUR,  label="Win"),
        mpatches.Patch(color=render.MID_COLOUR,  label="Mid-table"),
        mpatches.Patch(color=render.LOSS_COLOUR, label="Loss"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        framealpha=0.15,
        facecolor=render.SURFACE,
        edgecolor=render.AXIS_LINE,
        labelcolor=render.TEXT_PRIMARY,
        fontsize=9,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Positional breakdown grouped bar
# ---------------------------------------------------------------------------

def render_position_breakdown(
    position_data: Dict[str, list],
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a grouped horizontal bar chart showing defence, midfield, and
    attack points per manager, sorted by total positional points descending.

    Each manager gets three narrow bars stacked vertically within their row,
    colour-coded by position rather than manager colour to make cross-manager
    comparison easy.

    Args:
        position_data: Output of calculate_best_position_scores —
                       {'defence': [(name, pts), ...],
                        'midfield': [(name, pts), ...],
                        'attack':   [(name, pts), ...]}
        config:        League config.
        output_path:   Destination PNG path.
    """
    if not any(position_data.values()):
        return

    # Merge into a per-manager dict
    manager_totals: Dict[str, Dict[str, int]] = {}
    for position in ("defence", "midfield", "attack"):
        for name, pts in position_data.get(position, []):
            manager_totals.setdefault(name, {"defence": 0, "midfield": 0, "attack": 0})
            manager_totals[name][position] = pts

    # Sort by total descending
    sorted_managers = sorted(
        manager_totals.items(),
        key=lambda item: sum(item[1].values()),
        reverse=True,
    )

    n_managers = len(sorted_managers)
    if n_managers == 0:
        return

    # Three narrow bars per manager row
    group_height = render.BAR_HEIGHT
    bar_h = group_height / 3
    offsets = [bar_h, 0, -bar_h]  # defence top, midfield middle, attack bottom

    DEFENCE_COLOUR  = "#4ecdc4"   # teal
    MIDFIELD_COLOUR = "#ffe66d"   # yellow
    ATTACK_COLOUR   = "#ff6b6b"   # coral

    position_colours = {
        "defence":  DEFENCE_COLOUR,
        "midfield": MIDFIELD_COLOUR,
        "attack":   ATTACK_COLOUR,
    }

    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(
        fig, ax,
        title="Points by Position",
        xlabel="Points",
        subtitle=subtitle,
    )

    max_any = max(
        pts
        for _, totals in sorted_managers
        for pts in totals.values()
    ) if sorted_managers else 1
    x_max = max_any * (1 + render.X_PADDING_FRACTION)
    ax.set_xlim(-(x_max * 0.02), x_max)
    ax.set_yticks(list(range(n_managers)))
    ax.set_yticklabels([])
    ax.invert_yaxis()

    for i, (fpl_name, totals) in enumerate(sorted_managers):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
        )

        best_position_pts = max(totals.values())

        for position, offset in zip(("defence", "midfield", "attack"), offsets):
            pts = totals[position]
            bar_colour = position_colours[position]

            ax.barh(
                i + offset, pts,
                height=bar_h * 0.85,
                color=bar_colour,
                zorder=2,
                alpha=0.9,
            )

        # Avatar at the widest of the three bars
        render.place_avatar(ax, x=best_position_pts, y=i, avatar_rgba=avatar)
        render.draw_manager_label(ax, y=i, display_name=display_name,
                                  x_offset=-(x_max * 0.02))

    # Legend
    legend_handles = [
        mpatches.Patch(color=DEFENCE_COLOUR,  label="Defence (GK + DEF)"),
        mpatches.Patch(color=MIDFIELD_COLOUR, label="Midfield"),
        mpatches.Patch(color=ATTACK_COLOUR,   label="Attack"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        framealpha=0.15,
        facecolor=render.SURFACE,
        edgecolor=render.AXIS_LINE,
        labelcolor=render.TEXT_PRIMARY,
        fontsize=9,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Consistency bar chart
# ---------------------------------------------------------------------------

def render_consistency_bar(
    consistency: Dict[ManagerName, Dict[str, float]],
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a bar chart showing scoring consistency per manager.

    Each manager gets:
      - A bar of length equal to their mean weekly score (manager colour)
      - A horizontal range line from their lowest to highest single GW score,
        overlaid on the bar, in white at low opacity
      - A small dot marker at both the low and high extremes

    Sorted by standard deviation ascending (most consistent at top).

    Args:
        consistency: Output of calculate_score_consistency —
                     {fpl_name: {'mean': float, 'std': float,
                                 'high': float, 'low': float, 'range': float}}
        config:      League config.
        output_path: Destination PNG path.
    """
    if not consistency:
        return

    # Sort by std ascending — most consistent (lowest std) at the top
    sorted_managers = sorted(
        consistency.items(),
        key=lambda item: item[1]["std"],
    )

    n_managers = len(sorted_managers)
    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(
        fig, ax,
        title="Scoring Consistency",
        xlabel="Points",
        subtitle=subtitle,
    )

    max_high = max(v["high"] for _, v in sorted_managers) if sorted_managers else 1
    x_max = max_high * (1 + render.X_PADDING_FRACTION)
    ax.set_xlim(-(x_max * 0.02), x_max)
    ax.set_yticks(list(range(n_managers)))
    ax.set_yticklabels([])
    ax.invert_yaxis()

    for i, (fpl_name, stats) in enumerate(sorted_managers):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
        )

        mean  = stats["mean"]
        high  = stats["high"]
        low   = stats["low"]
        std   = stats["std"]

        render.draw_bar_track(ax, y=i, width=x_max)

        # Mean bar
        ax.barh(
            i, mean,
            height=render.BAR_HEIGHT,
            color=colour,
            zorder=2,
        )

        # High/low range line overlaid across the bar
        ax.plot(
            [low, high], [i, i],
            color="white",
            linewidth=2,
            alpha=0.4,
            zorder=3,
            solid_capstyle="round",
        )

        # Dot markers at extremes
        ax.plot(
            [low, high], [i, i],
            "o",
            color="white",
            markersize=5,
            alpha=0.7,
            zorder=4,
        )

        # Std deviation annotation to the right of the bar
        ax.text(
            mean + x_max * 0.01, i,
            f"SD {std:.1f}",
            va="center",
            ha="left",
            color=render.TEXT_SECONDARY,
            fontsize=8,
            zorder=5,
        )

        render.place_avatar(ax, x=mean, y=i, avatar_rgba=avatar)
        render.draw_manager_label(ax, y=i, display_name=display_name,
                                  x_offset=-(x_max * 0.02))

    # Subtitle explaining the range line
    fig.text(
        0.04, 0.02,
        "Bar = mean score  ·  Line = best to worst single gameweek  ·  SD = standard deviation",
        color=render.TEXT_MUTED,
        fontsize=8,
        va="bottom",
        transform=fig.transFigure,
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.93])
    render.save_figure(fig, output_path)
