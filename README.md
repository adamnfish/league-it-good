# League it Good

A Python tool for generating comprehensive Fantasy Premier League gameweek summaries and statistics.

## Features

- Fetches data from the official FPL API
- Generates detailed gameweek summaries with:
  - League standings with position changes
  - Chip usage overview
  - Captain analysis with triple captain indicators
  - Positional performance breakdown
  - Bench points tracking with bench boost highlights
  - Best differential picks
  - Transfer analysis with wildcard indicators (requires previous gameweek data)
- Administrative tools:
  - League cache management
  - Skipped section notifications
- Caches API responses to minimize requests
- Outputs WhatsApp-ready formatted text

## Setup

1. Create a virtual environment and install dependencies:

```bash
./setup.sh
```

2. Activate the virtual environment and install the package:

```bash
source .venv/bin/activate
pip install -e .
```

This makes the `lig` and `league-it-good` commands available.

## Usage

```bash
# Generate gameweek summary
lig gen --league-id YOUR_LEAGUE_ID --gameweek 1

# Or use the full name
league-it-good gen --league-id YOUR_LEAGUE_ID --gameweek 1

# List cached leagues and their available gameweeks
lig leagues

# Show help
lig --help
```

### Graphs

`lig graphs` renders a folder of PNG charts (cover-sheet legend, weekly
scores, league position, cumulative points, wins/losses, bench points,
transfer costs, positional breakdown, consistency, and one chart per chip)
for a league. Output goes to `~/.fpl-tools/graphs/<league-id>/`.

Each league needs a small TOML config holding display names and per-manager
colours. Bootstrap one from cached data:

```bash
# Writes ~/.fpl-tools/config/leagues/YOUR_LEAGUE_ID.toml
lig graphs-config -l YOUR_LEAGUE_ID
```

Open the file and edit `display_name`, `colour`, and (optionally)
`avatar` for each manager. Avatars are local PNG files placed at
`~/.fpl-tools/config/avatars/<name>.png` and referenced as
`avatar = "avatars/<name>.png"` in the TOML. Managers without an avatar
fall back to a coloured circle with their initials.

Then render:

```bash
# All charts (the default)
lig graphs -l YOUR_LEAGUE_ID

# Just one chart — see `lig graphs --list` for available names
lig graphs -l YOUR_LEAGUE_ID --chart cumulative_points

# Restrict to a gameweek range
lig graphs -l YOUR_LEAGUE_ID -g 1-20
```

Charts read only from `~/.fpl-tools/cache/` — populate it with `lig fetch`
or `lig gen` first.

## Output

### Gameweek Summaries
The script generates:
- Console output with the formatted summary
- A saved file in `~/.fpl-tools/summaries/` directory
- Cached API responses in `~/.fpl-tools/cache/` for faster subsequent runs

### Graphs
- PNG charts written to `~/.fpl-tools/graphs/<league-id>/`
- League configs at `~/.fpl-tools/config/leagues/<league-id>.toml`
- Avatars at `~/.fpl-tools/config/avatars/<name>.png`

### Administrative Commands
- `leagues` shows a comprehensive table of cached league data including:
  - League IDs and names
  - Number of teams in each league
  - Available gameweeks with missing weeks highlighted
