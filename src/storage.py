"""
Storage Module - Data Persistence Layer

Handles all file I/O operations including:
- Cache management (reading/writing cached API responses)
- Data directory paths (.fpl-tools or .league-it-good)
- Summary file output
- Admin functions (list cached leagues, etc.)

This module has no knowledge of FPL-specific logic or formatting.
It only deals with storing and retrieving data from the filesystem.
"""

import json
import os
import zipfile
from datetime import datetime
from typing import Optional, Dict, Any, List, Set


def get_data_dir() -> str:
    """
    Get the base data directory path.

    Currently uses .fpl-tools, will migrate to .league-it-good later.

    Returns:
        str: Absolute path to data directory
    """
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".fpl-tools")


def get_backups_dir() -> str:
    """
    Get the backups directory path, creating it if needed.

    Returns:
        str: Absolute path to backups directory
    """
    backups_dir = os.path.join(get_data_dir(), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    return backups_dir


def resolve_backup_name(backup_name: str) -> str:
    """
    Resolve backup filename to full path in backups directory.

    Args:
        backup_name: Filename of backup in backups directory

    Returns:
        str: Full path to backup file in backups directory
    """
    return os.path.join(get_backups_dir(), backup_name)


def list_backups() -> List[Dict[str, Any]]:
    """
    List all backup archives in the backups directory.

    Returns:
        List of backup info dicts with keys:
        - filename: Name of backup file
        - size: File size in bytes
        - modified: Modification timestamp (datetime)
        - path: Full path to file
    """
    backups_dir = get_backups_dir()
    backups = []

    if not os.path.exists(backups_dir):
        return []

    for filename in os.listdir(backups_dir):
        if filename.endswith('.zip'):
            filepath = os.path.join(backups_dir, filename)
            stat = os.stat(filepath)

            backups.append({
                'filename': filename,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'path': filepath
            })

    # Sort by modification time, newest first
    backups.sort(key=lambda x: x['modified'], reverse=True)

    return backups


def get_cache_path(gameweek: int, cache_type: str, league_id: Optional[int] = None,
                   manager_id: Optional[int] = None) -> str:
    """
    Generate cache file path for a specific data type.

    Args:
        gameweek: Gameweek number
        cache_type: Type of cache ('bootstrap', 'league', 'manager', or 'history')
        league_id: League ID (required for 'league' type)
        manager_id: Manager ID (required for 'manager' and 'history' types)

    Returns:
        str: Absolute path to cache file
    """
    cache_dir = os.path.join(get_data_dir(), "cache", f"gw{gameweek}")
    os.makedirs(cache_dir, exist_ok=True)

    if cache_type == "bootstrap":
        return os.path.join(cache_dir, "bootstrap.json")
    elif cache_type == "league":
        return os.path.join(cache_dir, f"league_{league_id}.json")
    elif cache_type == "manager":
        return os.path.join(cache_dir, f"manager_{manager_id}.json")
    elif cache_type == "history":
        return os.path.join(cache_dir, f"history_{manager_id}.json")

    raise ValueError(f"Unknown cache type: {cache_type}")


def load_from_cache(cache_path: str) -> Optional[Dict[Any, Any]]:
    """
    Load data from cache if it exists.
    
    Args:
        cache_path: Path to cache file
    
    Returns:
        dict: Cached data, or None if cache doesn't exist or is invalid
    """
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                print(f"📁 Loading from cache: {cache_path}")
                return json.load(f)
        except Exception as e:
            print(f"❌ Cache read error: {e}")
    return None


def save_to_cache(data: Dict[Any, Any], cache_path: str) -> None:
    """
    Save data to cache.
    
    Args:
        data: Data to cache
        cache_path: Path to cache file
    """
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved to cache: {cache_path}")
    except Exception as e:
        print(f"❌ Cache write error: {e}")


def save_summary(summary: str, league_id: int, gameweek: int) -> str:
    """
    Save gameweek summary to file.
    
    Args:
        summary: Formatted summary text
        league_id: League ID
        gameweek: Gameweek number
    
    Returns:
        str: Path to saved file
    """
    output_dir = os.path.join(get_data_dir(), "summaries")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"league_{league_id}_gw{gameweek}_summary.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)
    
    return output_file


def get_cached_league_data() -> Dict[int, Dict[str, Any]]:
    """
    Get detailed information about cached leagues and gameweeks.
    
    Scans the cache directory to find all cached leagues and the gameweeks
    available for each league.
    
    Returns:
        dict: Mapping of league_id to dict with keys:
            - 'gameweeks': list of available gameweek numbers
            - 'team_count': number of teams in league (or None)
            - 'league_name': name of league (or None)
    """
    cache_base_dir = os.path.join(get_data_dir(), "cache")
    
    if not os.path.exists(cache_base_dir):
        return {}
    
    league_data: Dict[int, Dict[str, Any]] = {}
    
    # Scan all gameweek directories for league cache files
    for item in os.listdir(cache_base_dir):
        gw_dir = os.path.join(cache_base_dir, item)
        if os.path.isdir(gw_dir) and item.startswith('gw'):
            try:
                # Extract gameweek number
                gw_num = int(item[2:])  # Remove "gw" prefix
                
                for cache_file in os.listdir(gw_dir):
                    if cache_file.startswith('league_') and cache_file.endswith('.json'):
                        # Extract league ID from filename like "league_12345.json"
                        league_id_str = cache_file[7:-5]  # Remove "league_" prefix and ".json" suffix
                        if league_id_str.isdigit():
                            league_id = int(league_id_str)
                            if league_id not in league_data:
                                league_data[league_id] = {
                                    'gameweeks': set(),
                                    'team_count': None,
                                    'league_name': None
                                }
                            league_data[league_id]['gameweeks'].add(gw_num)
                            
                            # Get team count and league name from the most recent gameweek data
                            if league_data[league_id]['team_count'] is None or league_data[league_id]['league_name'] is None:
                                try:
                                    cache_path = os.path.join(gw_dir, cache_file)
                                    with open(cache_path, 'r') as f:
                                        data = json.load(f)
                                        if 'standings' in data and 'results' in data['standings']:
                                            league_data[league_id]['team_count'] = len(data['standings']['results'])
                                        if 'league' in data and 'name' in data['league']:
                                            league_data[league_id]['league_name'] = data['league']['name']
                                except (json.JSONDecodeError, KeyError):
                                    pass
            except (OSError, ValueError):
                continue
    
    # Convert sets to sorted lists
    for league_id in league_data:
        league_data[league_id]['gameweeks'] = sorted(league_data[league_id]['gameweeks'])

    return league_data


def generate_backup_filename(prefix: str = "fpl-cache") -> str:
    """
    Generate timestamped backup filename.

    Args:
        prefix: Filename prefix (default: "fpl-cache")

    Returns:
        str: Filename like "fpl-cache-2025-11-10-143000.zip"
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    return f"{prefix}-{timestamp}.zip"


def export_backup(output_path: Optional[str] = None) -> str:
    """
    Export cache to backup archive.

    Args:
        output_path: Optional path for backup file. If None, generates timestamped
                    file in backups directory.

    Returns:
        str: Path to created backup file

    Raises:
        FileNotFoundError: If cache directory doesn't exist or is empty
    """
    cache_dir = os.path.join(get_data_dir(), "cache")

    if not os.path.exists(cache_dir):
        raise FileNotFoundError(f"Cache directory not found: {cache_dir}")

    # Generate output path if not provided
    if output_path is None:
        output_path = os.path.join(get_backups_dir(), generate_backup_filename())

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Create archive
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add all gameweek directories
        gw_count = 0
        file_count = 0

        for item in os.listdir(cache_dir):
            item_path = os.path.join(cache_dir, item)
            if os.path.isdir(item_path) and item.startswith("gw"):
                gw_count += 1
                # Add all files in gameweek directory
                for root, dirs, files in os.walk(item_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Store with relative path from cache dir
                        arcname = os.path.relpath(file_path, cache_dir)
                        zipf.write(file_path, arcname)
                        file_count += 1

        if file_count == 0:
            raise FileNotFoundError("No cache files found to export")

        # Create metadata
        metadata = {
            "export_date": datetime.now().isoformat(),
            "tool_version": "1.0.0",  # Could be read from package metadata
            "gameweek_count": gw_count,
            "file_count": file_count
        }

        # Add metadata to archive
        zipf.writestr("metadata.json", json.dumps(metadata, indent=2))

    return output_path


def read_backup_metadata(archive_path: str) -> Dict[str, Any]:
    """
    Read metadata from backup archive.

    Args:
        archive_path: Path to backup zip file

    Returns:
        dict: Metadata from archive (export_date, tool_version, etc.)

    Raises:
        FileNotFoundError: If archive doesn't exist
        KeyError: If metadata.json not found in archive
    """
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        if 'metadata.json' not in zipf.namelist():
            # Archive without metadata - return minimal info
            return {
                "export_date": "Unknown",
                "tool_version": "Unknown",
                "gameweek_count": 0,
                "file_count": 0
            }

        metadata_content = zipf.read('metadata.json')
        return json.loads(metadata_content)


def describe_backup(archive_path: str) -> Dict[int, Dict[str, Any]]:
    """
    Read backup archive and return league data in same format as list_leagues_data().

    Args:
        archive_path: Path to backup zip file

    Returns:
        dict: League data structure matching list_leagues_data() format

    Raises:
        FileNotFoundError: If archive doesn't exist
    """
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    league_data: Dict[int, Dict[str, Any]] = {}

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        # Scan archive contents for gameweek directories and league files
        for file_path in zipf.namelist():
            # Skip metadata and non-json files
            if file_path == 'metadata.json' or not file_path.endswith('.json'):
                continue

            # Parse path: should be like "gw1/league_123456.json"
            parts = file_path.split('/')
            if len(parts) != 2:
                continue

            gw_dir, filename = parts

            # Extract gameweek number
            if not gw_dir.startswith('gw'):
                continue

            try:
                gw_num = int(gw_dir[2:])
            except ValueError:
                continue

            # Look for league files
            if filename.startswith('league_'):
                league_id_str = filename[7:-5]  # Remove "league_" prefix and ".json" suffix
                if league_id_str.isdigit():
                    league_id = int(league_id_str)

                    # Initialize league entry if needed
                    if league_id not in league_data:
                        league_data[league_id] = {
                            'gameweeks': set(),
                            'team_count': None,
                            'league_name': None
                        }

                    league_data[league_id]['gameweeks'].add(gw_num)

                    # Get team count and league name from the league file
                    if league_data[league_id]['team_count'] is None or league_data[league_id]['league_name'] is None:
                        try:
                            file_content = zipf.read(file_path)
                            data = json.loads(file_content)
                            if 'standings' in data and 'results' in data['standings']:
                                league_data[league_id]['team_count'] = len(data['standings']['results'])
                            if 'league' in data and 'name' in data['league']:
                                league_data[league_id]['league_name'] = data['league']['name']
                        except (json.JSONDecodeError, KeyError):
                            pass

    # Convert sets to sorted lists
    for league_id in league_data:
        league_data[league_id]['gameweeks'] = sorted(league_data[league_id]['gameweeks'])

    return league_data


def list_cached_gameweeks() -> List[int]:
    """
    Return list of gameweek numbers that exist in local cache.

    Returns:
        List[int]: Sorted list of gameweek numbers found in cache directory
    """
    cache_dir = os.path.join(get_data_dir(), "cache")

    if not os.path.exists(cache_dir):
        return []

    gameweeks = []
    for item in os.listdir(cache_dir):
        item_path = os.path.join(cache_dir, item)
        if os.path.isdir(item_path) and item.startswith("gw"):
            try:
                gw_num = int(item[2:])
                gameweeks.append(gw_num)
            except ValueError:
                continue

    return sorted(gameweeks)


def create_safety_backup() -> str:
    """
    Create timestamped safety backup of current cache before import.

    Returns:
        str: Path to created backup file

    Raises:
        FileNotFoundError: If cache directory doesn't exist or is empty
    """
    backup_filename = generate_backup_filename(prefix="pre-import")
    backup_path = os.path.join(get_backups_dir(), backup_filename)
    return export_backup(backup_path)


def _scan_archive_for_leagues(archive_path: str) -> List[tuple]:
    """
    Scan archive and return list of (league_id, gameweek) pairs.

    Args:
        archive_path: Path to archive file

    Returns:
        List of (league_id, gameweek) tuples found in archive
    """
    pairs = set()

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        for file_path in zipf.namelist():
            # Skip metadata and non-json files
            if file_path == 'metadata.json' or not file_path.endswith('.json'):
                continue

            # Parse path: should be like "gw1/league_123456.json"
            parts = file_path.split('/')
            if len(parts) != 2:
                continue

            gw_dir, filename = parts

            # Extract gameweek number
            if not gw_dir.startswith('gw'):
                continue

            try:
                gw_num = int(gw_dir[2:])
            except ValueError:
                continue

            # Look for league files
            if filename.startswith('league_'):
                league_id_str = filename[7:-5]  # Remove "league_" and ".json"
                if league_id_str.isdigit():
                    league_id = int(league_id_str)
                    pairs.add((league_id, gw_num))

    return sorted(list(pairs))


def _league_file_exists_locally(league_id: int, gameweek: int) -> bool:
    """
    Check if a specific league file exists in local cache.

    Args:
        league_id: League ID to check
        gameweek: Gameweek number to check

    Returns:
        bool: True if league file exists locally
    """
    cache_dir = os.path.join(get_data_dir(), "cache")
    league_file = os.path.join(cache_dir, f"gw{gameweek}", f"league_{league_id}.json")
    return os.path.exists(league_file)


def _get_related_files(archive_path: str, league_id: int, gameweek: int) -> List[str]:
    """
    Get all files that should be imported for a given league/gameweek.

    This includes:
    - The league file itself
    - All manager files for that gameweek
    - The bootstrap file for that gameweek

    Args:
        archive_path: Path to archive
        league_id: League ID
        gameweek: Gameweek number

    Returns:
        List of file paths in archive to extract
    """
    files_to_extract = []
    gw_prefix = f"gw{gameweek}/"

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        for file_path in zipf.namelist():
            if file_path.startswith(gw_prefix):
                filename = file_path.split('/')[-1]

                # Include:
                # 1. The specific league file
                if filename == f"league_{league_id}.json":
                    files_to_extract.append(file_path)

                # 2. All manager files (we'll import all managers for the gameweek)
                elif filename.startswith('manager_'):
                    files_to_extract.append(file_path)

                # 3. Bootstrap file
                elif filename == 'bootstrap.json':
                    files_to_extract.append(file_path)

    return files_to_extract


def import_backup(archive_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Import missing league/gameweek data from backup.

    Works on a per-league, per-gameweek basis:
    - Scans backup for all (league_id, gameweek) pairs
    - For each pair, checks if cache/gw{N}/league_{id}.json exists locally
    - Imports only missing combinations (along with associated files)

    Args:
        archive_path: Path to backup file
        dry_run: If True, don't actually import, just report what would happen

    Returns:
        dict: Import report with status for each league/gameweek combination
              Format: {
                  'safety_backup': str (path to backup created),
                  'league_status': {league_id: {gameweek: status}},
                  'total_imported': int,
                  'total_skipped': int,
                  'file_count': int
              }

    Raises:
        FileNotFoundError: If backup file doesn't exist
    """
    if not os.path.exists(archive_path):
        raise FileNotFoundError(f"Backup not found: {archive_path}")

    # Scan archive for all (league, gameweek) pairs
    all_pairs = _scan_archive_for_leagues(archive_path)

    # Determine which are missing locally
    missing_pairs = []
    existing_pairs = []

    for league_id, gameweek in all_pairs:
        if _league_file_exists_locally(league_id, gameweek):
            existing_pairs.append((league_id, gameweek))
        else:
            missing_pairs.append((league_id, gameweek))

    # Build status report structure
    league_status: Dict[int, Dict[int, str]] = {}
    for league_id, gameweek in all_pairs:
        if league_id not in league_status:
            league_status[league_id] = {}

        if (league_id, gameweek) in existing_pairs:
            league_status[league_id][gameweek] = '✓'  # Already exists
        elif (league_id, gameweek) in missing_pairs:
            league_status[league_id][gameweek] = '↓'  # Will import / would import

    # If dry run, return report without importing
    if dry_run:
        return {
            'safety_backup': None,
            'league_status': league_status,
            'total_imported': len(missing_pairs),
            'total_skipped': len(existing_pairs),
            'file_count': 0,
            'dry_run': True
        }

    # Create safety backup before importing
    safety_backup = None
    if missing_pairs:  # Only create backup if we're actually importing something
        try:
            safety_backup = create_safety_backup()
        except FileNotFoundError:
            # No existing cache to backup - that's okay for first import
            pass

    # Extract missing files
    cache_dir = os.path.join(get_data_dir(), "cache")
    total_files = 0

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        for league_id, gameweek in missing_pairs:
            # Get all related files for this league/gameweek
            files_to_extract = _get_related_files(archive_path, league_id, gameweek)

            # Extract each file
            for file_path in files_to_extract:
                # Extract to cache directory
                zipf.extract(file_path, cache_dir)
                total_files += 1

    return {
        'safety_backup': safety_backup,
        'league_status': league_status,
        'total_imported': len(missing_pairs),
        'total_skipped': len(existing_pairs),
        'file_count': total_files,
        'dry_run': False
    }
