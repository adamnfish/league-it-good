# Claude AI Assistant Context

## Project Overview

FPL Tools is a Python application that generates Fantasy Premier League gameweek summaries by fetching data from the official FPL API and creating formatted reports suitable for sharing on WhatsApp or other messaging platforms.

## Key Technical Details

### Architecture
- Single Python script (`gameweek.py`) with modular functions
- Uses the official FPL API endpoints:
  - Bootstrap static data for player information
  - League standings for rankings and scores
  - Manager gameweek data for detailed picks and captain info
- Local JSON caching system to minimize API requests

### Current Implementation
- Hardcoded league ID and gameweek (needs parameterization)
- Cache stored in repository root (should move to persistent location)
- Heavy emoji usage in output formatting
- Basic command-line execution without argument parsing

### Data Flow
1. Fetch bootstrap data (player database)
2. Fetch league standings 
3. For each manager, fetch detailed gameweek data
4. Analyze captain choices, bench points, positional performance
5. Generate formatted summary text
6. Save to local file

## Development Guidelines

### Code Style
- Use existing patterns and conventions
- Maintain error handling with try/catch blocks
- Keep functions focused and well-documented
- Use descriptive variable names

### Testing
- No formal test framework currently implemented
- Manual testing by running against real FPL data
- Cache system allows for consistent testing without API calls

### Dependencies
- Minimal external dependencies (currently just `requests`)
- Standard library usage preferred where possible

## Future Enhancements Planned

### Phase 1 (Administrative)
- Parameter-driven league ID and gameweek
- Click library for CLI argument parsing
- Move cache to persistent location outside repo
- Reduce emoji usage in output

### Phase 2 (Features - when gameweek 2 data available)
- Most successful transfer analysis
- Best differential player identification  
- League position change tracking
- Worst captain choice highlighting

## API Information

The FPL API endpoints used:
- `https://fantasy.premierleague.com/api/bootstrap-static/` - Player and team data
- `https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/` - League standings
- `https://fantasy.premierleague.com/api/entry/{manager_id}/event/{gameweek}/picks/` - Manager picks

Rate limiting considerations: The script uses local caching to avoid repeated API calls during development and testing.