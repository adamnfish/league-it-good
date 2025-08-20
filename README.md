# FPL Tools

A Python tool for generating comprehensive Fantasy Premier League gameweek summaries and statistics.

## Features

- Fetches data from the official FPL API
- Generates detailed gameweek summaries with:
  - League standings and rankings
  - Captain analysis and statistics
  - Bench points tracking
  - Positional performance breakdown
  - Top performers and bottom performers
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

# Run the script with your league ID and gameweek
python gameweek.py --league-id YOUR_LEAGUE_ID --gameweek 1

# Deactivate when done
deactivate
```

## Output

The script generates:
- Console output with the formatted summary
- A saved file in `gw-summaries/` directory
- Cached API responses for faster subsequent runs
