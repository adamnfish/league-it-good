# FPL Tools

A Python tool for generating comprehensive Fantasy Premier League gameweek summaries and statistics.

## Features

- Fetches data from the official FPL API
- Generates detailed gameweek summaries with:
  - League standings with position changes
  - Captain analysis grouped by player choice
  - Bench points tracking
  - Positional performance breakdown
  - Transfer analysis (gameweek 2+, requires cached data for the previous week)
  - Chip usage tracking (Wildcard, Free Hit, Bench Boost, Triple Captain)
  - Best differential picks (unique high-scoring players)
- Administrative tools:
  - League cache management and overview
  - Clear feedback when sections are skipped
- Caches API responses to minimize requests
- Outputs WhatsApp-ready formatted text

## Setup

Run the setup script to create a virtual environment and install dependencies:

```bash
./setup.sh
```

## Usage

```bash
# Activate virtual environment
source .venv/bin/activate

# Generate gameweek summary
python gameweek.py --league-id YOUR_LEAGUE_ID --gameweek 1

# List cached leagues and their available gameweeks
python gameweek.py --list-leagues

# Deactivate when done
deactivate
```

## Output

### Gameweek Summaries
The script generates:
- Console output with the formatted summary
- A saved file in `~/.fpl-tools/summaries/` directory
- Cached API responses in `~/.fpl-tools/cache/` for faster subsequent runs
- Clear feedback about why certain analysis sections are skipped

### Administrative Commands
- `--list-leagues` shows a comprehensive table of cached league data including:
  - League IDs and names
  - Number of teams in each league
  - Available gameweeks with missing weeks highlighted
