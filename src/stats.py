"""
Stats Module - Season-Long Statistics Analysis

Analyzes cached gameweek data to produce aggregate statistics across the season:
- Most gameweeks won
- Best position scores (defence/midfield/attack)
- Highest bench points
- Best chip returns
- Most transfer points spent

This module is self-contained with both analysis and display formatting.
"""

from typing import List, Dict, Any, Optional, Tuple
from . import storage, fpl


def get_available_gameweeks(league_id: int) -> List[int]:
    """
    Get all cached gameweeks for a league.

    Args:
        league_id: League ID

    Returns:
        list: Sorted list of gameweek numbers that have cached data
    """
    league_data = storage.get_cached_league_data()
    if league_id in league_data:
        return league_data[league_id]['gameweeks']
    return []


def parse_gameweek_range(range_str: Optional[str], available: List[int]) -> List[int]:
    """
    Parse gameweek range string into list of gameweek numbers.

    Args:
        range_str: Range string - None, "all", "1-10", or "1,3,5"
        available: List of available gameweeks

    Returns:
        list: Sorted list of gameweek numbers to process

    Raises:
        ValueError: If range format is invalid or gameweeks unavailable
    """
    # Default to all available gameweeks
    if range_str is None or range_str.lower() == "all":
        return available

    # Parse range like "1-10"
    if "-" in range_str:
        try:
            parts = range_str.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid range format: {range_str}. Expected format like '1-10'")
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            gameweeks = list(range(start, end + 1))
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid range format: {range_str}. Expected format like '1-10'") from e
    # Parse comma-separated like "1,3,5"
    elif "," in range_str:
        try:
            gameweeks = [int(gw.strip()) for gw in range_str.split(",")]
        except ValueError as e:
            raise ValueError(f"Invalid gameweek list format: {range_str}. Expected format like '1,3,5'") from e
    # Single gameweek
    else:
        try:
            gameweeks = [int(range_str.strip())]
        except ValueError as e:
            raise ValueError(f"Invalid gameweek: {range_str}. Expected a number, range like '1-10', or list like '1,3,5'") from e

    # Validate all gameweeks are available
    unavailable = [gw for gw in gameweeks if gw not in available]
    if unavailable:
        raise ValueError(f"Gameweeks not in cache: {unavailable}. Available: {available}")

    return sorted(gameweeks)


def load_gameweek_data(league_id: int, gameweek: int) -> Optional[Dict[str, Any]]:
    """
    Load all necessary data for a single gameweek.

    Args:
        league_id: League ID
        gameweek: Gameweek number

    Returns:
        dict: Contains 'league_data', 'bootstrap_data', 'gameweek' keys, or None if data missing
    """
    # Load league standings
    league_path = storage.get_cache_path(gameweek, "league", league_id=league_id)
    league_data = storage.load_from_cache(league_path)
    if not league_data:
        return None

    # Load bootstrap for player lookups
    bootstrap_path = storage.get_cache_path(gameweek, "bootstrap")
    bootstrap_data = storage.load_from_cache(bootstrap_path)
    if not bootstrap_data:
        return None

    return {
        'league_data': league_data,
        'bootstrap_data': bootstrap_data,
        'gameweek': gameweek
    }


def calculate_gameweek_wins(league_id: int, gameweeks: List[int]) -> Dict[str, Any]:
    """
    Count gameweek wins per manager across all gameweeks.

    A manager "wins" a gameweek if they have the highest gameweek score
    for that gameweek. Ties count as wins for all tied managers.

    Scores come from the gameweek-pinned manager picks cache via
    fpl.load_gameweek_scores, not the league standings' volatile event_total.

    Args:
        league_id: League ID
        gameweeks: List of gameweeks to analyze

    Returns:
        dict: {
            'winners': [(manager_name, win_count), ...],  # Sorted desc by wins
            'gameweeks_processed': int
        }
    """
    win_counts: Dict[str, int] = {}
    gameweeks_processed = 0

    for gameweek in gameweeks:
        records = fpl.load_gameweek_scores(league_id, gameweek)
        if not records:
            continue

        # Find max score for this gameweek
        max_score = max(manager['event_total'] for manager in records)

        # Award win to all managers with max score (handles ties)
        for manager in records:
            if manager['event_total'] == max_score:
                manager_name = manager['player_name']
                win_counts[manager_name] = win_counts.get(manager_name, 0) + 1

        gameweeks_processed += 1

    # Sort by wins descending
    winners = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        'winners': winners,
        'gameweeks_processed': gameweeks_processed
    }


def calculate_total_bench_points(league_id: int, gameweeks: List[int]) -> Dict[str, Any]:
    """
    Sum points_on_bench across all gameweeks per manager.

    Args:
        league_id: League ID
        gameweeks: List of gameweeks to analyze

    Returns:
        dict: {
            'totals': [(manager_name, bench_points), ...],  # Sorted desc
            'gameweeks_processed': int
        }
    """
    bench_totals: Dict[str, int] = {}
    manager_ids: Dict[str, int] = {}  # Map names to IDs
    gameweeks_processed = 0

    for gameweek in gameweeks:
        gw_data = load_gameweek_data(league_id, gameweek)
        if not gw_data:
            continue

        standings = gw_data['league_data']['standings']['results']

        # Load manager data for each manager
        for manager in standings:
            manager_name = manager['player_name']
            manager_id = manager['entry']
            manager_ids[manager_name] = manager_id

            # Load manager gameweek data
            manager_path = storage.get_cache_path(gameweek, "manager", manager_id=manager_id)
            manager_data = storage.load_from_cache(manager_path)

            if manager_data and 'entry_history' in manager_data:
                bench_points = manager_data['entry_history'].get('points_on_bench', 0)
                bench_totals[manager_name] = bench_totals.get(manager_name, 0) + bench_points

        gameweeks_processed += 1

    # Sort by bench points descending
    totals = sorted(bench_totals.items(), key=lambda x: x[1], reverse=True)

    return {
        'totals': totals,
        'gameweeks_processed': gameweeks_processed
    }


def calculate_total_transfer_cost(league_id: int, gameweeks: List[int]) -> Dict[str, Any]:
    """
    Sum transfer costs across all gameweeks per manager.

    Note: GW1 has no transfers, so we skip it.

    Args:
        league_id: League ID
        gameweeks: List of gameweeks to analyze

    Returns:
        dict: {
            'totals': [(manager_name, transfer_cost), ...],  # Sorted desc
            'gameweeks_processed': int
        }
    """
    transfer_costs: Dict[str, int] = {}
    manager_ids: Dict[str, int] = {}
    gameweeks_processed = 0

    for gameweek in gameweeks:
        # Skip GW1 as there are no transfers
        if gameweek == 1:
            continue

        gw_data = load_gameweek_data(league_id, gameweek)
        if not gw_data:
            continue

        standings = gw_data['league_data']['standings']['results']

        for manager in standings:
            manager_name = manager['player_name']
            manager_id = manager['entry']
            manager_ids[manager_name] = manager_id

            # Load manager gameweek data
            manager_path = storage.get_cache_path(gameweek, "manager", manager_id=manager_id)
            manager_data = storage.load_from_cache(manager_path)

            if manager_data and 'entry_history' in manager_data:
                cost = manager_data['entry_history'].get('event_transfers_cost', 0)
                transfer_costs[manager_name] = transfer_costs.get(manager_name, 0) + cost

        gameweeks_processed += 1

    # Sort by cost descending
    totals = sorted(transfer_costs.items(), key=lambda x: x[1], reverse=True)

    return {
        'totals': totals,
        'gameweeks_processed': gameweeks_processed
    }


def calculate_best_position_scores(league_id: int, gameweeks: List[int]) -> Dict[str, Any]:
    """
    Aggregate points by position across all gameweeks.

    Positions are mapped as:
    - Defence: Goalkeepers (1) + Defenders (2)
    - Midfield: Midfielders (3)
    - Attack: Forwards (4)

    Args:
        league_id: League ID
        gameweeks: List of gameweeks to analyze

    Returns:
        dict: {
            'defence': [(manager_name, total_points), ...],
            'midfield': [(manager_name, total_points), ...],
            'attack': [(manager_name, total_points), ...],
            'gameweeks_processed': int
        }
    """
    # Initialize position totals for each manager
    position_totals: Dict[str, Dict[str, int]] = {}  # {manager_name: {position: points}}
    gameweeks_processed = 0

    for gameweek in gameweeks:
        gw_data = load_gameweek_data(league_id, gameweek)
        if not gw_data:
            continue

        standings = gw_data['league_data']['standings']['results']
        bootstrap_data = gw_data['bootstrap_data']

        # Create player lookup for fast access
        players_by_id = {p['id']: p for p in bootstrap_data['elements']}

        for manager in standings:
            manager_name = manager['player_name']
            manager_id = manager['entry']

            # Initialize manager's position totals if needed
            if manager_name not in position_totals:
                position_totals[manager_name] = {
                    'defence': 0,
                    'midfield': 0,
                    'attack': 0
                }

            # Load manager gameweek data
            manager_path = storage.get_cache_path(gameweek, "manager", manager_id=manager_id)
            manager_data = storage.load_from_cache(manager_path)

            if not manager_data or 'picks' not in manager_data:
                continue

            # Process each pick
            for pick in manager_data['picks']:
                # Only count starting players (multiplier > 0)
                multiplier = pick['multiplier']
                if multiplier == 0:
                    continue

                player_id = pick['element']
                player = players_by_id.get(player_id)

                if not player:
                    continue

                # Get position type
                element_type = player['element_type']
                position = fpl.get_position_type(element_type)

                # Get player's points for this gameweek
                event_points = player.get('event_points', 0)
                points_scored = event_points * multiplier

                # Add to position total
                if position in position_totals[manager_name]:
                    position_totals[manager_name][position] += points_scored

        gameweeks_processed += 1

    # Sort each position by points descending
    defence_totals = sorted(
        [(name, totals['defence']) for name, totals in position_totals.items()],
        key=lambda x: x[1],
        reverse=True
    )
    midfield_totals = sorted(
        [(name, totals['midfield']) for name, totals in position_totals.items()],
        key=lambda x: x[1],
        reverse=True
    )
    attack_totals = sorted(
        [(name, totals['attack']) for name, totals in position_totals.items()],
        key=lambda x: x[1],
        reverse=True
    )

    return {
        'defence': defence_totals,
        'midfield': midfield_totals,
        'attack': attack_totals,
        'gameweeks_processed': gameweeks_processed
    }


def calculate_best_chip_returns(league_id: int, gameweeks: List[int]) -> Dict[str, Any]:
    """
    Calculate highest returns for each chip type.

    Chip types:
    - Bench Boost: Points from bench players that week
    - Triple Captain: Base points the captain scored
    - Free Hit: Total team score for the week
    - Wildcard: Total points from newly transferred players

    Args:
        league_id: League ID
        gameweeks: List of gameweeks to analyze

    Returns:
        dict: {
            'bench_boost': [(manager_name, points, gameweek), ...],
            'triple_captain': [(manager_name, points, gameweek, player_name), ...],
            'free_hit': [(manager_name, points, gameweek), ...],
            'wildcard': [(manager_name, points, gameweek), ...],
            'gameweeks_processed': int
        }
    """
    bench_boost_returns = []
    triple_captain_returns = []
    free_hit_returns = []
    wildcard_returns = []
    gameweeks_processed = 0

    for gameweek in gameweeks:
        gw_data = load_gameweek_data(league_id, gameweek)
        if not gw_data:
            continue

        standings = gw_data['league_data']['standings']['results']
        bootstrap_data = gw_data['bootstrap_data']

        # Create player lookup
        players_by_id = {p['id']: p for p in bootstrap_data['elements']}

        for manager in standings:
            manager_name = manager['player_name']
            manager_id = manager['entry']

            # Load manager gameweek data
            manager_path = storage.get_cache_path(gameweek, "manager", manager_id=manager_id)
            manager_data = storage.load_from_cache(manager_path)

            if not manager_data:
                continue

            active_chip = manager_data.get('active_chip')
            if not active_chip:
                continue

            # Bench Boost
            if active_chip == 'bboost':
                # When bench boost is active, bench players have multiplier > 0
                # Need to calculate points from positions 12-15 (bench positions)
                bench_points = 0
                if 'picks' in manager_data:
                    for pick in manager_data['picks']:
                        # Positions 12, 13, 14, 15 are the bench
                        if pick.get('position', 0) in [12, 13, 14, 15]:
                            player_id = pick['element']
                            player = players_by_id.get(player_id)
                            if player:
                                event_points = player.get('event_points', 0)
                                multiplier = pick.get('multiplier', 0)
                                bench_points += event_points * multiplier
                bench_boost_returns.append((manager_name, bench_points, gameweek))

            # Triple Captain
            elif active_chip == '3xc':
                if 'picks' in manager_data:
                    # Find the captain
                    for pick in manager_data['picks']:
                        if pick.get('is_captain') or pick.get('multiplier', 0) >= 2:
                            player_id = pick['element']
                            player = players_by_id.get(player_id)
                            if player:
                                base_points = player.get('event_points', 0)
                                player_name = fpl.get_player_short_name(player_id, bootstrap_data)
                                triple_captain_returns.append((manager_name, base_points, gameweek, player_name))
                            break

            # Free Hit
            elif active_chip == 'freehit':
                total_points = manager_data.get('entry_history', {}).get('points', 0)
                free_hit_returns.append((manager_name, total_points, gameweek))

            # Wildcard
            elif active_chip == 'wildcard':
                # Load previous gameweek data to find new players
                if gameweek > 1:
                    prev_manager_path = storage.get_cache_path(gameweek - 1, "manager", manager_id=manager_id)
                    prev_manager_data = storage.load_from_cache(prev_manager_path)

                    if prev_manager_data and 'picks' in prev_manager_data and 'picks' in manager_data:
                        # Get player IDs from previous gameweek
                        prev_player_ids = {pick['element'] for pick in prev_manager_data['picks']}

                        # Find new players and sum their points
                        wildcard_points = 0
                        for pick in manager_data['picks']:
                            player_id = pick['element']
                            # Only count new players who are starting (multiplier > 0)
                            if player_id not in prev_player_ids and pick.get('multiplier', 0) > 0:
                                player = players_by_id.get(player_id)
                                if player:
                                    event_points = player.get('event_points', 0)
                                    multiplier = pick.get('multiplier', 1)
                                    wildcard_points += event_points * multiplier

                        wildcard_returns.append((manager_name, wildcard_points, gameweek))

        gameweeks_processed += 1

    # Sort each chip type by points descending
    bench_boost_returns.sort(key=lambda x: x[1], reverse=True)
    triple_captain_returns.sort(key=lambda x: x[1], reverse=True)
    free_hit_returns.sort(key=lambda x: x[1], reverse=True)
    wildcard_returns.sort(key=lambda x: x[1], reverse=True)

    return {
        'bench_boost': bench_boost_returns,
        'triple_captain': triple_captain_returns,
        'free_hit': free_hit_returns,
        'wildcard': wildcard_returns,
        'gameweeks_processed': gameweeks_processed
    }


def calculate_season_statistics(league_id: int, gameweeks: List[int]) -> Dict[str, Any]:
    """
    Calculate all season-long statistics.

    Args:
        league_id: League ID
        gameweeks: List of gameweeks to analyze

    Returns:
        dict: {
            'league_name': str,
            'gameweeks_analyzed': List[int],
            'gameweeks_skipped': List[int],
            'stats': {
                'most_wins': {...},
                'highest_bench_points': {...},
                'most_transfer_cost': {...}
            }
        }
    """
    # Get league name from first available gameweek
    league_name = "Unknown League"
    for gameweek in gameweeks:
        gw_data = load_gameweek_data(league_id, gameweek)
        if gw_data:
            league_name = gw_data['league_data'].get('league', {}).get('name', 'Unknown League')
            break

    # Calculate statistics
    wins_data = calculate_gameweek_wins(league_id, gameweeks)
    bench_data = calculate_total_bench_points(league_id, gameweeks)
    transfer_data = calculate_total_transfer_cost(league_id, gameweeks)
    position_data = calculate_best_position_scores(league_id, gameweeks)
    chip_data = calculate_best_chip_returns(league_id, gameweeks)

    # Determine which gameweeks were skipped
    gameweeks_processed = set()
    for stat_data in [wins_data, bench_data, transfer_data, position_data, chip_data]:
        if stat_data.get('gameweeks_processed', 0) > 0:
            gameweeks_processed.add(stat_data['gameweeks_processed'])

    # For now, assume all requested gameweeks were processed
    # (We'll add proper skip tracking when we implement the more complex stats)
    gameweeks_skipped = []

    return {
        'league_name': league_name,
        'gameweeks_analyzed': gameweeks,
        'gameweeks_skipped': gameweeks_skipped,
        'stats': {
            'most_wins': wins_data,
            'best_position_scores': position_data,
            'highest_bench_points': bench_data,
            'best_chip_returns': chip_data,
            'most_transfer_cost': transfer_data
        }
    }


def format_stats_summary(stats: Dict[str, Any]) -> str:
    """
    Format season-long statistics for display.

    Args:
        stats: Statistics dictionary from calculate_season_statistics()

    Returns:
        str: Formatted text output ready for display
    """
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append(f"📊 SEASON STATISTICS - {stats['league_name']}")
    lines.append("=" * 60)

    gw_list = stats['gameweeks_analyzed']
    if len(gw_list) > 5:
        gw_range = f"GW{min(gw_list)}-{max(gw_list)}"
    else:
        gw_range = ", ".join(f"GW{gw}" for gw in gw_list)
    lines.append(f"Gameweeks analyzed: {gw_range}")
    lines.append("")

    # Most Gameweeks Won
    lines.append("🏆 MOST GAMEWEEKS WON")
    lines.append("-" * 60)
    wins_data = stats['stats']['most_wins']
    if wins_data['winners']:
        lines.extend(_format_stat_winners(wins_data['winners'], "wins"))
    else:
        lines.append("No data available")
    lines.append("")

    # Best Position Scores
    lines.append("⚽ BEST POSITION SCORES")
    lines.append("-" * 60)
    position_data = stats['stats']['best_position_scores']
    lines.extend(_format_position_scores(position_data))
    lines.append("")

    # Highest Bench Points
    lines.append("🪑 HIGHEST BENCH POINTS")
    lines.append("-" * 60)
    bench_data = stats['stats']['highest_bench_points']
    if bench_data['totals']:
        lines.extend(_format_stat_winners(bench_data['totals'], "points"))
    else:
        lines.append("No data available")
    lines.append("")

    # Best Chip Returns
    lines.append("🎴 BEST CHIP RETURNS")
    lines.append("-" * 60)
    chip_data = stats['stats']['best_chip_returns']
    lines.extend(_format_chip_returns(chip_data))
    lines.append("")

    # Most Transfer Points Spent
    lines.append("💸 MOST TRANSFER POINTS SPENT")
    lines.append("-" * 60)
    transfer_data = stats['stats']['most_transfer_cost']
    if transfer_data['totals']:
        lines.extend(_format_stat_winners(transfer_data['totals'], "points"))
    else:
        lines.append("No data available")
    lines.append("")

    # Warnings
    if stats['gameweeks_skipped']:
        lines.append("=" * 60)
        skipped_str = ", ".join(str(gw) for gw in stats['gameweeks_skipped'])
        lines.append(f"⚠️  Skipped gameweeks due to missing data: {skipped_str}")
        lines.append("")

    return "\n".join(lines)


def _format_stat_winners(winners: List[Tuple[str, int]], value_label: str, show_count: int = 3) -> List[str]:
    """
    Format a list of winners with rankings.

    Internal helper function for formatting stat results.

    Args:
        winners: List of (manager_name, value) tuples, sorted descending
        value_label: Label for the value (e.g., "wins", "points")
        show_count: Number of top entries to show (default 3)

    Returns:
        list: Formatted lines
    """
    lines = []

    if not winners:
        return ["No data available"]

    # Show top N, but include all ties for the Nth position
    # Use standard competition ranking (1, 1, 3, 3, 5...)
    rank = 1
    prev_value = None
    shown = 0
    position = 0

    for manager_name, value in winners:
        position += 1

        # Update rank when value changes (rank = current position)
        if value != prev_value:
            rank = position

        # Stop if we've shown enough (but complete ties)
        if shown >= show_count and value != prev_value:
            break

        # Format entry
        if value == 1:
            value_str = f"{value} {value_label.rstrip('s')}"  # Singular
        else:
            value_str = f"{value} {value_label}"  # Plural

        lines.append(f"{rank}. {manager_name} - {value_str}")

        prev_value = value
        shown += 1

    return lines


def _format_position_scores(position_data: Dict[str, Any]) -> List[str]:
    """
    Format position scores section.

    Internal helper function for formatting position scores.

    Args:
        position_data: Position scores data with 'defence', 'midfield', 'attack' keys

    Returns:
        list: Formatted lines
    """
    lines = []

    # Defence
    lines.append("Defence (GK + DEF):")
    if position_data['defence']:
        lines.extend(_format_stat_winners(position_data['defence'], "points"))
    else:
        lines.append("  No data available")
    lines.append("")

    # Midfield
    lines.append("Midfield:")
    if position_data['midfield']:
        lines.extend(_format_stat_winners(position_data['midfield'], "points"))
    else:
        lines.append("  No data available")
    lines.append("")

    # Attack
    lines.append("Attack:")
    if position_data['attack']:
        lines.extend(_format_stat_winners(position_data['attack'], "points"))
    else:
        lines.append("  No data available")

    return lines


def _format_chip_returns(chip_data: Dict[str, Any]) -> List[str]:
    """
    Format chip returns section.

    Internal helper function for formatting chip returns.

    Args:
        chip_data: Chip returns data with chip types as keys

    Returns:
        list: Formatted lines
    """
    lines = []

    # Bench Boost
    lines.append("Bench Boost:")
    if chip_data['bench_boost']:
        best = chip_data['bench_boost'][0]
        lines.append(f"  {best[0]} - {best[1]} points (GW{best[2]})")
    else:
        lines.append("  No Bench Boost used")
    lines.append("")

    # Triple Captain
    lines.append("Triple Captain:")
    if chip_data['triple_captain']:
        best = chip_data['triple_captain'][0]
        lines.append(f"  {best[0]} - {best[1]} points (GW{best[2]}, {best[3]})")
    else:
        lines.append("  No Triple Captain used")
    lines.append("")

    # Free Hit
    lines.append("Free Hit:")
    if chip_data['free_hit']:
        best = chip_data['free_hit'][0]
        lines.append(f"  {best[0]} - {best[1]} points (GW{best[2]})")
    else:
        lines.append("  No Free Hit used")
    lines.append("")

    # Wildcard
    lines.append("Wildcard:")
    if chip_data['wildcard']:
        best = chip_data['wildcard'][0]
        lines.append(f"  {best[0]} - {best[1]} points from new players (GW{best[2]})")
    else:
        lines.append("  No Wildcard used")

    return lines
