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
from matplotlib import font_manager, ticker
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

# --- Vector-ring avatars (place_avatar_ringed) -----------------------------
# The coloured border is drawn as a scatter marker in points space rather than
# baked into the raster, so its edge is rasterised crisply at output DPI and
# never shows resampling stair-stepping. Sizes are in points (DPI-independent):
# the on-screen diameter is `diameter_pt` regardless of FIGURE_DPI.
#
# The bar-tip outer diameter matches the old raster avatar (92 px * 0.37 zoom
# ≈ 34 pt) so layout/label clearance is unchanged. The photo bitmap is rendered
# well above its ~62 px displayed size so matplotlib always downsamples it.
AVATAR_DIAMETER_PT_BAR   = 34.0   # outer ring diameter on bar charts, in points
AVATAR_RING_WIDTH_PT_BAR = 3.0    # ring stroke thickness, in points
AVATAR_PHOTO_PX_BAR      = 128    # photo bitmap resolution for ringed bar avatars

# Line-chart avatars are smaller (52 px * 0.27 zoom ≈ 14 pt under the old
# baked-border path). The photo bitmap (~24 px displayed) is rendered well
# above that so matplotlib downsamples it.
AVATAR_DIAMETER_PT_LINE   = 14.0
AVATAR_RING_WIDTH_PT_LINE = 2.0
AVATAR_PHOTO_PX_LINE      = 64

# Legend cover-sheet avatars are the largest (80 px * 0.518 zoom ≈ 41 pt) and,
# under the old path, the only ones matplotlib upscaled. The 160 px photo
# bitmap now downsamples to ~74 px displayed.
AVATAR_DIAMETER_PT_LEGEND   = 41.0
AVATAR_RING_WIDTH_PT_LEGEND = 3.5
AVATAR_PHOTO_PX_LEGEND      = 160

# Approx half-width of a bar-tip avatar, expressed as a fraction of x_max.
# Used to position labels past the avatar that would otherwise sit under it.
# Empirical — tuned to clear an AVATAR_DIAMETER_PT_BAR-wide avatar.
AVATAR_HALF_WIDTH_FRACTION = 0.025

# A bar segment must be at least this fraction of x_max to hold its label
# inside; narrower segments have their label drawn externally instead.
SEGMENT_LABEL_MIN_WIDTH_FRACTION = 0.12

LINE_WIDTH      = 2.5
GLOW_WIDTH      = 5
GLOW_ALPHA      = 0.10

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
    size: int = AVATAR_PHOTO_PX_BAR,
) -> np.ndarray:
    """
    Load a circular avatar photo as an RGBA numpy array, with no border.

    If `path` is None or the file can't be opened, falls back to a filled
    circle in `colour` with the manager's initials in white. The coloured
    border is drawn separately as a vector ring by `place_avatar_ringed`.

    Args:
        path:          Absolute path to an image file, or None.
        display_name:  Used to generate initials for the fallback avatar.
        colour:        Hex colour string for the fallback circle.
        size:          Output size in pixels (square).

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

    return np.array(_apply_circular_mask(img))


def _lighten_colour(hex_colour: str, factor: float = 0.65) -> str:
    """Blend a hex colour toward white by `factor` (0 = unchanged, 1 = white)."""
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i:i+2], 16) for i in (0, 2, 4))
    r = round(r + (255 - r) * factor)
    g = round(g + (255 - g) * factor)
    b = round(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _make_initials_avatar(
    display_name: str,
    colour: str,
    size: int,
) -> Image.Image:
    """
    Create a solid-colour square with up to two initials centred on it.

    The square is later clipped to a circle by `_apply_circular_mask`. The
    full-square fill (rather than an `ellipse` fill) ensures the anti-aliased
    mask edge has solid colour to blend into instead of transparent corners.
    """
    bg_colour = _lighten_colour(colour)
    img = Image.new("RGBA", (size, size), bg_colour)
    draw = ImageDraw.Draw(img)

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
        fill=colour,
    )

    return img


def _apply_circular_mask(img: Image.Image) -> Image.Image:
    """
    Apply a circular alpha mask to an RGBA image, making corners transparent.

    The mask is rendered at 4x size and downsampled with LANCZOS so the
    visible circle edge is anti-aliased. The caller is expected to have
    filled the underlying RGB to the image edges (not just inside the
    circle) so the anti-aliased band blends with solid colour rather than
    bleeding through to transparent pixels.
    """
    img = img.convert("RGBA")
    size = img.size[0]

    ss = 4
    mask = Image.new("L", (size * ss, size * ss), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse([0, 0, size * ss - 1, size * ss - 1], fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)

    img.putalpha(mask)
    return img


def place_avatar_ringed(
    ax: matplotlib.axes.Axes,
    x: float,
    y: float,
    avatar_rgba: np.ndarray,
    ring_colour: str,
    *,
    diameter_pt: float,
    ring_width_pt: float,
    photo_overlap_pt: float = 1.5,
    zorder: float = 10,
) -> None:
    """
    Place a circular avatar with a crisp vector ring as its border.

    The ring is a scatter marker drawn in points space rather than baked into
    the bitmap. It stays perfectly circular regardless of axis scaling and is
    rasterised at output DPI, so its edge never shows the resampling
    stair-stepping a baked-in raster border does.

    The photo is sized to tuck its own (resampled) circular edge just under the
    ring's inner stroke, so the only visible geometry is the two sharp vector
    edges of the ring.

    Args:
        ax:               The matplotlib Axes to draw on.
        x, y:             Data coordinate for the avatar centre.
        avatar_rgba:      Circular-masked photo RGBA (no baked border), from
                          load_avatar().
        ring_colour:      Hex colour for the ring stroke.
        diameter_pt:      Outer diameter of the ring, in points (DPI-independent).
        ring_width_pt:    Ring stroke thickness, in points.
        photo_overlap_pt: How far the photo extends under the ring's inner edge.
        zorder:           Stacking order for the photo; the ring sits just above.
    """
    # scatter draws the stroke centred on a circle of diameter `marker_path_pt`,
    # so the stroke spans [path - width, path + width]/2 about that radius.
    # Choosing path = diameter - width makes the outer edge land at diameter_pt.
    marker_path_pt = diameter_pt - ring_width_pt
    inner_edge_pt = marker_path_pt - ring_width_pt
    photo_diameter_pt = inner_edge_pt + photo_overlap_pt

    bitmap_px = avatar_rgba.shape[0]
    zoom = photo_diameter_pt / bitmap_px

    imagebox = OffsetImage(avatar_rgba, zoom=zoom)
    imagebox.image.axes = ax
    ab = AnnotationBbox(
        imagebox,
        (x, y),
        frameon=False,
        box_alignment=(0.5, 0.5),
        pad=0,
        zorder=zorder,
    )
    ax.add_artist(ab)

    ax.scatter(
        [x], [y],
        s=marker_path_pt ** 2,
        facecolors="none",
        edgecolors=ring_colour,
        linewidths=ring_width_pt,
        zorder=zorder + 0.1,
    )


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
    description: Optional[str] = None,
) -> None:
    """
    Apply the standard dark style to a horizontal bar chart.

    Removes top/right/left spines, adds a subtle horizontal grid,
    styles tick labels, and draws the chart title in the accent colour.

    Args:
        fig:         The Figure to style.
        ax:          The Axes to style.
        title:       Chart title — displayed top-left in accent colour.
        xlabel:      X-axis label.
        subtitle:    Optional secondary line beneath the title (e.g. league + GW range),
                     rendered in TEXT_SECONDARY.
        description: Optional short sentence describing what the chart shows,
                     rendered top-right in TEXT_SECONDARY at modest size.
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

    # Values on these charts are always integers (points, counts, hit costs) —
    # avoid matplotlib's default 0.0/2.5/5.0 fractional ticks on small ranges.
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

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

    if description:
        fig.text(
            0.96, 0.97,
            description,
            color=TEXT_SECONDARY,
            fontsize=10,
            va="top",
            ha="right",
            transform=fig.transFigure,
        )


def apply_line_style(
    fig: matplotlib.figure.Figure,
    ax: matplotlib.axes.Axes,
    title: str,
    ylabel: str = "",
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Apply the standard dark style to a line (time series) chart.

    Args:
        fig:         The Figure to style.
        ax:          The Axes to style.
        title:       Chart title — displayed top-left in accent colour.
        ylabel:      Y-axis label.
        subtitle:    Optional secondary line beneath the title (e.g. league + GW range),
                     rendered in TEXT_SECONDARY.
        description: Optional short sentence describing what the chart shows,
                     rendered top-right in TEXT_SECONDARY at modest size.
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

    if description:
        fig.text(
            0.96, 0.97,
            description,
            color=TEXT_SECONDARY,
            fontsize=10,
            va="top",
            ha="right",
            transform=fig.transFigure,
        )


def save_figure(
    fig: matplotlib.figure.Figure,
    output_path: Path,
    tight_bbox: bool = True,
) -> None:
    """
    Save a figure to disk and close it to free memory.

    Args:
        fig:         The Figure to save.
        output_path: Destination path (should end in .png).
        tight_bbox:  When True (default) trim to a tight bounding box around
                     all drawn artists. Set False for figures with many
                     AnnotationBbox/OffsetImage artists where the tight-bbox
                     calculation balloons the saved canvas.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=FIGURE_DPI,
        bbox_inches="tight" if tight_bbox else None,
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
    if segment_label_fits(segment_width, x_max):
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
        # Place outside the segment, to the right of the bar's avatar so
        # the label doesn't sit under the avatar disc.
        segment_end = x_centre + segment_width / 2
        draw_external_segment_labels(ax, x_tip=segment_end, y=y, labels=[label], x_max=x_max)


def segment_label_fits(segment_width: float, x_max: float) -> bool:
    """True if a label fits comfortably inside a segment of this width."""
    return segment_width >= x_max * SEGMENT_LABEL_MIN_WIDTH_FRACTION


def draw_external_segment_labels(
    ax: matplotlib.axes.Axes,
    x_tip: float,
    y: float,
    labels: list[str],
    x_max: float,
) -> None:
    """
    Draw segment label(s) on one line just to the right of a bar tip.

    Used when segments are too narrow to hold their label inside. Placing them
    past the bar tip (the avatar) keeps them off neighbouring segments — narrow
    segments mean a short bar, so there's empty track to the right. Multiple
    labels are joined with a vertical-bar divider so each usage reads distinctly.

    Args:
        ax:     The Axes to draw on.
        x_tip:  Data x of the bar tip (the rightmost segment end / avatar).
        y:      Bar y-position (manager row index).
        labels: Labels to place, in chronological order.
        x_max:  Chart x-axis maximum, for avatar-clearance offset.
    """
    if not labels:
        return

    x = x_tip + x_max * (AVATAR_HALF_WIDTH_FRACTION + 0.01)
    ax.text(
        x, y,
        "   |   ".join(labels),
        va="center", ha="left",
        color=TEXT_SECONDARY, fontsize=8, zorder=6, clip_on=True,
    )
