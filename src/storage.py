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


def get_cache_path(gameweek: int, cache_type: str, league_id: Optional[int] = None, 
                   manager_id: Optional[int] = None) -> str:
    """
    Generate cache file path for a specific data type.
    
    Args:
        gameweek: Gameweek number
        cache_type: Type of cache ('bootstrap', 'league', or 'manager')
        league_id: League ID (required for 'league' type)
        manager_id: Manager ID (required for 'manager' type)
    
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


def export_cache(output_path: Optional[str] = None) -> str:
    """
    Export cache to zip archive.

    Args:
        output_path: Optional path for archive. If None, generates timestamped
                    file in backups directory.

    Returns:
        str: Path to created archive file

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
