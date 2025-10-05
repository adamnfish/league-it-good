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

### Administrative Commands
- `--list-leagues` shows a comprehensive table of cached league data including:
  - League IDs and names
  - Number of teams in each league
  - Available gameweeks with missing weeks highlighted
