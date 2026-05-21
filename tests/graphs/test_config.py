"""
Tests for graphs/config.py

Run with: python -m pytest src/tests/graphs/test_config.py -v
"""

import pytest
from pathlib import Path
import tempfile
import os

from src.graphs.config import (
    load_league_config,
    LeagueConfig,
    ManagerConfig,
    ConfigError,
)


def write_toml(directory: Path, league_id: int, content: str) -> Path:
    """Helper to write a TOML config file and return its path."""
    leagues_dir = directory / "leagues"
    leagues_dir.mkdir(parents=True, exist_ok=True)
    path = leagues_dir / f"{league_id}.toml"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_load_minimal_config():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345
name = "Test League"

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
""")
        config = load_league_config(config_dir, 12345)
        assert config.id == 12345
        assert config.name == "Test League"
        assert len(config.managers) == 1
        assert config.managers[0].fpl_name == "Adam Smith"
        assert config.managers[0].display_name == "Adam"
        assert config.managers[0].colour == "#e63946"
        assert config.managers[0].avatar_path is None


def test_load_config_without_optional_name():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
""")
        config = load_league_config(config_dir, 12345)
        assert config.name is None


def test_load_config_multiple_managers():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"

[[managers]]
fpl_name = "Dave Jones"
display_name = "Dave"
colour = "#457b9d"
""")
        config = load_league_config(config_dir, 12345)
        assert len(config.managers) == 2
        assert config.fpl_names == ["Adam Smith", "Dave Jones"]


def test_get_manager_found():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
""")
        config = load_league_config(config_dir, 12345)
        manager = config.get_manager("Adam Smith")
        assert manager is not None
        assert manager.display_name == "Adam"


def test_get_manager_not_found_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
""")
        config = load_league_config(config_dir, 12345)
        assert config.get_manager("Unknown Manager") is None


def test_colour_normalised_to_lowercase():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#E63946"
""")
        config = load_league_config(config_dir, 12345)
        assert config.managers[0].colour == "#e63946"


def test_short_hex_colour_expanded():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#f39"
""")
        config = load_league_config(config_dir, 12345)
        assert config.managers[0].colour == "#ff3399"


def test_avatar_resolved_when_file_exists():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        # Create a dummy avatar file
        avatars_dir = config_dir / "avatars"
        avatars_dir.mkdir()
        avatar_file = avatars_dir / "adam.png"
        avatar_file.write_bytes(b"fake png")

        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
avatar = "avatars/adam.png"
""")
        config = load_league_config(config_dir, 12345)
        assert config.managers[0].avatar_path == avatar_file.resolve()


def test_avatar_none_when_file_missing(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
avatar = "avatars/does_not_exist.png"
""")
        config = load_league_config(config_dir, 12345)
        assert config.managers[0].avatar_path is None
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "Adam Smith" in captured.out


def test_manager_initials_single_word():
    m = ManagerConfig(fpl_name="Adam", display_name="Adam", colour="#e63946")
    assert m.initials == "A"


def test_manager_initials_two_words():
    m = ManagerConfig(fpl_name="Adam Smith", display_name="Adam Smith", colour="#e63946")
    assert m.initials == "AS"


def test_manager_initials_truncated_at_two():
    m = ManagerConfig(fpl_name="x", display_name="Adam Adonis Smith", colour="#e63946")
    assert m.initials == "AA"


def test_no_managers_produces_warning(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345
""")
        config = load_league_config(config_dir, 12345)
        assert config.managers == []
        captured = capsys.readouterr()
        assert "Warning" in captured.out


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_missing_file_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ConfigError, match="No config file found"):
            load_league_config(Path(tmp), 99999)


def test_missing_league_section_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"
""")
        with pytest.raises(ConfigError, match="missing the required \\[league\\] section"):
            load_league_config(config_dir, 12345)


def test_missing_league_id_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
name = "Test"
""")
        with pytest.raises(ConfigError, match="missing 'id'"):
            load_league_config(config_dir, 12345)


def test_league_id_mismatch_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 99999
""")
        with pytest.raises(ConfigError, match="League ID mismatch"):
            load_league_config(config_dir, 12345)


def test_missing_fpl_name_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
display_name = "Adam"
colour = "#e63946"
""")
        with pytest.raises(ConfigError, match="Missing required field 'fpl_name'"):
            load_league_config(config_dir, 12345)


def test_missing_display_name_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
colour = "#e63946"
""")
        with pytest.raises(ConfigError, match="Missing required field 'display_name'"):
            load_league_config(config_dir, 12345)


def test_missing_colour_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
""")
        with pytest.raises(ConfigError, match="Missing required field 'colour'"):
            load_league_config(config_dir, 12345)


def test_invalid_colour_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "not-a-colour"
""")
        with pytest.raises(ConfigError, match="Invalid colour"):
            load_league_config(config_dir, 12345)


def test_duplicate_fpl_names_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam"
colour = "#e63946"

[[managers]]
fpl_name = "Adam Smith"
display_name = "Adam (2)"
colour = "#457b9d"
""")
        with pytest.raises(ConfigError, match="Duplicate fpl_name"):
            load_league_config(config_dir, 12345)


def test_empty_fpl_name_raises_config_error():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        write_toml(config_dir, 12345, """
[league]
id = 12345

[[managers]]
fpl_name = "   "
display_name = "Adam"
colour = "#e63946"
""")
        with pytest.raises(ConfigError, match="cannot be empty"):
            load_league_config(config_dir, 12345)
