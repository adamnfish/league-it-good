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
lig --league-id YOUR_LEAGUE_ID --gameweek 1

# Or use the full name
league-it-good --league-id YOUR_LEAGUE_ID --gameweek 1

# List cached leagues and their available gameweeks
lig --list-leagues

# Show help
lig --help
```

## Output

### Gameweek Summaries
The script generates:
- Console output with the formatted summary
- A saved file in `~/.fpl-tools/summaries/` directory
- Cached API responses in `~/.fpl-tools/cache/` for faster subsequent runs

### Administrative Commands
- `--list-leagues` shows a comprehensive table of cached league data including:
  - League IDs and names
  - Number of teams in each league
  - Available gameweeks with missing weeks highlighted
