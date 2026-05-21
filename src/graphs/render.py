"""
Shared Rendering Utilities

Provides avatar loading, chart styling constants, and common matplotlib helpers
used across all chart types. Every chart module imports from here to ensure a
consistent visual language.

Outfit font files must be present at:
    src/graphs/fonts/Outfit-Regular.ttf
    src/graphs/fonts/Outfit-Bold.ttf

Download from https://fonts.google.com/specimen/Outfit (OFL licence).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.figure
import matplotlib.axes
import numpy as np
from matplotlib import font_manager
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Font registration
# ---------------------------------------------------------------------------

_FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_REGULAR = _FONTS_DIR / "Outfit-Regular.ttf"
_FONT_BOLD = _FONTS_DIR / "Outfit-Bold.ttf"

def _register_fonts() -> str:
    """
    Register Outfit fonts with matplotlib if available.
    Returns the font family name to use in rcParams.
    Falls back to sans-serif if font files are missing.
    """
    if _FONT_REGULAR.exists() and _FONT_BOLD.exists():
        font_manager.fontManager.addfont(str(_FONT_REGULAR))
        font_manager.fontManager.addfont(str(_FONT_BOLD))
        return "Outfit"
    else:
        print(
            "Warning: Outfit font files not found in "
            f"{_FONTS_DIR}\n"
            "  Download from https://fonts.google.com/specimen/Outfit\n"
            "  Falling back to system sans-serif."
        )
        return "sans-serif"

_FONT_FAMILY = _register_fonts()

plt.rcParams.update({
    "font.family": _FONT_FAMILY,
    "font.size": 11,
})


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BACKGROUND     = "#0f1923"   # very dark blue-black — canvas colour
SURFACE        = "#1c2b3a"   # slightly lighter — bar tracks, card backgrounds
ACCENT         = "#00d4aa"   # teal/mint — titles and highlights
TEXT_PRIMARY   = "#f0f4f8"   # near-white — axis labels, values
TEXT_SECONDARY = "#7a8fa6"   # muted blue-grey — annotations, subtitles
TEXT_MUTED     = "#3d5166"   # very muted — "unused" labels, grid

GRID           = "#1e3048"   # subtle grid lines
AXIS_LINE      = "#2a4060"   # axis spines

WIN_COLOUR     = "#2ecc71"   # green — gameweek wins
LOSS_COLOUR    = "#e74c3c"   # red — gameweek losses
MID_COLOUR     = "#2a4060"   # dark — mid-table finishes

BAR_TRACK      = SURFACE     # grey background track behind every bar


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

FIGURE_DPI      = 150
FIGURE_WIDTH    = 14         # inches — consistent across all bar charts
ROW_HEIGHT      = 0.9        # inches per manager row for bar charts
ROW_PADDING     = 0.9        # extra inches for title + axis
BAR_HEIGHT      = 0.55       # fraction of row height used by the bar itself

AVATAR_SIZE_BAR  = 80        # px — avatar on bar chart tip
AVATAR_SIZE_LINE = 52        # px — avatar on line chart endpoint
AVATAR_ZOOM_BAR  = 0.37      # OffsetImage zoom for bar charts
AVATAR_ZOOM_LINE = 0.27      # OffsetImage zoom for line charts

LINE_WIDTH      = 2.5
GLOW_WIDTH      = 8
GLOW_ALPHA      = 0.18

# How far right to extend the x-axis beyond the longest bar,
# expressed as a fraction of the max value. This leaves room for
# the avatar to sit at the bar tip without clipping.
X_PADDING_FRACTION = 0.13


# ---------------------------------------------------------------------------
# Avatar helpers
# ---------------------------------------------------------------------------

def load_avatar(
    path: Optional[Path],
    display_name: str,
    colour: str,
    size: int = AVATAR_SIZE_BAR,
) -> np.ndarray:
    """
    Load a circular avatar image as an RGBA numpy array.

    If `path` is None or the file can't be opened, falls back to a filled
    circle in `colour` with the manager's initials in white.

    Args:
        path:         Absolute path to an image file, or None.
        display_name: Used to generate initials for the fallback avatar.
        colour:       Hex colour string for the fallback circle.
        size:         Output size in pixels (square).

    Returns:
        RGBA numpy array of shape (size, size, 4).
    """
    img: Optional[Image.Image] = None

    if path is not None:
        try:
            img = Image.open(path).convert("RGBA").resize(
                (size, size), Image.LANCZOS
            )
        except Exception as e:
            print(f"Warning: could not load avatar from {path}: {e}")
            img = None

    if img is None:
        img = _make_initials_avatar(display_name, colour, size)

    return _apply_circular_mask(img)


def _make_initials_avatar(
    display_name: str,
    colour: str,
    size: int,
) -> Image.Image:
    """
    Create a solid-colour circle with up to two initials centred on it.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Filled circle
    draw.ellipse([0, 0, size - 1, size - 1], fill=colour)

    # Initials
    words = display_name.split()
    initials = "".join(w[0].upper() for w in words[:2])

    # Attempt to use the bundled font for initials; fall back to PIL default
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont
    font_size = int(size * 0.38)
    if _FONT_BOLD.exists():
        try:
            font = ImageFont.truetype(str(_FONT_BOLD), font_size)
        except Exception:
            font = ImageFont.load_default()
    else:
        font = ImageFont.load_default()

    draw.text(
        (size / 2, size / 2),
        initials,
        font=font,
        anchor="mm",
        fill="#ffffff",
    )

    return img


def _apply_circular_mask(img: Image.Image) -> np.ndarray:
    """
    Apply a circular alpha mask to an RGBA image, making corners transparent.
    Returns an RGBA numpy array.
    """
    img = img.convert("RGBA")
    size = img.size[0]

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size - 1, size - 1], fill=255)

    img.putalpha(mask)
    return np.array(img)


def place_avatar(
    ax: matplotlib.axes.Axes,
    x: float,
    y: float,
    avatar_rgba: np.ndarray,
    zoom: float = AVATAR_ZOOM_BAR,
) -> None:
    """
    Place a circular avatar image centred on the data coordinate (x, y).

    The centre of the image is pinned to (x, y) via box_alignment=(0.5, 0.5),
    which means a zero-value bar will show the avatar half-overlapping the
    y-axis, and a non-zero bar will show it sitting at the bar's right tip.

    Args:
        ax:          The matplotlib Axes to draw on.
        x:           Data x-coordinate (bar value, or line chart x position).
        y:           Data y-coordinate (bar index, or line chart y position).
        avatar_rgba: RGBA numpy array from load_avatar().
        zoom:        OffsetImage zoom factor. Use AVATAR_ZOOM_BAR for bar
                     charts and AVATAR_ZOOM_LINE for line charts.
    """
    imagebox = OffsetImage(avatar_rgba, zoom=zoom)
    imagebox.image.axes = ax
    ab = AnnotationBbox(
        imagebox,
        (x, y),
        frameon=False,
        box_alignment=(0.5, 0.5),
        pad=0,
        zorder=10,
    )
    ax.add_artist(ab)


# ---------------------------------------------------------------------------
# Colour utilities
# ---------------------------------------------------------------------------

def lighten(hex_colour: str, amount: float) -> str:
    """
    Lighten a hex colour by blending it toward white.

    Args:
        hex_colour: Hex string like '#e63946'.
        amount:     0.0 = no change, 1.0 = pure white.

    Returns:
        Lightened hex string.
    """
    stripped = hex_colour.lstrip("#")
    r, g, b = (int(stripped[i:i+2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def darken(hex_colour: str, amount: float) -> str:
    """
    Darken a hex colour by blending it toward black.

    Args:
        hex_colour: Hex string like '#e63946'.
        amount:     0.0 = no change, 1.0 = pure black.

    Returns:
        Darkened hex string.
    """
    stripped = hex_colour.lstrip("#")
    r, g, b = (int(stripped[i:i+2], 16) for i in (0, 2, 4))
    r = int(r * (1 - amount))
    g = int(g * (1 - amount))
    b = int(b * (1 - amount))
    return f"#{r:02x}{g:02x}{b:02x}"


def with_alpha(hex_colour: str, alpha: float) -> tuple[float, float, float, float]:
    """
    Convert a hex colour to an RGBA tuple for matplotlib.

    Args:
        hex_colour: Hex string like '#e63946'.
        alpha:      0.0 = transparent, 1.0 = opaque.

    Returns:
        (r, g, b, a) tuple with values in [0, 1].
    """
    stripped = hex_colour.lstrip("#")
    r, g, b = (int(stripped[i:i+2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b, alpha)


# ---------------------------------------------------------------------------
# Figure / axes helpers
# ---------------------------------------------------------------------------

def make_bar_figure(n_rows: int) -> tuple[matplotlib.figure.Figure, matplotlib.axes.Axes]:
    """
    Create a consistently-sized figure for horizontal bar charts.

    Height scales with the number of manager rows, ensuring bars always
    appear at the same visual weight regardless of league size.

    Args:
        n_rows: Number of manager rows (bars).

    Returns:
        (fig, ax) tuple ready for bar chart rendering.
    """
    fig_height = n_rows * ROW_HEIGHT + ROW_PADDING
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, fig_height))
    return fig, ax


def apply_bar_style(
    fig: matplotlib.figure.Figure,
    ax: matplotlib.axes.Axes,
    title: str,
    xlabel: str = "Points",
    subtitle: Optional[str] = None,
) -> None:
    """
    Apply the standard dark style to a horizontal bar chart.

    Removes top/right/left spines, adds a subtle horizontal grid,
    styles tick labels, and draws the chart title in the accent colour.

    Args:
        fig:      The Figure to style.
        ax:       The Axes to style.
        title:    Chart title — displayed top-left in accent colour.
        xlabel:   X-axis label.
        subtitle: Optional secondary line beneath the title (e.g. league + GW range),
                  rendered in TEXT_SECONDARY.
    """
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)

    # Spines — keep only the bottom axis line
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(AXIS_LINE)

    # Grid — horizontal lines only, behind bars
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=GRID, linewidth=0.5, alpha=0.6)
    ax.yaxis.grid(False)

    # Tick styling
    ax.tick_params(axis="x", colors=TEXT_SECONDARY, labelsize=10)
    ax.tick_params(axis="y", left=False, labelsize=10)

    # X label
    ax.set_xlabel(xlabel, color=TEXT_SECONDARY, fontsize=10, labelpad=8)

    # Title — top-left in accent colour, in figure coordinates so it sits
    # above the axes area and is consistent regardless of subplot layout
    fig.text(
        0.04, 0.97,
        title,
        color=ACCENT,
        fontsize=15,
        fontweight="bold",
        va="top",
        transform=fig.transFigure,
    )

    if subtitle:
        fig.text(
            0.04, 0.94,
            subtitle,
            color=TEXT_SECONDARY,
            fontsize=10,
            va="top",
            transform=fig.transFigure,
        )


def apply_line_style(
    fig: matplotlib.figure.Figure,
    ax: matplotlib.axes.Axes,
    title: str,
    ylabel: str = "",
    subtitle: Optional[str] = None,
) -> None:
    """
    Apply the standard dark style to a line (time series) chart.

    Args:
        fig:      The Figure to style.
        ax:       The Axes to style.
        title:    Chart title — displayed top-left in accent colour.
        ylabel:   Y-axis label.
        subtitle: Optional secondary line beneath the title (e.g. league + GW range),
                  rendered in TEXT_SECONDARY.
    """
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(AXIS_LINE)
    ax.spines["bottom"].set_color(AXIS_LINE)

    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.5, alpha=0.6)
    ax.xaxis.grid(False)

    ax.tick_params(axis="x", colors=TEXT_SECONDARY, labelsize=10)
    ax.tick_params(axis="y", colors=TEXT_SECONDARY, labelsize=10)

    ax.set_xlabel("Gameweek", color=TEXT_SECONDARY, fontsize=10, labelpad=8)
    ax.set_ylabel(ylabel, color=TEXT_SECONDARY, fontsize=10, labelpad=8)

    fig.text(
        0.04, 0.97,
        title,
        color=ACCENT,
        fontsize=15,
        fontweight="bold",
        va="top",
        transform=fig.transFigure,
    )

    if subtitle:
        fig.text(
            0.04, 0.94,
            subtitle,
            color=TEXT_SECONDARY,
            fontsize=10,
            va="top",
            transform=fig.transFigure,
        )


def save_figure(
    fig: matplotlib.figure.Figure,
    output_path: Path,
) -> None:
    """
    Save a figure to disk and close it to free memory.

    Args:
        fig:         The Figure to save.
        output_path: Destination path (should end in .png).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=FIGURE_DPI,
        bbox_inches="tight",
        facecolor=BACKGROUND,
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Bar chart drawing helpers
# Shared by chips.py, bars.py — called once per manager row
# ---------------------------------------------------------------------------

def draw_bar_track(
    ax: matplotlib.axes.Axes,
    y: float,
    width: float,
) -> None:
    """
    Draw the grey background track behind a manager's bar.

    The track extends to `width` (the maximum x value on this chart),
    giving every manager — including those with zero values — a visible
    "lane". This makes empty bars immediately readable as unused rather
    than missing.

    Args:
        ax:    The Axes to draw on.
        y:     The bar's y-position (manager row index).
        width: How far the track extends (typically x_max for this chart).
    """
    ax.barh(
        y, width,
        height=BAR_HEIGHT,
        color=BAR_TRACK,
        zorder=1,
        left=0,
    )


def draw_manager_label(
    ax: matplotlib.axes.Axes,
    y: float,
    display_name: str,
    x_offset: float,
) -> None:
    """
    Draw the manager's display name to the left of the y-axis.

    Args:
        ax:           The Axes to draw on.
        y:            The bar's y-position (manager row index).
        display_name: Short name from ManagerConfig.
        x_offset:     Negative x value in data coordinates — typically
                      -(x_max * 0.02) so the label sits just outside the axis.
    """
    ax.text(
        x_offset, y,
        display_name,
        va="center",
        ha="right",
        color=TEXT_PRIMARY,
        fontsize=10,
        fontweight="bold",
        zorder=5,
    )


def draw_segment_label(
    ax: matplotlib.axes.Axes,
    x_centre: float,
    y: float,
    label: str,
    segment_width: float,
    x_max: float,
) -> None:
    """
    Draw a label inside a bar segment, or outside if the segment is too narrow.

    Labels inside segments use white bold text. If the segment is too narrow
    to fit the label comfortably, the label is placed just to the right of
    the segment end in TEXT_SECONDARY.

    Args:
        ax:            The Axes to draw on.
        x_centre:      Centre x-coordinate of the segment.
        y:             Bar y-position (manager row index).
        label:         Text to render.
        segment_width: Width of the segment in data units.
        x_max:         Chart x-axis maximum, used to determine "narrow" threshold.
    """
    min_width_for_inside = x_max * 0.12

    if segment_width >= min_width_for_inside:
        ax.text(
            x_centre, y,
            label,
            va="center",
            ha="center",
            color="white",
            fontsize=8,
            fontweight="bold",
            zorder=6,
            clip_on=True,
        )
    else:
        # Place outside the segment, to the right
        ax.text(
            x_centre + segment_width / 2 + x_max * 0.01, y,
            label,
            va="center",
            ha="left",
            color=TEXT_SECONDARY,
            fontsize=8,
            zorder=6,
            clip_on=True,
        )
