"""
Graphs Config Module

Loads and validates per-league configuration from TOML files.
Each league has a config file at config/leagues/{league_id}.toml.

Config schema:
    [league]
    id = 12345
    name = "Our League"   # optional display override

    [[managers]]
    fpl_name = "Adam Smith"      # must match player_name from FPL API exactly
    display_name = "Adam"        # short label for chart axes
    avatar = "avatars/adam.png"  # relative to config/ directory, optional
    colour = "#e63946"           # hex colour for this manager's bars/lines
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# tomllib is stdlib from Python 3.11; fall back to tomli for older versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError as e:
        raise ImportError(
            "Python < 3.11 requires the 'tomli' package: pip install tomli"
        ) from e


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ManagerConfig:
    """Configuration for a single manager."""

    fpl_name: str
    """Exact match for player_name as returned by the FPL API."""

    display_name: str
    """Short friendly name used on chart axes and labels."""

    colour: str
    """Hex colour string, e.g. '#e63946'."""

    avatar_path: Optional[Path] = field(default=None)
    """Absolute path to the avatar image file, or None if not configured / not found."""

    @property
    def initials(self) -> str:
        """Up to two initials from display_name, used as avatar fallback."""
        words = self.display_name.split()
        return "".join(w[0].upper() for w in words[:2])


@dataclass(frozen=True)
class LeagueConfig:
    """Configuration for a single league."""

    id: int
    managers: list[ManagerConfig]
    name: Optional[str] = field(default=None)
    """Optional display name override. Falls back to the name from the FPL API."""

    def get_manager(self, fpl_name: str) -> Optional[ManagerConfig]:
        """
        Look up a manager by their FPL API player_name.

        Returns None if the manager isn't in the config — callers should
        handle this gracefully with a fallback (generic colour, initials avatar).
        """
        return next((m for m in self.managers if m.fpl_name == fpl_name), None)

    @property
    def fpl_names(self) -> list[str]:
        """All FPL names in config order."""
        return [m.fpl_name for m in self.managers]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when a config file is missing or malformed."""


def _validate_hex_colour(colour: str, context: str) -> str:
    """
    Validate a hex colour string.

    Accepts '#rgb' and '#rrggbb' formats.
    Raises ConfigError with a clear message if invalid.
    """
    stripped = colour.lstrip("#")
    if len(stripped) not in (3, 6) or not all(c in "0123456789abcdefABCDEF" for c in stripped):
        raise ConfigError(
            f"Invalid colour '{colour}' for {context}. "
            f"Expected hex format like '#e63946' or '#f39'."
        )
    # Normalise to full 6-char form
    if len(stripped) == 3:
        stripped = "".join(c * 2 for c in stripped)
    return f"#{stripped.lower()}"


def _resolve_avatar(
    raw_avatar: Optional[str],
    config_dir: Path,
    fpl_name: str,
) -> Optional[Path]:
    """
    Resolve an avatar path relative to config_dir.

    Returns the absolute Path if the file exists, otherwise None.
    A warning is printed if the path was specified but the file is missing —
    the rest of the config load proceeds normally.
    """
    if not raw_avatar:
        return None

    avatar_path = (config_dir / raw_avatar).resolve()

    if not avatar_path.exists():
        print(
            f"Warning: avatar not found for '{fpl_name}': {avatar_path}\n"
            f"  Falling back to initials avatar."
        )
        return None

    return avatar_path


def _parse_manager(raw: dict, config_dir: Path, index: int) -> ManagerConfig:
    """Parse and validate a single [[managers]] entry."""
    context = f"manager at index {index}"

    # Required fields
    for required in ("fpl_name", "display_name", "colour"):
        if required not in raw:
            raise ConfigError(
                f"Missing required field '{required}' for {context}."
            )

    fpl_name: str = raw["fpl_name"].strip()
    display_name: str = raw["display_name"].strip()

    if not fpl_name:
        raise ConfigError(f"'fpl_name' cannot be empty for {context}.")
    if not display_name:
        raise ConfigError(f"'display_name' cannot be empty for {context}.")

    colour = _validate_hex_colour(raw["colour"], context=f"'{fpl_name}'")
    avatar_path = _resolve_avatar(raw.get("avatar"), config_dir, fpl_name)

    return ManagerConfig(
        fpl_name=fpl_name,
        display_name=display_name,
        colour=colour,
        avatar_path=avatar_path,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_league_config(config_dir: Path, league_id: int) -> LeagueConfig:
    """
    Load and validate league config from config/leagues/{league_id}.toml.

    Args:
        config_dir: Path to the config/ directory (typically the repo root's
                    config/ folder).
        league_id:  The FPL league ID, used to find the right TOML file.

    Returns:
        A fully validated LeagueConfig instance.

    Raises:
        ConfigError: If the file is missing, unreadable, or contains invalid data.
    """
    config_path = config_dir / "leagues" / f"{league_id}.toml"

    if not config_path.exists():
        raise ConfigError(
            f"No config file found for league {league_id}.\n"
            f"Expected: {config_path}\n"
            f"Create it using the template in config/leagues/example.toml"
        )

    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
    except Exception as e:
        raise ConfigError(
            f"Failed to read config file {config_path}: {e}"
        ) from e

    # Parse [league] section
    if "league" not in raw:
        raise ConfigError(
            f"Config file {config_path} is missing the required [league] section."
        )

    league_section = raw["league"]

    if "id" not in league_section:
        raise ConfigError(
            f"Config file {config_path} is missing 'id' in the [league] section."
        )

    config_league_id = league_section["id"]
    if config_league_id != league_id:
        raise ConfigError(
            f"League ID mismatch: filename suggests {league_id} "
            f"but config says {config_league_id}."
        )

    # Parse [[managers]] entries
    raw_managers = raw.get("managers", [])
    if not raw_managers:
        print(
            f"Warning: no managers defined in {config_path}.\n"
            f"  Charts will use FPL names and generic colours."
        )

    managers = [
        _parse_manager(m, config_dir, i)
        for i, m in enumerate(raw_managers)
    ]

    # Check for duplicate fpl_names
    seen_fpl_names: set[str] = set()
    for manager in managers:
        if manager.fpl_name in seen_fpl_names:
            raise ConfigError(
                f"Duplicate fpl_name '{manager.fpl_name}' in {config_path}."
            )
        seen_fpl_names.add(manager.fpl_name)

    return LeagueConfig(
        id=league_id,
        name=league_section.get("name"),
        managers=managers,
    )
