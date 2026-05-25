"""
FPL Module - Fantasy Premier League API & Data Layer

Handles all interactions with the FPL API and data structures:
- Fetching data from FPL API endpoints
- Parsing API responses
- Player and team lookup utilities
- Position type mapping

This module knows about FPL data structures but has no caching logic
(delegates to storage module) and no analysis logic (delegates to analysis module).
"""

import requests
from typing import Optional, Dict, Any
from . import storage


def fetch_league_standings(league_id: int, gameweek: Optional[int] = None) -> Optional[Dict[Any, Any]]:
    """
    Fetch FPL league standings data with caching.
    
    Args:
        league_id: FPL league ID
        gameweek: Gameweek number (for caching), optional
    
    Returns:
        dict: League data including standings, or None on error
    """
    cache_path = storage.get_cache_path(gameweek, "league", league_id=league_id) if gameweek else None
    
    # Try cache first
    if cache_path:
        cached_data = storage.load_from_cache(cache_path)
        if cached_data:
            return cached_data
    
    # Fetch from API
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    
    try:
        print(f"🌐 Fetching league data from API...")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Save to cache
        if cache_path:
            storage.save_to_cache(data, cache_path)
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def fetch_manager_gameweek(manager_id: int, gameweek: int) -> Optional[Dict[Any, Any]]:
    """
    Get detailed gameweek data for a specific manager with caching.
    
    Args:
        manager_id: Manager ID
        gameweek: Gameweek number
    
    Returns:
        dict: Manager's gameweek data including picks, or None on error
    """
    cache_path = storage.get_cache_path(gameweek, "manager", manager_id=manager_id)
    
    # Try cache first
    cached_data = storage.load_from_cache(cache_path)
    if cached_data:
        return cached_data
    
    # Fetch from API
    url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/event/{gameweek}/picks/"
    
    try:
        print(f"🌐 Fetching manager {manager_id} data from API...")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Save to cache
        storage.save_to_cache(data, cache_path)
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manager data: {e}")
        return None


def load_previous_gameweek_data(manager_id: int, gameweek: int) -> Optional[Dict[Any, Any]]:
    """
    Load previous gameweek data from cache only (never fetch from API).
    
    Args:
        manager_id: Manager ID
        gameweek: Current gameweek number
    
    Returns:
        dict: Previous gameweek data, or None if not available
    """
    if gameweek <= 1:
        return None
    
    previous_gameweek = gameweek - 1
    cache_path = storage.get_cache_path(previous_gameweek, "manager", manager_id=manager_id)
    
    return storage.load_from_cache(cache_path)


def get_previous_league_standings(league_id: int, gameweek: int) -> Optional[list]:
    """
    Get previous gameweek league standings from cache only.
    
    Args:
        league_id: League ID
        gameweek: Current gameweek number
    
    Returns:
        list: Previous standings results, or None if not available
    """
    if gameweek <= 1:
        return None
    
    previous_gameweek = gameweek - 1
    cache_path = storage.get_cache_path(previous_gameweek, "league", league_id=league_id)
    
    previous_data = storage.load_from_cache(cache_path)
    if previous_data:
        return previous_data['standings']['results']
    return None


# Tracks (league_id, gameweek, entry) rows already warned about this run, so the
# stale-standings guard reports each once even though several stat functions read
# the same gameweek.
_warned_stale_rows: set = set()


def load_gameweek_scores(league_id: int, gameweek: int) -> Optional[list]:
    """
    Return per-manager score records for a single gameweek, with scores sourced
    from the gameweek-pinned manager picks cache rather than the league
    standings' event_total / total fields.

    The league standings endpoint is fetched without a gameweek parameter, so
    its event_total reflects whichever gameweek was live when the file was
    written — wrong for any standings file captured at the wrong time (or
    restored from a backup with mismatched contents). The manager picks endpoint
    (entry/{id}/event/{gw}/picks/) is pinned to the gameweek, so its
    entry_history.points / total_points are reliable.

    Uses the standings only for league membership (entry -> name). For each
    member, reads the score from the gameweek's manager cache. When a picks
    value disagrees with the standings event_total a warning is printed
    (surfacing stale caches); when a picks file is missing it warns and falls
    back to the standings value.

    Args:
        league_id: League ID.
        gameweek: Gameweek number.

    Returns:
        List of dicts mirroring the standings result shape, or None if the
        league standings cache is missing. Each dict has keys:
            'entry':       int — manager FPL entry id
            'player_name': str — manager's name
            'entry_name':  str — manager's team name
            'event_total': int — gameweek points (authoritative)
            'total':       int — cumulative points (authoritative)
    """
    league_path = storage.get_cache_path(gameweek, "league", league_id=league_id)
    league_data = storage.load_from_cache(league_path)
    if not league_data:
        return None

    records = []
    for manager in league_data["standings"]["results"]:
        entry = manager["entry"]
        standings_event_total = manager["event_total"]
        standings_total = manager["total"]

        manager_path = storage.get_cache_path(gameweek, "manager", manager_id=entry)
        manager_data = storage.load_from_cache(manager_path)
        entry_history = (manager_data or {}).get("entry_history") or {}

        if "points" in entry_history:
            event_total = entry_history["points"]
            total = entry_history.get("total_points", standings_total)
            if event_total != standings_event_total:
                row_key = (league_id, gameweek, entry)
                if row_key not in _warned_stale_rows:
                    _warned_stale_rows.add(row_key)
                    print(
                        f"⚠️  Stale standings: GW{gameweek} league {league_id} "
                        f"{manager['player_name']} event_total={standings_event_total} "
                        f"but picks points={event_total}; using picks value"
                    )
        else:
            print(
                f"⚠️  Missing picks: GW{gameweek} league {league_id} "
                f"{manager['player_name']} (entry {entry}); "
                f"falling back to standings event_total"
            )
            event_total = standings_event_total
            total = standings_total

        records.append({
            "entry": entry,
            "player_name": manager["player_name"],
            "entry_name": manager.get("entry_name"),
            "event_total": event_total,
            "total": total,
        })

    return records


def fetch_bootstrap_data(gameweek: Optional[int] = None) -> Optional[Dict[Any, Any]]:
    """
    Get general FPL data including player names with caching.
    
    Args:
        gameweek: Gameweek number (for caching), optional
    
    Returns:
        dict: Bootstrap data including all players and teams, or None on error
    """
    cache_path = storage.get_cache_path(gameweek, "bootstrap") if gameweek else None
    
    # Try cache first
    if cache_path:
        cached_data = storage.load_from_cache(cache_path)
        if cached_data:
            return cached_data
    
    # Fetch from API
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    
    try:
        print(f"🌐 Fetching bootstrap data from API...")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Save to cache
        if cache_path:
            storage.save_to_cache(data, cache_path)
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching bootstrap data: {e}")
        return None


def get_player_by_id(player_id: int, bootstrap_data: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
    """
    Get player data from ID using bootstrap data.
    
    Args:
        player_id: Player ID
        bootstrap_data: Bootstrap data containing all players
    
    Returns:
        dict: Player data, or None if not found
    """
    for player in bootstrap_data['elements']:
        if player['id'] == player_id:
            return player
    return None


def get_player_name(player_id: int, bootstrap_data: Dict[Any, Any]) -> str:
    """
    Get player name from ID using bootstrap data.

    Args:
        player_id: Player ID
        bootstrap_data: Bootstrap data containing all players

    Returns:
        str: Player's full name, or "Unknown Player" if not found
    """
    player = get_player_by_id(player_id, bootstrap_data)
    if player:
        return f"{player['first_name']} {player['second_name']}"
    return "Unknown Player"


def get_player_short_name(player_id: int, bootstrap_data: Dict[Any, Any]) -> str:
    """
    Get the short display name (web_name) for a player.

    web_name is the colloquial name FPL uses in the UI (e.g. "Salah",
    "Gabriel") rather than the full first+second name. Preferred where
    horizontal space is tight, such as inside chart bar segments.
    """
    player = get_player_by_id(player_id, bootstrap_data)
    if player:
        return player.get("web_name") or f"{player['first_name']} {player['second_name']}"
    return "Unknown Player"


def get_team_name(team_id: int, bootstrap_data: Dict[Any, Any]) -> str:
    """
    Get team name from team ID using bootstrap data.

    Args:
        team_id: Team ID
        bootstrap_data: Bootstrap data containing all teams

    Returns:
        str: Team name, or "Unknown Team" if not found
    """
    for team in bootstrap_data['teams']:
        if team['id'] == team_id:
            return team['name']
    return "Unknown Team"


def fetch_manager_history(manager_id: int, gameweek: int) -> Optional[Dict[Any, Any]]:
    """
    Fetch manager's history data including chip usage.

    This endpoint provides manager history including which chips have been used
    throughout the season in a 'chips' array at the top level.

    Args:
        manager_id: Manager ID
        gameweek: Gameweek number (for caching)

    Returns:
        dict: Manager's history data including 'chips' array, or None on error
    """
    cache_path = storage.get_cache_path(gameweek, "history", manager_id=manager_id)

    # Try cache first
    cached_data = storage.load_from_cache(cache_path)
    if cached_data:
        return cached_data

    # Fetch from API
    url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Save to cache
        storage.save_to_cache(data, cache_path)

        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manager history data: {e}")
        return None


def get_position_type(element_type: int) -> str:
    """
    Map FPL position types to our categories.

    Args:
        element_type: FPL element type (1=GK, 2=DEF, 3=MID, 4=FWD)

    Returns:
        str: Position category ('defence', 'midfield', 'attack', or 'unknown')
    """
    position_map = {
        1: 'defence',  # Goalkeeper counts as defence
        2: 'defence',
        3: 'midfield',
        4: 'attack'
    }
    return position_map.get(element_type, 'unknown')
