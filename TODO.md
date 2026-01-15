# League it Good - TODO List

## Phase 0: Immediate Fixes & CLI Improvements

### Command Restructuring
- [x] **Split backup command** - Refactor the current `backup` command into separate `export` and `import` commands for better CLI usability
  - `lig export` - Export cache to backup file with optional custom path, defaults to timestamped filename
  - `lig import` - Import missing gameweeks from backup, resolves filename from backups directory or accepts full path with `--file` flag
  - Keep `--dry-run` flag for import command
  - Both commands should maintain current functionality from the unified backup command
  - Update help text and documentation accordingly
  - Also created `lig describe` command for inspecting backup contents

### Data Fetching
- [ ] **Add fetch command** - Create new `lig fetch` command to preload/refresh cache data without generating summary output
  - Support fetching specific league with `--league-id` and `--gameweek` parameters
  - Support fetching all cached leagues with `--all` flag (discovers leagues from existing cache)
  - Add `--force` flag to refresh cache even when data already exists
  - Display progress messages showing what's being fetched
  - Useful for:
    - Preloading data before going offline
    - Refreshing stale cache data
    - Warming cache for multiple leagues at once
    - Testing API connectivity

### Analysis Bug Fixes
- [x] **Handle ties in overall league positions** - When multiple managers have the same total points, they should be displayed with tied rankings
  - Currently: Using `manager['rank']` from FPL API which assigns sequential ranks (1, 2, 3, 4...) even when there are ties
  - Example bug: Two managers with 1169 pts show as ranks 2 and 3 instead of both being rank 2
  - Solution: Calculate proper ranks based on `total` field in standings
  - When managers are tied, they should have the same rank
  - After a tie, skip ranks appropriately (if 2 people tied at rank 2, next person is rank 4, not 3)
  - Update `format_league_standings()` in `src/display.py` line 194
  - **COMPLETED**: Created `calculate_proper_ranks()` helper function in analysis.py, updated both display and position change calculations

- [ ] **Handle ties in gameweek rankings** - When multiple managers have the same gameweek score, they should be displayed with tied rankings
  - Currently: Ties are already handled for the gameweek winner display (lines 69-74 in display.py)
  - Verify wooden spoon handling also works correctly with ties
  - Update the gameweek summary section in `src/display.py` if needed

- [ ] **Fix transfer analysis after Free Hit** - When analyzing transfers, handle the Free Hit chip edge case properly
  - Currently: After a Free Hit week, all players appear as "new transfers" because the squad reverts to pre-Free Hit state
  - Solution: When previous gameweek was a Free Hit, compare against gameweek N-2 instead of N-1 for transfer tracking
  - Check the `active_chip` field in previous gameweek data to detect Free Hit usage
  - Add logic to `analyze_transfers()` function in `src/analysis.py`
  - Consider adding a note in transfer section when this occurs (e.g., "Transfer comparison vs GW N-2 due to Free Hit in GW N-1")
  - Add console warning if N-2 week data is not available in cache (e.g., analyzing GW3 after a Free Hit in GW2, but no GW1 data cached)

### Chip Display Enhancements
- [ ] **Fix chip availability tracking** - Update chip availability section to handle chip replenishment at halfway point
  - FPL replenishes all chips at the halfway point of the season (after GW19 in 2024/25)
  - Current implementation may not correctly handle this replenishment
  - Investigate the FPL API data structure to understand how replenished chips are tracked
  - Update the chip availability analysis to accurately show which chips are available after replenishment
  - May need to check both the chip usage history and some indicator of chip grants/replenishments
  - Display appropriately in the "Available chips" section being added (see Phase 2 chip features)

## Phase 1: Configuration & Cleanup

### Configuration Tasks
- [x] **Parameterize league ID** - Remove hardcoded league ID and accept as CLI argument
- [x] **Parameterize gameweek** - Remove hardcoded gameweek and accept as CLI argument  
- [x] **Move cache directory** - Move cache from `fpl_cache/` to persistent location outside repo (`~/.fpl-tools/cache/`)
- [x] **Move output directory** - Move output files to persistent location (`~/.fpl-tools/summaries/`)
- [ ] **Rename data directories** - Update our data directories to use the new name `league-it-good` (instead of `fpl-tools`)

### UI/UX Improvements  
- [x] **Reduce emoji usage** - Tone down emoji usage in output formatting while keeping it readable and fun
- [x] **Update section headings** - Make section headings more fun and punny
- [x] **Improve captain display** - Group by captain choice instead of manager, remove redundant doubling calculation, handle vice captain edge cases

## Phase 2: Enhanced Features (for Gameweek 2+)

### Transfer Analysis
- [x] **Transfer tracking** - Compare current gameweek picks with previous gameweek to identify new signings
- [x] **Transfer activity display** - Show number of transfers, costs, and group managers by transfer count
- [x] **Best/worst transfers** - Highlight managers with best and worst performing transfer decisions

### League Display Enhancements
- [x] **League position changes** - Add up/down arrows showing position movement from previous gameweek
- [x] **Enhanced league table** - Two-line format with team names, position changes, total points, and gameweek highlights
- [x] **Improved gameweek summary** - Show gameweek winner, wooden spoon, and league average instead of duplicating league table
- [x] **Inline vice captain display** - Show "(v)" when vice captain stepped up in captain analysis

### Captain Analysis
- [x] **Captain performance tracking** - Show captain choices grouped by player with points scored
- [x] **Vice captain integration** - Handle edge cases where vice captain steps up

### Completed Features
- [x] **Best differential** - Show highest scoring player that was only owned by one manager (unique picks)
- [x] **Chip usage tracking** - Display chips used in gameweek (Wildcard, Free Hit, Bench Boost, Triple Captain)

### Chip features
- [x] **Triple captain's log** - Include a `*(x3)*` note in the captain's log display for managers that played their triple captain chip
- [x] **Wildcard transfer display** - Show `*(wc)*` in the transfer count display next to managers that played their wildcard chip
- [ ] **Free hit** - Add a free hit section that appears when any manager played a Free Hit chip. This should compare the score of their free hit squad to the score of the squad they had the week before, and display that difference
- [x] **Bench boost** - Managers that played their bench boost should get a callout in the bench press section, displaying the points they got for this chip
- [ ] **Available chips** - add a new section that displays the chips each manager has available to them. Let's have an icon for each chip, and display the icon (or a cross) before each manager's name

### Messaging

- [ ] **Gameweek-based table title** - The main table title gets manually changed every week, let's bring that into the logic so the display uses the selected gameweek to decide which title to use

## Phase 3: Code Quality & Polish

### Technical Improvements
- [x] **League-specific output files** - Parameterize filenames with league ID to prevent overwriting
- [x] **User feedback** - Add logging to the summary generation to describe clarify why sections are skipped
- [x] **Restructure application** - Separate modules for FPL / cache / main / display (✨ **COMPLETED!** See REFACTORING.md)
- [ ] **Table formatting library** - Consider using `tabulate` or similar for cleaner admin table formatting in `--list-leagues` command
- [ ] **Single data fetch** - Let's fetch the gameweek data we need once up front, and pass this around the program while it runs, rather than have each feature independently lookup the gameweek/manager data
- [ ] **Remove legacy entry point** - The gameweek.py file is now deprecated, let's remove it and update all the usage docs

## Phase 4: Tests

### FPL analysis

- [ ] **Fake league data** - Generate cache data for a fake league with historic football stars that can be used for testing analysis logic
- [ ] **Tests for analysis logic**

### Display

- [ ] **Snapshot tests** - Add snapshot tests for the output, to catch accidental regressions (with an easy way to update the saved snapshot after a deliberate change)

### Storage

- [ ] **Cached league data** - Test the logic that scans the cache in the get_cached_league_data function

## Implementation Notes

### Phase 1 Requirements
- All Phase 1 tasks can be implemented immediately
- No additional API data required
- Focus on making the tool more flexible and professional

### Phase 2 Requirements  
- Requires gameweek 2+ data to be meaningful
- Will need to store/compare data across multiple gameweeks
- May need additional API endpoints or enhanced caching strategy

### Technical Considerations
- Use Click for CLI argument parsing (already added to requirements.txt)
- Consider using `appdirs` or similar for cross-platform cache directory location
- Maintain backward compatibility where possible
- Keep the WhatsApp-ready output format as the primary goal
