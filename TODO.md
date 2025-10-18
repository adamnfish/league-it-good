# FPL Tools - TODO List

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
