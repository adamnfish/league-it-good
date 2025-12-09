"""
Analysis Module - Business Logic Layer

Contains all statistics and analysis calculations:
- Captain analysis
- Bench points calculation
- Position performance tracking
- Transfer analysis
- Chip usage tracking
- Differential picks
- Position changes between gameweeks

This module has no I/O operations (delegates to storage/fpl modules)
and no formatting logic (delegates to display module).
Pure business logic only.
"""

from typing import Dict, List, Optional, Any, Set, Tuple
from . import fpl


def calculate_position_changes(current_standings: list, previous_standings: Optional[list]) -> Dict[int, Optional[int]]:
    """
    Calculate position changes between gameweeks.
    
    Args:
        current_standings: Current gameweek standings
        previous_standings: Previous gameweek standings, or None
    
    Returns:
        dict: Mapping of manager ID to position change
            Positive = moved up, Negative = moved down, None = new manager
    """
    if not previous_standings:
        return {}
    
    # Create mapping of manager ID to previous position
    previous_positions = {}
    for manager in previous_standings:
        previous_positions[manager['entry']] = manager['rank']
    
    # Calculate changes
    position_changes = {}
    for manager in current_standings:
        manager_id = manager['entry']
        current_pos = manager['rank']
        previous_pos = previous_positions.get(manager_id)
        
        if previous_pos is not None:
            change = previous_pos - current_pos  # Positive = moved up, Negative = moved down
            position_changes[manager_id] = change
        else:
            position_changes[manager_id] = None  # New manager
    
    return position_changes


def analyze_captain_choices(standings: list, gameweek: int, bootstrap_data: Dict[Any, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze captain choices across all managers.
    
    Groups managers by their captain choice and tracks whether triple captain
    or vice captain was used.
    
    Args:
        standings: League standings
        gameweek: Gameweek number
        bootstrap_data: Bootstrap data for player lookups
    
    Returns:
        dict: Mapping of player name to dict with 'points' and 'managers' list
    """
    captain_choices = {}
    
    for manager in standings:
        manager_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
        if manager_data:
            active_chip = manager_data.get('active_chip')
            
            for pick in manager_data['picks']:
                player_name = fpl.get_player_name(pick['element'], bootstrap_data)
                player_data = fpl.get_player_by_id(pick['element'], bootstrap_data)
                
                if not player_data:
                    continue
                
                player_points = player_data['event_points']
                
                # Check if this is the active captain (multiplier = 2 or 3 for triple captain)
                if pick['multiplier'] >= 2:
                    # Group by captain choice
                    if player_name not in captain_choices:
                        captain_choices[player_name] = {
                            'points': player_points,
                            'managers': []
                        }
                    
                    # Add manager with indicators if applicable
                    manager_display = manager['player_name']
                    if pick['is_vice_captain']:
                        manager_display += " (v)"
                    if active_chip == '3xc':
                        manager_display += " *(x3)*"
                    
                    captain_choices[player_name]['managers'].append(manager_display)
                    break
    
    return captain_choices


def analyze_chip_usage(standings: list, gameweek: int) -> Dict[str, List[str]]:
    """
    Analyze chip usage for the gameweek.
    
    Args:
        standings: League standings
        gameweek: Gameweek number
    
    Returns:
        dict: Mapping of chip type to list of manager names
    """
    chip_usage = {
        'wildcard': [],
        'freehit': [],
        'bboost': [],  # Bench Boost
        '3xc': []      # Triple Captain
    }
    
    for manager in standings:
        manager_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
        if not manager_data:
            continue
        
        active_chip = manager_data.get('active_chip')
        if active_chip and active_chip in chip_usage:
            chip_usage[active_chip].append(manager['player_name'])
    
    return chip_usage


def analyze_best_differential(standings: list, gameweek: int, bootstrap_data: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Find the highest scoring player owned by only one manager (6+ points, no ties).
    
    Args:
        standings: League standings
        gameweek: Gameweek number
        bootstrap_data: Bootstrap data for player lookups
    
    Returns:
        dict: Result with 'result' (player info or None) and 'reason'
    """
    player_ownership: Dict[int, List[str]] = {}
    
    # Count ownership for each player
    for manager in standings:
        manager_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
        if not manager_data:
            continue
        
        for pick in manager_data['picks']:
            player_id = pick['element']
            if player_id not in player_ownership:
                player_ownership[player_id] = []
            player_ownership[player_id].append(manager['player_name'])
    
    # Find players owned by exactly one manager with 6+ points
    unique_picks = {}
    for player_id, managers in player_ownership.items():
        if len(managers) == 1:  # Only owned by one manager
            player_data = fpl.get_player_by_id(player_id, bootstrap_data)
            if player_data:
                points = player_data['event_points']
                if points >= 6:  # Must have at least 6 points
                    unique_picks[player_id] = {
                        'manager': managers[0],
                        'points': points,
                        'player_name': fpl.get_player_name(player_id, bootstrap_data)
                    }
    
    # Find the highest scoring unique pick, but only if there's a clear winner
    if not unique_picks:
        return {'result': None, 'reason': 'no_qualifying_picks'}
    
    # Check for ties at the highest score
    max_points = max(pick['points'] for pick in unique_picks.values())
    top_picks = [pick for pick in unique_picks.values() if pick['points'] == max_points]
    
    # Only return if there's a single standout winner
    if len(top_picks) == 1:
        return {'result': top_picks[0], 'reason': None}
    else:
        return {'result': None, 'reason': 'tie', 'tied_count': len(top_picks), 'tied_points': max_points}


def analyze_transfers(standings: list, gameweek: int, bootstrap_data: Dict[Any, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Analyze transfer activity and performance.
    
    Args:
        standings: League standings
        gameweek: Gameweek number
        bootstrap_data: Bootstrap data for player lookups
    
    Returns:
        list: Transfer stats for each manager, or None if gameweek 1
    """
    if gameweek <= 1:
        return None
    
    transfer_stats = []
    
    for manager in standings:
        current_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
        previous_data = fpl.load_previous_gameweek_data(manager['entry'], gameweek)
        
        if not current_data or not previous_data:
            continue
        
        # Get transfer info
        transfers_made = current_data['entry_history']['event_transfers']
        transfer_cost = current_data['entry_history']['event_transfers_cost']
        active_chip = current_data.get('active_chip')
        
        # Skip free hit users (they don't actually change their squad)
        # Skip if no transfers unless they used wildcard (wildcard shows transfers_made as 0)
        if active_chip == 'freehit':
            continue
        if transfers_made == 0 and active_chip != 'wildcard':
            continue
        
        # Find new players by comparing picks
        current_players = {pick['element'] for pick in current_data['picks']}
        previous_players = {pick['element'] for pick in previous_data['picks']}
        
        new_players = current_players - previous_players
        
        # For wildcard users, the actual transfer count is the number of changes made
        # (API reports 0 for wildcard transfers)
        actual_transfers = len(new_players) if active_chip == 'wildcard' else transfers_made
        
        # Calculate points scored by new players
        new_player_points = 0
        new_player_details = []
        
        for player_id in new_players:
            player_data = fpl.get_player_by_id(player_id, bootstrap_data)
            if player_data:
                points = player_data['event_points']
                # Check if player was in starting XI (not bench)
                for pick in current_data['picks']:
                    if pick['element'] == player_id and pick['multiplier'] > 0:
                        new_player_points += points * pick['multiplier']
                        new_player_details.append({
                            'name': fpl.get_player_name(player_id, bootstrap_data),
                            'points': points,
                            'multiplier': pick['multiplier']
                        })
                        break
        
        transfer_stats.append({
            'manager': manager['player_name'],
            'transfers_made': actual_transfers,
            'transfer_cost': transfer_cost,
            'new_player_points': new_player_points,
            'new_player_details': new_player_details,
            'net_cost': transfer_cost,
            'used_wildcard': active_chip == 'wildcard'
        })
    
    return transfer_stats


def analyze_bench_and_positions(standings: list, gameweek: int, bootstrap_data: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Analyze bench points and positional performance.
    
    Args:
        standings: League standings
        gameweek: Gameweek number
        bootstrap_data: Bootstrap data for player lookups
    
    Returns:
        dict: Contains 'bench_stats' and 'position_leaders'
    """
    bench_stats = []
    position_stats = {'defence': [], 'midfield': [], 'attack': []}
    
    for manager in standings:
        manager_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
        if not manager_data:
            continue
        
        # Calculate bench points
        bench_points = 0
        playing_squad = []
        active_chip = manager_data.get('active_chip')
        
        for pick in manager_data['picks']:
            player_data = fpl.get_player_by_id(pick['element'], bootstrap_data)
            if not player_data:
                continue
            
            player_points = player_data['event_points']
            
            # For bench boost, positions 12-15 are the bench (even though multiplier is 1)
            # Otherwise, bench players have multiplier 0
            is_bench = False
            if active_chip == 'bboost':
                is_bench = pick['position'] > 11
            else:
                is_bench = pick['multiplier'] == 0
            
            if is_bench:
                bench_points += player_points
            else:
                playing_squad.append({
                    'player_data': player_data,
                    'points': player_points * pick['multiplier'],
                    'position_type': fpl.get_position_type(player_data['element_type'])
                })
        
        bench_stats.append({
            'manager': manager['player_name'],
            'bench_points': bench_points,
            'used_bench_boost': active_chip == 'bboost'
        })
        
        # Calculate positional points
        pos_points = {'defence': 0, 'midfield': 0, 'attack': 0}
        for player in playing_squad:
            pos_type = player['position_type']
            if pos_type in pos_points:
                pos_points[pos_type] += player['points']
        
        for pos, points in pos_points.items():
            position_stats[pos].append({
                'manager': manager['player_name'],
                'points': points
            })
    
    # Find position leaders
    position_leaders = {}
    for pos, stats in position_stats.items():
        if stats:
            leader = max(stats, key=lambda x: x['points'])
            position_leaders[pos] = leader
    
    return {
        'bench_stats': bench_stats,
        'position_leaders': position_leaders
    }


def analyze_chip_availability(standings: list, gameweek: int) -> Dict[str, List[str]]:
    """
    Analyze which chips each manager has available.

    For the first half of the season, tracks availability of:
    - Bench Boost (BB)
    - Triple Captain (TC)
    - Wildcard (WC)
    - Free Hit (FH)

    Args:
        standings: League standings
        gameweek: Gameweek number

    Returns:
        dict: Mapping of chip pattern to list of manager names
              e.g., {'BB, TC, WC, FH': ['Manager1', 'Manager2'], 'BB, TC, FH': ['Manager3']}
    """
    # Track which chips each manager has available
    manager_chips = {}

    for manager in standings:
        history_data = fpl.fetch_manager_history(manager['entry'], gameweek)
        if not history_data:
            continue

        # Get list of chips already used from the 'chips' array at top level
        used_chips = set()
        if 'chips' in history_data:
            for chip in history_data['chips']:
                chip_name = chip.get('name')
                if chip_name:
                    used_chips.add(chip_name)

        # Determine available chips (first-half chips only)
        # FPL API chip names: 'bboost', '3xc', 'wildcard', 'freehit'
        available = []
        if 'bboost' not in used_chips:
            available.append('BB')
        if '3xc' not in used_chips:
            available.append('TC')
        if 'wildcard' not in used_chips:
            available.append('WC')
        if 'freehit' not in used_chips:
            available.append('FH')

        # Create pattern key
        if available:
            pattern = ', '.join(available)
        else:
            pattern = 'All in'  # No chips available

        if pattern not in manager_chips:
            manager_chips[pattern] = []
        manager_chips[pattern].append(manager['player_name'])

    # Sort patterns: "All chips available" first, then by number of chips (descending), then "All in" last
    def sort_key(item):
        pattern = item[0]
        if pattern == 'BB, TC, WC, FH':
            return (0, '')  # First
        elif pattern == 'All in':
            return (2, '')  # Last
        else:
            # Count commas to estimate number of chips
            chip_count = pattern.count(',') + 1
            return (1, -chip_count, pattern)  # Middle, sorted by count desc, then alphabetically

    sorted_chips = dict(sorted(manager_chips.items(), key=sort_key))

    return sorted_chips


def analyze_chip_returns(standings: list, gameweek: int, bootstrap_data: Dict[Any, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Analyze the points return for each chip used this gameweek.

    Calculates:
    - Triple Captain: Captain's base points (the extra gain from 3x vs 2x)
    - Bench Boost: Total bench points
    - Wildcard: Points from new players
    - Free Hit: Points from players in free hit team that weren't in previous team

    Args:
        standings: League standings
        gameweek: Gameweek number
        bootstrap_data: Bootstrap data for player lookups

    Returns:
        dict: Chip returns grouped by chip type
    """
    chip_returns = {
        'triple_captain': [],
        'bench_boost': [],
        'wildcard': [],
        'free_hit': []
    }

    for manager in standings:
        manager_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
        if not manager_data:
            continue

        active_chip = manager_data.get('active_chip')
        if not active_chip:
            continue

        # Triple Captain
        if active_chip == '3xc':
            # Find the captain
            for pick in manager_data['picks']:
                if pick['multiplier'] >= 2:
                    player_data = fpl.get_player_by_id(pick['element'], bootstrap_data)
                    if player_data:
                        chip_returns['triple_captain'].append({
                            'manager': manager['player_name'],
                            'player': fpl.get_player_name(pick['element'], bootstrap_data),
                            'points': player_data['event_points']
                        })
                    break

        # Bench Boost
        elif active_chip == 'bboost':
            bench_points = 0
            for pick in manager_data['picks']:
                # Bench positions are 12-15 for bench boost
                if pick['position'] > 11:
                    player_data = fpl.get_player_by_id(pick['element'], bootstrap_data)
                    if player_data:
                        bench_points += player_data['event_points']

            chip_returns['bench_boost'].append({
                'manager': manager['player_name'],
                'points': bench_points
            })

        # Wildcard or Free Hit - need to compare with previous gameweek
        elif active_chip in ['wildcard', 'freehit']:
            if gameweek <= 1:
                continue

            previous_data = fpl.load_previous_gameweek_data(manager['entry'], gameweek)
            if not previous_data:
                continue

            # Find new players
            current_players = {pick['element'] for pick in manager_data['picks']}
            previous_players = {pick['element'] for pick in previous_data['picks']}
            new_players = current_players - previous_players

            # Calculate points from new players (only counting starting XI)
            new_player_points = 0
            for player_id in new_players:
                player_data = fpl.get_player_by_id(player_id, bootstrap_data)
                if player_data:
                    # Check if player was in starting XI (multiplier > 0)
                    for pick in manager_data['picks']:
                        if pick['element'] == player_id and pick['multiplier'] > 0:
                            # Count points with multiplier (for captains)
                            new_player_points += player_data['event_points'] * pick['multiplier']
                            break

            chip_type = 'wildcard' if active_chip == 'wildcard' else 'free_hit'
            chip_returns[chip_type].append({
                'manager': manager['player_name'],
                'points': new_player_points
            })

    # Sort each chip type by points (descending)
    for chip_type in chip_returns:
        chip_returns[chip_type].sort(key=lambda x: x['points'], reverse=True)

    return chip_returns
