# FPL Tools - TODO List

## Phase 1: Configuration & Cleanup

### Configuration Tasks
- [x] **Parameterize league ID** - Remove hardcoded league ID and accept as CLI argument
- [x] **Parameterize gameweek** - Remove hardcoded gameweek and accept as CLI argument  
- [x] **Move cache directory** - Move cache from `fpl_cache/` to persistent location outside repo (`~/.fpl-tools/cache/`)
- [x] **Move output directory** - Move output files to persistent location (`~/.fpl-tools/summaries/`)

### UI/UX Improvements  
- [x] **Reduce emoji usage** - Tone down emoji usage in output formatting while keeping it readable and fun
- [x] **Update section headings** - Make section headings more fun and punny
- [x] **Improve captain display** - Group by captain choice instead of manager, remove redundant doubling calculation, handle vice captain edge cases

## Phase 2: Enhanced Features (for Gameweek 2+)

### Transfer Analysis
- [ ] **Most successful transfer** - Find highest scoring player that was just transferred in by any manager
- [ ] **Worst captain choice** - Highlight the captain selection that scored the lowest points

### Unique Player Analysis  
- [ ] **Best differential** - Show highest scoring player that was only owned by one manager (unique picks)

### Historical Comparison
- [ ] **League position changes** - Add up/down arrows showing position movement from previous gameweek
- [ ] **Transfer tracking** - Compare current gameweek picks with previous gameweek to identify new signings

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