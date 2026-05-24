"""
Chip Return Charts

Renders one horizontal stacked bar chart per chip type:
    - Bench Boost
    - Triple Captain
    - Free Hit
    - Wildcard

Each chart shows all managers sorted by total chip points descending.
Managers who never used the chip get an empty grey track with an "unused"
label. Managers who used the chip once or twice get stacked segments ordered
chronologically (earliest usage on the left).

The avatar for each manager is placed at the right tip of their bar,
centred on the bar's total value — so zero-value bars show the avatar
half-overlapping the y-axis.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ..config import LeagueConfig, ManagerConfig
from .. import render


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# Raw usage tuples as returned by calculate_best_chip_returns in stats.py:
#   Normal chips:         (manager_name, points, gameweek)
#   Triple captain:       (manager_name, points, gameweek, player_name)
RawUsage = Tuple  # kept loose — handled by reshape

# Reshaped per-manager record ready for rendering
ManagerChipRecord = dict  # see reshape_chip_data docstring for shape


# ---------------------------------------------------------------------------
# Data reshaping
# ---------------------------------------------------------------------------

def reshape_chip_data(
    raw: List[RawUsage],
    all_manager_names: List[str],
    is_triple_captain: bool = False,
) -> List[ManagerChipRecord]:
    """
    Reshape the flat chip usage list into per-manager records sorted by
    total points descending.

    Args:
        raw:               Flat list of usage tuples from calculate_best_chip_returns.
                           Normal chips:    (manager_name, points, gameweek)
                           Triple captain:  (manager_name, points, gameweek, player_name)
        all_manager_names: All managers in the league (FPL names), used to
                           ensure every manager appears even with zero usages.
        is_triple_captain: When True, each usage tuple includes a player_name
                           at index 3.

    Returns:
        List of records, one per manager, sorted by total descending:
        {
            'fpl_name': str,
            'total':    int,
            'usages':   [
                            {
                                'points':      int,
                                'gameweek':    int,
                                'player_name': str | None,  # TC only
                            },
                            ...
                        ]
                        Usages are sorted chronologically (earliest first).
        }
    """
    # Group raw usages by manager name
    by_manager: dict[str, list[dict]] = {name: [] for name in all_manager_names}

    for entry in raw:
        manager_name: str = entry[0]
        points: int = entry[1]
        gameweek: int = entry[2]
        player_name: Optional[str] = entry[3] if is_triple_captain and len(entry) > 3 else None

        if manager_name in by_manager:
            by_manager[manager_name].append({
                "points": points,
                "gameweek": gameweek,
                "player_name": player_name,
            })

    # Sort each manager's usages chronologically
    for name in by_manager:
        by_manager[name].sort(key=lambda u: u["gameweek"])

    # Build records and sort by total descending
    records: List[ManagerChipRecord] = []
    for name, usages in by_manager.items():
        total = sum(u["points"] for u in usages)
        records.append({
            "fpl_name": name,
            "total": total,
            "usages": usages,
        })

    return sorted(records, key=lambda r: r["total"], reverse=True)


# ---------------------------------------------------------------------------
# Label formatting
# ---------------------------------------------------------------------------

def _format_segment_label(
    points: int,
    gameweek: int,
    player_name: Optional[str],
) -> str:
    """
    Format the label shown inside (or beside) a bar segment.

    Normal chips:       "GW8 · 47pts"
    Triple captain:     "GW8 · Salah · 47pts"
    """
    if player_name:
        return f"GW{gameweek} · {player_name} · {points}pts"
    return f"GW{gameweek} · {points}pts"


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_chip_chart(
    chip_name: str,
    raw_data: List[RawUsage],
    all_manager_names: List[str],
    config: LeagueConfig,
    output_path: Path,
    is_triple_captain: bool = False,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a chip return chart and save it as a PNG.

    Args:
        chip_name:          Display name for this chip, e.g. "Bench Boost".
                            Used as the chart title.
        raw_data:           Flat usage list from calculate_best_chip_returns.
        all_manager_names:  All managers in the league (FPL names), determines
                            which managers appear on the chart.
        config:             League config for display names, colours, avatars.
        output_path:        Destination PNG path.
        is_triple_captain:  Pass True to include player name in segment labels.
    """
    records = reshape_chip_data(raw_data, all_manager_names, is_triple_captain)
    n_managers = len(records)

    if n_managers == 0:
        return

    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(fig, ax, title=f"Chip Returns · {chip_name}", subtitle=subtitle)

    # X axis: scale to the highest total, padded for avatar overlap
    max_total = max((r["total"] for r in records), default=1)
    # If everyone has zero (chip never used this season) use a nominal width
    x_max = max(max_total * (1 + render.X_PADDING_FRACTION), 20)
    ax.set_xlim(0, x_max)

    # Y axis: one row per manager, best at the top
    y_positions = list(range(n_managers))
    ax.set_yticks(y_positions)
    ax.set_yticklabels([])
    ax.invert_yaxis()

    for i, record in enumerate(records):
        manager_cfg = config.get_manager(record["fpl_name"])
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = (
            manager_cfg.display_name if manager_cfg else record["fpl_name"]
        )
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
            border_colour=colour,
            border_ratio=render.AVATAR_BORDER_RATIO_BAR,
        )

        # 1. Grey background track the full width of the chart
        render.draw_bar_track(ax, y=i, width=x_max)

        if record["total"] == 0:
            # Unused — muted label inside the track
            ax.text(
                x_max * 0.02, i,
                "unused",
                va="center",
                ha="left",
                color=render.TEXT_MUTED,
                fontsize=9,
                fontstyle="italic",
                zorder=3,
            )
        else:
            # 2. Stacked segments, chronologically left to right
            left = 0.0
            for j, usage in enumerate(record["usages"]):
                points: int = usage["points"]
                gameweek: int = usage["gameweek"]
                player_name: Optional[str] = usage["player_name"]

                # Second usage is slightly lightened to distinguish the two
                bar_colour = colour if j == 0 else render.lighten(colour, 0.25)

                ax.barh(
                    i, points,
                    left=left,
                    height=render.BAR_HEIGHT,
                    color=bar_colour,
                    zorder=2,
                )

                # Thin divider line between segments
                if j > 0:
                    ax.axvline(
                        left,
                        color=render.BACKGROUND,
                        linewidth=1.5,
                        zorder=3,
                        ymin=(i - render.BAR_HEIGHT / 2) / n_managers,
                        ymax=(i + render.BAR_HEIGHT / 2) / n_managers,
                    )

                label = _format_segment_label(points, gameweek, player_name)
                segment_centre = left + points / 2
                render.draw_segment_label(
                    ax,
                    x_centre=segment_centre,
                    y=i,
                    label=label,
                    segment_width=points,
                    x_max=x_max,
                )

                left += points

        # 3. Avatar centred on the bar's total value
        #    Zero-value bars: avatar centre sits on the y-axis
        render.place_avatar(ax, x=record["total"], y=i, avatar_rgba=avatar)

        # 4. Manager name to the left of the axis
        render.draw_manager_label(
            ax,
            y=i,
            display_name=display_name,
            x_offset=-(x_max * 0.02),
        )

    # Leave room on the left for manager name labels
    ax.set_xlim(-(x_max * 0.02), x_max)

    plt.tight_layout(rect=[0, 0, 1, 0.93])  # leave space for the fig.text title
    render.save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Convenience: render all four chip charts
# ---------------------------------------------------------------------------

def render_all_chip_charts(
    chip_data: dict,
    all_manager_names: List[str],
    config: LeagueConfig,
    output_dir: Path,
) -> None:
    """
    Render all four chip return charts from the output of
    calculate_best_chip_returns in stats.py.

    Output files:
        chip_bench_boost.png
        chip_triple_captain.png
        chip_free_hit.png
        chip_wildcard.png

    Args:
        chip_data:          Output of stats.calculate_best_chip_returns —
                            a dict with keys 'bench_boost', 'triple_captain',
                            'free_hit', 'wildcard'.
        all_manager_names:  All managers in the league (FPL names).
        config:             League config.
        output_dir:         Directory to write PNGs into.
    """
    chips = [
        ("bench_boost",     "Bench Boost",     False),
        ("triple_captain",  "Triple Captain",  True),
        ("free_hit",        "Free Hit",        False),
        ("wildcard",        "Wildcard",        False),
    ]

    for key, name, is_tc in chips:
        raw = chip_data.get(key, [])
        output_path = output_dir / f"chip_{key}.png"
        render_chip_chart(
            chip_name=name,
            raw_data=raw,
            all_manager_names=all_manager_names,
            config=config,
            output_path=output_path,
            is_triple_captain=is_tc,
        )
