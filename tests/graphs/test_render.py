"""
Tests for graphs/render.py

Covers pure functions (colour utilities, avatar generation) and verifies
matplotlib figure helpers run without error and produce figures with the
expected style properties.

Run with: python -m pytest src/tests/graphs/test_render.py -v
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — no display needed
import matplotlib.pyplot as plt
from PIL import Image

from src.graphs import render


# ---------------------------------------------------------------------------
# Colour utilities
# ---------------------------------------------------------------------------

class TestLighten:
    def test_no_change_at_zero(self):
        assert render.lighten("#000000", 0.0) == "#000000"

    def test_pure_white_at_one(self):
        assert render.lighten("#000000", 1.0) == "#ffffff"

    def test_lightens_red(self):
        result = render.lighten("#e63946", 0.5)
        # Result should be lighter — all channels higher than original
        orig_r = 0xe6
        result_r = int(result.lstrip("#")[:2], 16)
        assert result_r > orig_r

    def test_output_is_valid_hex(self):
        result = render.lighten("#457b9d", 0.3)
        assert result.startswith("#")
        assert len(result) == 7
        int(result.lstrip("#"), 16)  # should not raise


class TestDarken:
    def test_no_change_at_zero(self):
        assert render.darken("#ffffff", 0.0) == "#ffffff"

    def test_pure_black_at_one(self):
        assert render.darken("#ffffff", 1.0) == "#000000"

    def test_darkens_colour(self):
        result = render.darken("#e63946", 0.5)
        orig_r = 0xe6
        result_r = int(result.lstrip("#")[:2], 16)
        assert result_r < orig_r

    def test_output_is_valid_hex(self):
        result = render.darken("#457b9d", 0.3)
        assert result.startswith("#")
        assert len(result) == 7
        int(result.lstrip("#"), 16)


class TestWithAlpha:
    def test_returns_four_tuple(self):
        result = render.with_alpha("#ffffff", 1.0)
        assert len(result) == 4

    def test_white_is_1_1_1(self):
        r, g, b, a = render.with_alpha("#ffffff", 1.0)
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(1.0)
        assert b == pytest.approx(1.0)

    def test_black_is_0_0_0(self):
        r, g, b, a = render.with_alpha("#000000", 0.5)
        assert r == pytest.approx(0.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(0.5)

    def test_alpha_preserved(self):
        _, _, _, a = render.with_alpha("#e63946", 0.75)
        assert a == pytest.approx(0.75)

    def test_known_colour(self):
        # #e63946 → r=230, g=57, b=70
        r, g, b, a = render.with_alpha("#e63946", 1.0)
        assert r == pytest.approx(230 / 255)
        assert g == pytest.approx(57 / 255)
        assert b == pytest.approx(70 / 255)


# ---------------------------------------------------------------------------
# Avatar generation
# ---------------------------------------------------------------------------

class TestLoadAvatar:
    def test_returns_numpy_array(self):
        result = render.load_avatar(None, "Adam", "#e63946")
        assert isinstance(result, np.ndarray)

    def test_correct_shape_for_default_size(self):
        result = render.load_avatar(None, "Adam", "#e63946", size=80)
        assert result.shape == (80, 80, 4)  # RGBA

    def test_correct_shape_for_custom_size(self):
        result = render.load_avatar(None, "Dave", "#457b9d", size=48)
        assert result.shape == (48, 48, 4)

    def test_fallback_when_path_is_none(self):
        # Should not raise, should return a valid array
        result = render.load_avatar(None, "Adam Fish", "#e63946")
        assert result is not None
        assert result.shape[2] == 4  # RGBA

    def test_fallback_when_file_missing(self, tmp_path, capsys):
        missing = tmp_path / "ghost.png"
        result = render.load_avatar(missing, "Eve", "#2a9d8f")
        assert result is not None
        captured = capsys.readouterr()
        assert "Warning" in captured.out

    def test_loads_real_image(self, tmp_path):
        # Create a small valid PNG
        img = Image.new("RGB", (100, 100), color=(200, 100, 50))
        avatar_path = tmp_path / "avatar.png"
        img.save(avatar_path)

        result = render.load_avatar(avatar_path, "Adam", "#e63946", size=80)
        assert result.shape == (80, 80, 4)

    def test_circular_mask_applied(self):
        # Corners of a circular mask should be transparent (alpha=0)
        result = render.load_avatar(None, "A", "#e63946", size=80)
        # Top-left corner pixel should be fully transparent
        assert result[0, 0, 3] == 0

    def test_centre_is_opaque(self):
        # Centre pixel should be fully opaque
        result = render.load_avatar(None, "A", "#e63946", size=80)
        centre = 40
        assert result[centre, centre, 3] == 255


class TestMakeInitialsAvatar:
    def test_returns_pil_image(self):
        result = render._make_initials_avatar("Adam", "#e63946", 80)
        assert isinstance(result, Image.Image)

    def test_correct_size(self):
        result = render._make_initials_avatar("Dave Smith", "#457b9d", 64)
        assert result.size == (64, 64)

    def test_is_rgba(self):
        result = render._make_initials_avatar("Eve", "#2a9d8f", 80)
        assert result.mode == "RGBA"


class TestApplyCircularMask:
    def test_returns_pil_image(self):
        img = Image.new("RGBA", (80, 80), (255, 0, 0, 255))
        result = render._apply_circular_mask(img)
        assert isinstance(result, Image.Image)
        assert result.mode == "RGBA"

    def test_corners_are_transparent(self):
        img = Image.new("RGBA", (80, 80), (255, 0, 0, 255))
        result = np.array(render._apply_circular_mask(img))
        assert result[0, 0, 3] == 0      # top-left
        assert result[0, 79, 3] == 0     # top-right
        assert result[79, 0, 3] == 0     # bottom-left
        assert result[79, 79, 3] == 0    # bottom-right

    def test_centre_is_opaque(self):
        img = Image.new("RGBA", (80, 80), (255, 0, 0, 255))
        result = np.array(render._apply_circular_mask(img))
        assert result[40, 40, 3] == 255


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------

class TestMakeBarFigure:
    def test_returns_fig_and_ax(self):
        fig, ax = render.make_bar_figure(8)
        assert fig is not None
        assert ax is not None
        plt.close(fig)

    def test_figure_width_is_constant(self):
        fig, _ = render.make_bar_figure(8)
        assert fig.get_figwidth() == pytest.approx(render.FIGURE_WIDTH)
        plt.close(fig)

    def test_height_scales_with_rows(self):
        fig_small, _ = render.make_bar_figure(4)
        fig_large, _ = render.make_bar_figure(12)
        assert fig_large.get_figheight() > fig_small.get_figheight()
        plt.close(fig_small)
        plt.close(fig_large)


class TestApplyBarStyle:
    def setup_method(self):
        self.fig, self.ax = plt.subplots()

    def teardown_method(self):
        plt.close(self.fig)

    def test_runs_without_error(self):
        render.apply_bar_style(self.fig, self.ax, "Test Chart")

    def test_figure_background_colour(self):
        render.apply_bar_style(self.fig, self.ax, "Test Chart")
        assert self.fig.get_facecolor() == pytest.approx(
            matplotlib.colors.to_rgba(render.BACKGROUND), abs=0.01
        )

    def test_top_spine_hidden(self):
        render.apply_bar_style(self.fig, self.ax, "Test Chart")
        assert not self.ax.spines["top"].get_visible()

    def test_right_spine_hidden(self):
        render.apply_bar_style(self.fig, self.ax, "Test Chart")
        assert not self.ax.spines["right"].get_visible()

    def test_left_spine_hidden(self):
        render.apply_bar_style(self.fig, self.ax, "Test Chart")
        assert not self.ax.spines["left"].get_visible()

    def test_subtitle_rendered_when_provided(self):
        render.apply_bar_style(self.fig, self.ax, "Title", subtitle="My League · GW1–27")
        texts = [t.get_text() for t in self.fig.texts]
        assert "My League · GW1–27" in texts

    def test_no_subtitle_when_omitted(self):
        render.apply_bar_style(self.fig, self.ax, "Title")
        texts = [t.get_text() for t in self.fig.texts]
        assert texts == ["Title"]


class TestApplyLineStyle:
    def setup_method(self):
        self.fig, self.ax = plt.subplots()

    def teardown_method(self):
        plt.close(self.fig)

    def test_runs_without_error(self):
        render.apply_line_style(self.fig, self.ax, "Test Line Chart")

    def test_figure_background_colour(self):
        render.apply_line_style(self.fig, self.ax, "Test Line Chart")
        assert self.fig.get_facecolor() == pytest.approx(
            matplotlib.colors.to_rgba(render.BACKGROUND), abs=0.01
        )

    def test_top_spine_hidden(self):
        render.apply_line_style(self.fig, self.ax, "Test Line Chart")
        assert not self.ax.spines["top"].get_visible()

    def test_right_spine_hidden(self):
        render.apply_line_style(self.fig, self.ax, "Test Line Chart")
        assert not self.ax.spines["right"].get_visible()

    def test_subtitle_rendered_when_provided(self):
        render.apply_line_style(self.fig, self.ax, "Title", subtitle="My League · GW1–27")
        texts = [t.get_text() for t in self.fig.texts]
        assert "My League · GW1–27" in texts

    def test_no_subtitle_when_omitted(self):
        render.apply_line_style(self.fig, self.ax, "Title")
        texts = [t.get_text() for t in self.fig.texts]
        assert texts == ["Title"]


class TestSaveFigure:
    def test_saves_png(self, tmp_path):
        fig, ax = plt.subplots()
        ax.barh([0], [10])
        output = tmp_path / "test.png"
        render.save_figure(fig, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_creates_parent_dirs(self, tmp_path):
        fig, ax = plt.subplots()
        output = tmp_path / "nested" / "dir" / "chart.png"
        render.save_figure(fig, output)
        assert output.exists()

    def test_figure_closed_after_save(self, tmp_path):
        fig, ax = plt.subplots()
        output = tmp_path / "test.png"
        render.save_figure(fig, output)
        # plt.close() should have been called — figure should not be open
        assert fig.number not in plt.get_fignums()


# ---------------------------------------------------------------------------
# Bar drawing helpers
# ---------------------------------------------------------------------------

class TestDrawBarTrack:
    def test_runs_without_error(self):
        fig, ax = plt.subplots()
        render.draw_bar_track(ax, y=0, width=100)
        plt.close(fig)

    def test_adds_a_patch(self):
        fig, ax = plt.subplots()
        before = len(ax.patches)
        render.draw_bar_track(ax, y=0, width=100)
        assert len(ax.patches) == before + 1
        plt.close(fig)


class TestDrawManagerLabel:
    def test_runs_without_error(self):
        fig, ax = plt.subplots()
        render.draw_manager_label(ax, y=0, display_name="Adam", x_offset=-5)
        plt.close(fig)

    def test_adds_a_text_artist(self):
        fig, ax = plt.subplots()
        before = len(ax.texts)
        render.draw_manager_label(ax, y=0, display_name="Adam", x_offset=-5)
        assert len(ax.texts) == before + 1
        plt.close(fig)


class TestDrawSegmentLabel:
    def test_inside_label_for_wide_segment(self):
        fig, ax = plt.subplots()
        ax.set_xlim(0, 100)
        render.draw_segment_label(ax, x_centre=25, y=0, label="GW8 · 47pts",
                                  segment_width=50, x_max=100)
        texts = ax.texts
        assert len(texts) == 1
        assert texts[0].get_color() == "white"
        plt.close(fig)

    def test_outside_label_for_narrow_segment(self):
        fig, ax = plt.subplots()
        ax.set_xlim(0, 100)
        render.draw_segment_label(ax, x_centre=2, y=0, label="GW8 · 47pts",
                                  segment_width=5, x_max=100)
        texts = ax.texts
        assert len(texts) == 1
        assert texts[0].get_color() == render.TEXT_SECONDARY
        plt.close(fig)
