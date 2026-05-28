"""
Legend / Cover Sheet

Renders the introductory chart for a season's set of PNGs: large league
name, season + gameweek-range subtitle, and one row per manager showing
their avatar, display name, FPL name, and colour swatch.

Shares the visual language of the rest of the chart suite (dark surface,
mint accent, Outfit font, circular avatars) so it slots in as the first
PNG when sharing a folder.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from ..config import LeagueConfig
from .. import render


# ---------------------------------------------------------------------------
# Season derivation
# ---------------------------------------------------------------------------

def _derive_season(now: Optional[datetime] = None) -> str:
    """
    Derive a season label like "2025/26" from the current date.

    Premier League seasons run roughly August → May. We treat month >= 7
    as the start of a new season; earlier months belong to the season that
    began in the previous calendar year.

    Args:
        now: Override for "current" datetime — injection point for tests.

    Returns:
        Season label, e.g. "2025/26".
    """
    if now is None:
        now = datetime.now()

    if now.month >= 7:
        start_year = now.year
    else:
        start_year = now.year - 1

    return f"{start_year}/{(start_year + 1) % 100:02d}"


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

_HEADER_HEIGHT_IN = 2.4         # inches reserved for league name + subtitle
_ROW_HEIGHT_IN = 0.9            # inches per manager row
_BOTTOM_PADDING_IN = 0.4

_SWATCH_WIDTH = 0.08            # axis-fraction width of colour swatch
_SWATCH_HEIGHT = 0.55           # row-fraction height of swatch
_AVATAR_X = 0.04                # axis-fraction x of avatar centre
_TEXT_X = 0.10                  # axis-fraction x of display_name
_SWATCH_X = 0.88                # axis-fraction x of left edge of swatch


# ---------------------------------------------------------------------------
# Public renderer
# ---------------------------------------------------------------------------

def render_legend(
    config: LeagueConfig,
    league_name: str,
    gameweek_range: Tuple[int, int],
    season: Optional[str],
    output_path: Path,
) -> None:
    """
    Render the cover-sheet legend PNG for a league.

    Args:
        config:         Loaded LeagueConfig; managers are rendered
                        alphabetically by display_name (see below).
        league_name:    Display name for the league (typically the config
                        override, or the FPL API name as a fallback).
        gameweek_range: (first_gw, last_gw) inclusive.
        season:         Season label like "2025/26"; derived from today's
                        date if None.
        output_path:    Destination PNG path.
    """
    if season is None:
        season = _derive_season()

    first_gw, last_gw = gameweek_range

    n_rows = max(len(config.managers), 1)
    fig_height = _HEADER_HEIGHT_IN + n_rows * _ROW_HEIGHT_IN + _BOTTOM_PADDING_IN
    fig, ax = plt.subplots(figsize=(render.FIGURE_WIDTH, fig_height))

    fig.patch.set_facecolor(render.BACKGROUND)
    ax.set_facecolor(render.BACKGROUND)

    # Axes occupy the full figure; we'll work entirely in axes-fraction
    # coordinates for predictable placement.
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_axis_off()

    # Header — league name + subtitle. Coordinates in figure space so the
    # block stays at a fixed inch-height regardless of row count.
    header_top_y = 1 - (0.55 / fig_height)
    fig.text(
        0.06, header_top_y,
        league_name,
        color=render.ACCENT,
        fontsize=40,
        fontweight="bold",
        va="top",
        transform=fig.transFigure,
    )
    subtitle = f"Season {season}  ·  Gameweeks {first_gw}–{last_gw}"
    fig.text(
        0.06, header_top_y - (0.85 / fig_height),
        subtitle,
        color=render.TEXT_SECONDARY,
        fontsize=14,
        va="top",
        transform=fig.transFigure,
    )

    # Body region in figure-fraction space: starts below the header.
    body_top = 1 - (_HEADER_HEIGHT_IN / fig_height)
    body_bottom = _BOTTOM_PADDING_IN / fig_height
    body_height = body_top - body_bottom

    # Match axes to the body region so axes-fraction maps cleanly to rows.
    ax.set_position([0.04, body_bottom, 0.92, body_height])

    if not config.managers:
        ax.text(
            0.5, 0.5,
            "No managers configured",
            color=render.TEXT_SECONDARY,
            fontsize=12,
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        render.save_figure(fig, output_path)
        return

    row_count = len(config.managers)
    row_height = 1.0 / row_count

    sorted_managers = sorted(
        config.managers, key=lambda m: m.display_name.casefold()
    )
    for i, manager in enumerate(sorted_managers):
        # Rows render top-to-bottom: index 0 is the top row.
        row_centre_y = 1.0 - (i + 0.5) * row_height

        avatar = render.load_avatar(
            manager.avatar_path,
            manager.display_name,
            manager.colour,
            size=render.AVATAR_PHOTO_PX_LEGEND,
        )
        render.place_avatar_ringed(
            ax,
            x=_AVATAR_X,
            y=row_centre_y,
            avatar_rgba=avatar,
            ring_colour=manager.colour,
            diameter_pt=render.AVATAR_DIAMETER_PT_LEGEND,
            ring_width_pt=render.AVATAR_RING_WIDTH_PT_LEGEND,
        )

        ax.text(
            _TEXT_X, row_centre_y + row_height * 0.10,
            manager.display_name,
            va="center",
            ha="left",
            color=render.TEXT_PRIMARY,
            fontsize=14,
            fontweight="bold",
            transform=ax.transAxes,
        )
        ax.text(
            _TEXT_X, row_centre_y - row_height * 0.22,
            manager.fpl_name,
            va="center",
            ha="left",
            color=render.TEXT_SECONDARY,
            fontsize=10,
            transform=ax.transAxes,
        )

        swatch = mpatches.FancyBboxPatch(
            (_SWATCH_X, row_centre_y - row_height * _SWATCH_HEIGHT / 2),
            _SWATCH_WIDTH,
            row_height * _SWATCH_HEIGHT,
            boxstyle="round,pad=0,rounding_size=0.015",
            linewidth=0,
            facecolor=manager.colour,
            transform=ax.transAxes,
            zorder=5,
        )
        ax.add_patch(swatch)

    render.save_figure(fig, output_path)
