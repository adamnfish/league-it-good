# Cache Import/Export Feature Design

## Overview
Enable syncing FPL cache data across multiple machines by exporting to a portable archive and importing missing gameweeks from archives.

## Use Case
Running the tool across multiple laptops means data directories are incomplete individually, but collectively contain complete weeks. Need a way to consolidate and sync cache data, handling overlaps and gaps.

---

## Unified Table Format

As part of this feature, we'll modernize the `--list-leagues` display to use a more compact, scannable format. This same format will then be used consistently across all cache management commands.

### New `--list-leagues` Format

**Before:**
```
📊 Cached League Data
================================================================================
League ID  League Name               Teams  Gameweeks Available
--------------------------------------------------------------------------------
123456     The Best League           12     1 2 3 4
789012     Another League            10     1 2 x x
```

**After:**
```
📊 Cached League Data
================================================================================
League ID  League Name               👥  GW 1 2 3 4
--------------------------------------------------------------------------------
123456     The Best League           12     ✓ ✓ ✓ ✓
789012     Another League            10     ✓ ✓ x x
```

**Changes:**
- Header uses 👥 emoji (2 chars) instead of "Teams" (5 chars)
- Header uses "GW 1 2 3 4..." instead of "Gameweeks Available"
- Extra space between 👥 and GW for visual distinction
- Uses ✓ icon for present gameweeks (instead of showing the number)
- Keeps bold **x** for missing gameweeks
- More compact (saves vertical and horizontal space)
- More scannable (icons easier to parse than mixed numbers/x's)

This becomes the base format for `--describe-backup` (same icons) and `--import-cache` (different status icons).

---

## Archive Format

**ZIP archive** containing the cache directory structure:
```
fpl-cache-2025-11-05.zip
├── gw1/
│   ├── bootstrap.json
│   ├── league_123456.json
│   └── manager_789012_picks.json
├── gw2/
│   └── ...
├── gw3/
│   └── ...
└── metadata.json
```

### Metadata Format
```json
{
  "export_date": "2025-11-05T14:30:00Z",
  "machine_name": "MacBook-Pro",
  "tool_version": "1.0.0",
  "gameweeks": {
    "1": {
      "leagues": ["123456", "789012"],
      "managers": 12,
      "files": 25
    },
    "2": {
      "leagues": ["123456"],
      "managers": 12,
      "files": 25
    }
  }
}
```

**Why ZIP?**
- Single portable file
- Built-in Python support (`zipfile` module)
- Cross-platform compatibility
- Preserves directory structure
- Good compression for JSON files

---

## CLI Commands

### Export Cache
```bash
lig --export-cache [<output_path>]
```

**Behavior:**
- If path not provided, auto-generate: `~/.fpl-tools/backups/fpl-cache-{date}.zip`
- Creates backup in the backups directory by default
- Includes all cached gameweek data
- Generates metadata.json with export info

**Example:**
```bash
# Auto-generate filename in backups directory
lig --export-cache

# Specify custom location
lig --export-cache ~/Desktop/fpl-backup.zip
```

### Import Cache
```bash
lig --import-cache <archive_path> [--dry-run]
```

**Behavior:**
- Scan archive for all `(league_id, gameweek)` combinations
- **For each combination**, check if that specific league file exists locally:
  - `cache/gw{N}/league_{id}.json` exists? → Skip (already have it)
  - Doesn't exist? → Import from archive (including associated manager files)
- **Auto-backup before import:** Create safety backup to `~/.fpl-tools/backups/pre-import-{timestamp}.zip`
- Import missing data on a **per-league, per-gameweek basis**
- Report results in league-by-league format with status for each gameweek

**Important:** Import is granular - a gameweek directory might exist locally but be missing data for some leagues. Import only fills in the gaps.

**Example:**
```bash
# See what would be imported (no changes made)
lig --import-cache ~/backup.zip --dry-run

# Actually import missing data
lig --import-cache ~/backup.zip
```

### Describe Backup
```bash
lig --describe-backup <archive_path>
```

**Behavior:**
- Read metadata from archive
- Show export date, source machine, version as header
- **Reuse existing `format_admin_table()` function** to display league data in identical format to `--list-leagues`
- Don't extract or modify anything

**Example output:**
```
Backup Archive: ~/fpl-backup.zip
Exported: 2025-11-05 14:30:00
Source: MacBook-Pro
Tool Version: 1.0.0

📊 Cached League Data
================================================================================
League ID  League Name               👥  GW 1 2 3 4 5 6
--------------------------------------------------------------------------------
123456     The Best League           12     ✓ ✓ ✓ ✓ x x
789012     Another League            10     ✓ ✓ x x x x

```
(Uses ✓ for present gameweeks, bold **x** for missing)

**Implementation Note:**
- Extract league structure from archive (scan for league_*.json files in each gw directory)
- Build same data structure as `list_leagues_data()` in storage.py
- Pass to existing `format_admin_table()` for display
- This ensures 100% consistency with `--list-leagues` output

---

## Import Report Format

Use the same table format as `--list-leagues`, with status icons instead of gameweek numbers:

```
Importing from fpl-backup.zip...

Created safety backup: ~/.fpl-tools/backups/pre-import-2025-11-05-143000.zip

================================================================================
League ID  League Name               👥  GW 1 2 3 4 5 6
--------------------------------------------------------------------------------
123456     The Best League           12     ✓ ↓ ↓ x x x
789012     Another League            10     x ↓ ↓ x x x

Summary:
↓ Total imported: 4 gameweeks across 2 leagues (156 files)
- Total skipped: 1 gameweek (already exists)
```

### Status Icons
- `✓` = Already exists locally (skipped)
- `↓` = Imported from archive
- `x` = Not in archive (bold **x** in actual output)
- `⚠` = Overridden (force mode, Phase 2)

**Implementation Note:**
- Similar table layout to `format_admin_table()` with compact header
- Header includes "GW" prefix with gameweek numbers (saves vertical space)
- Display status icons for each league/gameweek combination
- Maximum code reuse with existing display logic

### Dry-run Output
```
DRY RUN: No changes will be made

Would import from fpl-backup.zip:

================================================================================
League ID  League Name               👥  GW 1 2 3 4 5 6
--------------------------------------------------------------------------------
123456     The Best League           12     ✓ ↓ ↓ x x x
789012     Another League            10     x ↓ ↓ x x x

Summary:
↓ Would import: 4 gameweeks across 2 leagues (156 files)
- Would skip: 1 gameweek (already exists)

Run without --dry-run to perform import
```

---

## Import Granularity

Import works on a **per-league, per-gameweek** basis, not just per-gameweek.

### Example Scenario

**Local cache state:**
```
cache/
├── gw3/
│   └── league_123456.json  ✓ exists
└── gw4/
    └── league_123456.json  ✓ exists
```

**Archive contains:**
```
gw3/
├── league_123456.json  (skip - already exists locally)
└── league_789012.json  (IMPORT - missing locally)
gw4/
├── league_123456.json  (skip - already exists locally)
└── league_789012.json  (IMPORT - missing locally)
```

**Result:**
- Import creates `cache/gw3/league_789012.json` and associated manager files
- Import creates `cache/gw4/league_789012.json` and associated manager files
- Skips league_123456 data (already exists)
- Both leagues now have data for gw3 and gw4

### Import Status Per League

The import table shows status for each `(league, gameweek)` combination:

```
League ID  League Name               👥  GW 3 4
123456     League A                  12     ✓ ✓   (skipped - already had both)
789012     League B                  10     ↓ ↓   (imported - was missing both)
```

---

## Data Directory Structure

Add a `backups` directory to the data directory:

```
~/.fpl-tools/
├── cache/
│   ├── gw1/
│   ├── gw2/
│   └── ...
├── summaries/
│   ├── league_123456_gw1.txt
│   └── ...
└── backups/
    ├── fpl-cache-2025-11-05.zip
    ├── pre-import-2025-11-05-143000.zip
    └── ...
```

**Backups Directory:**
- Default location for exports (when path not specified)
- Safety backups created before imports
- Named with timestamps for easy identification
- Can accumulate over time (user can manually clean up)

---

## Implementation Plan

### Phase 1: Basic Import/Export

#### storage.py - New Functions
```python
def get_backups_dir() -> str:
    """Get path to backups directory, create if needed."""

def export_cache(output_path: Optional[str] = None) -> str:
    """Export cache to zip archive, return path to created file."""

def import_cache(archive_path: str, dry_run: bool = False) -> dict:
    """
    Import missing league/gameweek data from archive, return import report.

    Works on a per-league, per-gameweek basis:
    - Scans archive for all (league_id, gameweek) pairs
    - For each pair, checks if cache/gw{N}/league_{id}.json exists locally
    - Imports only missing combinations (along with associated files)
    """

def describe_backup(archive_path: str) -> Dict[int, Dict[str, Any]]:
    """Read backup archive and return league data in same format as list_leagues_data()."""

def read_backup_metadata(archive_path: str) -> dict:
    """Read metadata.json from backup archive."""

def create_safety_backup() -> str:
    """Create timestamped backup before import, return path."""

def generate_backup_filename(prefix: str = "fpl-cache") -> str:
    """Generate timestamped backup filename."""
```

#### main.py - CLI Updates
```python
@click.option('--export-cache', type=click.Path(),
              help='Export cache to archive file')
@click.option('--import-cache', type=click.Path(exists=True),
              help='Import missing gameweeks from archive')
@click.option('--dry-run', is_flag=True,
              help='Show what would be imported without making changes')
@click.option('--describe-backup', type=click.Path(exists=True),
              help='Show information about a backup archive')
```

#### display.py - Report Formatting
```python
def format_import_table(league_data: Dict[int, Dict[str, Any]],
                        import_status: Dict[int, Dict[int, str]]) -> None:
    """
    Display import results table with status icons.
    Similar to format_admin_table() but with gameweek numbers header
    and status icons (✓, ↓, x, ⚠) instead of numbers.

    Args:
        league_data: League structure (same format as list_leagues_data())
        import_status: Dict mapping league_id -> {gameweek -> status_icon}
    """

# Note: --describe-backup will reuse existing format_admin_table() function
# Just needs to print backup metadata header before calling it
```

### Phase 1 Implementation Steps

1. **Modernize `--list-leagues` display** (display.py)
   - Update `format_admin_table()` to use new compact header format
   - Change "Teams" to 👥 emoji (saves horizontal space)
   - Change from "Gameweeks Available" to "GW 1 2 3 4 5..."
   - Add extra space between 👥 and GW for visual separation
   - Use ✓ icons for present gameweeks instead of numbers
   - Keep **x** for missing gameweeks
   - This becomes the base table format for all commands

2. **Add backups directory support** (storage.py)
   - `get_backups_dir()` function
   - Auto-create on first use

3. **Implement export** (storage.py)
   - Create zip from cache directory
   - Generate metadata.json
   - Default to backups dir with auto-generated name
   - Support custom output path

4. **Implement describe** (storage.py + main.py)
   - `describe_backup()` scans archive and builds league data structure
   - Returns same format as `list_leagues_data()`
   - main.py prints metadata header, then calls updated `format_admin_table()`
   - Automatically uses new format!

5. **Implement import logic** (storage.py)
   - Scan archive for all `(league_id, gameweek)` pairs
   - For each pair, check if `cache/gw{N}/league_{id}.json` exists locally
   - Create safety backup of current cache before any changes
   - Extract missing league files and associated manager/bootstrap files
   - Work on a per-league, per-gameweek granular basis
   - Generate detailed report data with status for each league/gameweek combination

6. **Implement import reporting** (display.py)
   - New `format_import_table()` function based on updated `format_admin_table()`
   - Reuse same table layout and header format
   - Display status icons (✓, ↓, x, ⚠) for import status
   - Summary statistics at bottom

7. **Add CLI commands** (main.py)
   - Wire up all three commands
   - Handle dry-run flag
   - Error handling and user feedback

8. **Testing**
   - Test updated `--list-leagues` display
   - Test export with existing cache
   - Test import to empty cache
   - Test import with overlapping data
   - Test dry-run mode
   - Test describe on various archives

---

## Phase 2: Force Override (Future)

### CLI Update
```bash
lig --import-cache <archive_path> --force <gameweek>
```

**Behavior:**
- Only affects specified gameweek
- Validates that gameweek exists in archive
- Detects if local data appears stale/provisional:
  - Bonus points are 0 (indicates provisional data)
  - File timestamp suggests data fetched before gameweek finished
  - Other heuristics
- Overrides local data with archive data for that specific gameweek
- Creates safety backup before override
- Report shows `⚠` icon for overridden week

### Stale Data Detection
```python
def is_gameweek_stale(gameweek: int) -> bool:
    """Detect if local gameweek data appears to be provisional/stale."""
    # Check bonus points = 0
    # Check fetch timestamp vs gameweek deadline
    # Other validation
```

### Safety Considerations
- Require explicit gameweek argument (no wildcards or "all")
- Always create backup before override
- Confirm action with user or require explicit flag
- Log what was overridden for audit trail

---

## Edge Cases & Considerations

### Export
- Empty cache directory - create archive with just metadata
- Very large cache - show progress indicator
- Disk space - check before creating large archives
- File permissions - handle read errors gracefully

### Import
- Archive with different tool version - warn but allow
- Corrupted archive - validate before extracting
- Partial import failure - rollback from safety backup
- Disk space - check before extracting
- Duplicate leagues with different data - prefer local (safe default)

### Describe
- Archive without metadata - infer from contents
- Corrupted metadata - fall back to directory scan
- Empty archive - show appropriate message

### Backups Directory
- Accumulation over time - document user can clean up manually
- Potential future: auto-cleanup old backups (keep last N)
- Naming conflicts - add sequence number if needed

---

## Success Criteria

### Phase 1
- ✓ `--list-leagues` uses new compact format with ✓/x icons
- ✓ Can export cache to portable archive
- ✓ Can describe contents of archive without importing
- ✓ Can preview import with dry-run
- ✓ Import creates safety backup automatically
- ✓ Import correctly merges missing gameweeks
- ✓ Import preserves existing data (no overwrites)
- ✓ All three commands use consistent table format
- ✓ Reports show clear league-by-league status
- ✓ Works across machines with different partial caches

### Phase 2
- ✓ Can force-override specific stale gameweek
- ✓ Detects provisional/incomplete data
- ✓ Only affects explicitly specified gameweek
- ✓ Safety mechanisms prevent accidental data loss

---

## Open Questions

1. **Archive naming:** Default filename format? `fpl-cache-{date}.zip` or include machine name?
2. **What to include:** Just cache directory, or also summaries?
3. **Metadata completeness:** What additional info would be useful? (leagues, managers, file counts per week?)
4. **Backup retention:** Should we auto-cleanup old backups or leave that to user?
5. **Progress indicators:** For large exports/imports, show progress?
6. **Validation:** Should we validate JSON files during import/export?

---

## Future Enhancements (Beyond Phase 2)

- **Merge command:** Intelligently merge two archives
- **Cleanup command:** Remove old backups based on age/count
- **Selective export:** Export only specific gameweeks or leagues
- **Cloud sync:** Integration with cloud storage (Dropbox, Google Drive)
- **Compression options:** Different compression levels for size vs speed
- **Encryption:** Secure archives with password protection
- **Diff command:** Compare two archives to see differences
