import requests
import json
import os
from datetime import datetime
import click

def get_fpl_tools_dir():
    """Get the base .fpl-tools directory path"""
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".fpl-tools")

def get_cache_path(gameweek, cache_type, league_id=None, manager_id=None):
    """Generate cache file path"""
    cache_dir = os.path.join(get_fpl_tools_dir(), "cache", f"gw{gameweek}")
    os.makedirs(cache_dir, exist_ok=True)
    
    if cache_type == "bootstrap":
        return os.path.join(cache_dir, "bootstrap.json")
    elif cache_type == "league":
        return os.path.join(cache_dir, f"league_{league_id}.json")
    elif cache_type == "manager":
        return os.path.join(cache_dir, f"manager_{manager_id}.json")
    
def load_from_cache(cache_path):
    """Load data from cache if it exists"""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                print(f"📁 Loading from cache: {cache_path}")
                return json.load(f)
        except Exception as e:
            print(f"❌ Cache read error: {e}")
    return None

def save_to_cache(data, cache_path):
    """Save data to cache"""
    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved to cache: {cache_path}")
    except Exception as e:
        print(f"❌ Cache write error: {e}")

def get_fpl_league_data(league_id, gameweek=None):
    """Fetch FPL league standings data with caching"""
    cache_path = get_cache_path(gameweek, "league", league_id=league_id) if gameweek else None
    
    # Try cache first
    if cache_path:
        cached_data = load_from_cache(cache_path)
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
            save_to_cache(data, cache_path)
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def get_manager_gameweek_data(manager_id, gameweek):
    """Get detailed gameweek data for a specific manager with caching"""
    cache_path = get_cache_path(gameweek, "manager", manager_id=manager_id)
    
    # Try cache first
    cached_data = load_from_cache(cache_path)
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
        save_to_cache(data, cache_path)
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manager data: {e}")
        return None

def load_previous_gameweek_data(manager_id, gameweek):
    """Load previous gameweek data from cache only (never fetch from API)"""
    if gameweek <= 1:
        return None
    
    previous_gameweek = gameweek - 1
    cache_path = get_cache_path(previous_gameweek, "manager", manager_id=manager_id)
    
    return load_from_cache(cache_path)

def get_previous_league_standings(league_id, gameweek):
    """Get previous gameweek league standings from cache only"""
    if gameweek <= 1:
        return None
    
    previous_gameweek = gameweek - 1
    cache_path = get_cache_path(previous_gameweek, "league", league_id=league_id)
    
    previous_data = load_from_cache(cache_path)
    if previous_data:
        return previous_data['standings']['results']
    return None

def calculate_position_changes(current_standings, previous_standings):
    """Calculate position changes between gameweeks"""
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

def get_bootstrap_data(gameweek=None):
    """Get general FPL data including player names with caching"""
    cache_path = get_cache_path(gameweek, "bootstrap") if gameweek else None
    
    # Try cache first
    if cache_path:
        cached_data = load_from_cache(cache_path)
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
            save_to_cache(data, cache_path)
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching bootstrap data: {e}")
        return None

def get_player_data(player_id, bootstrap_data):
    """Get player data from ID using bootstrap data"""
    for player in bootstrap_data['elements']:
        if player['id'] == player_id:
            return player
    return None

def get_player_name(player_id, bootstrap_data):
    """Get player name from ID using bootstrap data"""
    player = get_player_data(player_id, bootstrap_data)
    if player:
        return f"{player['first_name']} {player['second_name']}"
    return "Unknown Player"

def generate_gameweek_summary(league_id, gameweek=1):
    """Generate a comprehensive gameweek summary for WhatsApp"""
    
    print("🔄 Fetching league data...")
    league_data = get_fpl_league_data(league_id, gameweek)
    if not league_data:
        return "❌ Could not fetch league data"
    
    print("🔄 Fetching player database...")
    bootstrap_data = get_bootstrap_data(gameweek)
    if not bootstrap_data:
        return "❌ Could not fetch player data"
    
    league_name = league_data['league']['name']
    standings = league_data['standings']['results']
    
    # Sort by rank
    standings.sort(key=lambda x: x['rank'])
    
    # Get position changes from previous gameweek
    previous_standings = get_previous_league_standings(league_id, gameweek)
    position_changes = calculate_position_changes(standings, previous_standings)
    
    # Find highest and lowest scores for highlighting
    highest_score = max(standings, key=lambda x: x['event_total'])
    lowest_score = min(standings, key=lambda x: x['event_total'])
    
    summary = f"🌟 *{league_name}* - Gameweek {gameweek} Summary\n\n"
    
    # Top 3
    summary += "🏆 *WEEK AS I AM*\n"
    for i, manager in enumerate(standings[:3]):
        medals = ["🥇", "🥈", "🥉"]
        summary += f"{medals[i]} {manager['player_name']} ({manager['entry_name']}) - {manager['event_total']} pts\n"
    
    summary += "\n"
    
    # Enhanced league standings
    summary += "📊 *LEAGUE IT GOOD*\n"
    for manager in standings:
        # Format position change
        change = position_changes.get(manager['entry'])
        if change is None:
            change_str = ""  # New manager or GW1
        elif change > 0:
            change_str = f"(↑{change}) " if change > 1 else "(↑1) "
        elif change < 0:
            change_str = f"(↓{abs(change)}) " if abs(change) > 1 else "(↓1) "
        else:
            change_str = "(=) "
        
        # Format awards for team name line
        awards = ""
        if manager['entry'] == highest_score['entry']:
            awards = " ⭐"
        elif manager['entry'] == lowest_score['entry']:
            awards = " 💩"
        
        # Two-line format with unified points display
        gw_points = manager['event_total']
        summary += f"{manager['rank']}. {change_str}{manager['player_name']} - {manager['total']} pts (+{gw_points})\n"
        summary += f"      {manager['entry_name']}{awards}\n"
        
    # Get captain info for each manager
    print("🔄 Fetching captain details...")
    captain_choices = {}
    special_cases = []
    
    for manager in standings:
        manager_data = get_manager_gameweek_data(manager['entry'], gameweek)
        if manager_data:
            captain_found = False
            vice_used = False
            
            for pick in manager_data['picks']:
                player_name = get_player_name(pick['element'], bootstrap_data)
                player_data = get_player_data(pick['element'], bootstrap_data)
                
                if not player_data:
                    continue
                    
                player_points = player_data['event_points']
                
                # Check if this is the active captain (multiplier = 2)
                if pick['multiplier'] == 2:
                    captain_found = True
                    
                    # Check if this was originally the vice captain (vice stepped up)
                    if pick['is_vice_captain']:
                        vice_used = True
                        special_cases.append(f"{manager['player_name']}: Vice captain {player_name} stepped up")
                    
                    # Group by captain choice
                    if player_name not in captain_choices:
                        captain_choices[player_name] = {
                            'points': player_points,
                            'managers': []
                        }
                    captain_choices[player_name]['managers'].append(manager['player_name'])
                    break
            
            # Handle edge case: neither captain nor vice played
            if not captain_found:
                special_cases.append(f"{manager['player_name']}: Neither captain nor vice captain played!")
    
    # Captain analysis
    if captain_choices:
        summary += "\n👑 *CAPTAINS LOG*\n"
        
        # Sort by points, then by popularity
        sorted_captains = sorted(captain_choices.items(), 
                               key=lambda x: (x[1]['points'], len(x[1]['managers'])), 
                               reverse=True)
        
        for captain_name, data in sorted_captains:
            managers_str = ", ".join([f"_{manager}_" for manager in data['managers']])
            summary += f"{captain_name} ({data['points']} pts):\n  {managers_str}\n"
        
        # Add special cases if any
        if special_cases:
            summary += "\n"
            for case in special_cases:
                summary += f"⚠️ {case}\n"
    
    # Get detailed data for fun categories
    print("🔄 Analyzing bench points and position stats...")
    detailed_stats = analyze_detailed_stats(standings, gameweek, bootstrap_data)
    
    # Bench points
    summary += "\n🪑 *BENCH PRESS*\n"
    if detailed_stats['bench_stats']:
        bench_leader = max(detailed_stats['bench_stats'], key=lambda x: x['bench_points'])
        summary += f"Most Points on Bench: {bench_leader['manager']} ({bench_leader['bench_points']} pts)\n"
    
    # Best by position
    summary += "\n⚽ *DOING ZONE GOOD*\n"
    if detailed_stats['position_leaders']:
        for pos, leader in detailed_stats['position_leaders'].items():
            summary += f"Best {pos.title()}: {leader['manager']} ({leader['points']} pts)\n"
    
    # Transfer analysis (for gameweeks > 1)
    if gameweek > 1 and detailed_stats['transfer_stats']:
        summary += "\n💸 *WHEELER DEALER*\n"
        
        # Show transfer activity
        active_managers = [t for t in detailed_stats['transfer_stats'] if t['transfers_made'] > 0]
        if active_managers:
            # Best and worst transfer performance first
            if detailed_stats['best_transfer']:
                best = detailed_stats['best_transfer']
                summary += f"Best Transfers: {best['manager']} ({best['new_player_points']} pts from new signings)\n"
            
            if detailed_stats['worst_transfer'] and detailed_stats['worst_transfer'] != detailed_stats['best_transfer']:
                worst = detailed_stats['worst_transfer']
                net_return = worst['new_player_points'] - worst['net_cost']
                summary += f"Worst Transfers: {worst['manager']} ({net_return:+} pts net return)\n"
            
            # Group managers by number of transfers
            transfer_groups = {}
            for manager_transfer in active_managers:
                transfers = manager_transfer['transfers_made']
                if transfers not in transfer_groups:
                    transfer_groups[transfers] = []
                
                # Format manager name with cost if applicable
                cost_str = f" (-{manager_transfer['transfer_cost']} pts)" if manager_transfer['transfer_cost'] > 0 else ""
                manager_display = f"_{manager_transfer['manager']}{cost_str}_"
                transfer_groups[transfers].append(manager_display)
            
            # Display grouped transfers (sorted by number of transfers, descending)
            summary += "\n"
            for transfer_count in sorted(transfer_groups.keys(), reverse=True):
                managers_str = ", ".join(transfer_groups[transfer_count])
                plural = "transfers" if transfer_count > 1 else "transfer"
                summary += f"{transfer_count} {plural}:\n  {managers_str}\n"
    
    return summary

def analyze_transfer_stats(standings, gameweek, bootstrap_data):
    """Analyze transfer activity and performance"""
    if gameweek <= 1:
        return None
        
    transfer_stats = []
    
    for manager in standings:
        current_data = get_manager_gameweek_data(manager['entry'], gameweek)
        previous_data = load_previous_gameweek_data(manager['entry'], gameweek)
        
        if not current_data or not previous_data:
            continue
            
        # Get transfer info
        transfers_made = current_data['entry_history']['event_transfers']
        transfer_cost = current_data['entry_history']['event_transfers_cost']
        
        # Skip if no transfers or used wildcard/free hit (unlimited transfers)
        active_chip = current_data.get('active_chip')
        if transfers_made == 0 or active_chip in ['wildcard', 'freehit']:
            continue
            
        # Find new players by comparing picks
        current_players = {pick['element'] for pick in current_data['picks']}
        previous_players = {pick['element'] for pick in previous_data['picks']}
        
        new_players = current_players - previous_players
        removed_players = previous_players - current_players
        
        # Calculate points scored by new players
        new_player_points = 0
        new_player_details = []
        
        for player_id in new_players:
            player_data = get_player_data(player_id, bootstrap_data)
            if player_data:
                points = player_data['event_points']
                # Check if player was in starting XI (not bench)
                for pick in current_data['picks']:
                    if pick['element'] == player_id and pick['multiplier'] > 0:
                        new_player_points += points * pick['multiplier']
                        new_player_details.append({
                            'name': get_player_name(player_id, bootstrap_data),
                            'points': points,
                            'multiplier': pick['multiplier']
                        })
                        break
        
        transfer_stats.append({
            'manager': manager['player_name'],
            'transfers_made': transfers_made,
            'transfer_cost': transfer_cost,
            'new_player_points': new_player_points,
            'new_player_details': new_player_details,
            'net_cost': transfer_cost,  # Points deducted for transfers
        })
    
    return transfer_stats

def analyze_detailed_stats(standings, gameweek, bootstrap_data):
    """Analyze bench points, positional performance, and transfers"""
    bench_stats = []
    position_stats = {'defence': [], 'midfield': [], 'attack': []}
    
    for manager in standings:
        manager_data = get_manager_gameweek_data(manager['entry'], gameweek)
        if not manager_data:
            continue
            
        # Calculate bench points
        bench_points = 0
        playing_squad = []
        
        for pick in manager_data['picks']:
            player_data = get_player_data(pick['element'], bootstrap_data)
            if not player_data:
                continue
                
            player_points = player_data['event_points']
            
            # Check if player is on bench (multiplier = 0 or position > 11)
            if pick['multiplier'] == 0:
                bench_points += player_points
            else:
                playing_squad.append({
                    'player_data': player_data,
                    'points': player_points * pick['multiplier'],
                    'position_type': get_position_type(player_data['element_type'])
                })
        
        bench_stats.append({
            'manager': manager['player_name'],
            'bench_points': bench_points
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
    
    # Get transfer analysis
    transfer_stats = analyze_transfer_stats(standings, gameweek, bootstrap_data)
    best_transfer = None
    worst_transfer = None
    
    if transfer_stats:
        # Find best performing transfers (highest points from new players)
        best_transfer = max(transfer_stats, key=lambda x: x['new_player_points'])
        # Find worst performing transfers (lowest points relative to cost)
        worst_transfer = min(transfer_stats, key=lambda x: x['new_player_points'] - x['net_cost'])
    
    return {
        'bench_stats': bench_stats,
        'position_leaders': position_leaders,
        'transfer_stats': transfer_stats,
        'best_transfer': best_transfer,
        'worst_transfer': worst_transfer
    }

def get_position_type(element_type):
    """Map FPL position types to our categories"""
    # 1=GK, 2=DEF, 3=MID, 4=FWD
    position_map = {
        1: 'defence',  # Goalkeeper counts as defence
        2: 'defence',
        3: 'midfield', 
        4: 'attack'
    }
    return position_map.get(element_type, 'unknown')

@click.command()
@click.option('--league-id', '-l', required=True, type=int, help='FPL league ID')
@click.option('--gameweek', '-g', required=True, type=int, help='Gameweek number')
def main(league_id, gameweek):
    """Generate FPL gameweek summary for a specific league and gameweek."""
    
    print("🚀 Generating FPL Gameweek Summary...")
    summary = generate_gameweek_summary(league_id, gameweek)
    print("\n" + "="*50)
    print("WHATSAPP READY SUMMARY:")
    print("="*50)
    print(summary)
    
    # Create output directory in .fpl-tools
    output_dir = os.path.join(get_fpl_tools_dir(), "summaries")
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to file
    output_file = os.path.join(output_dir, f"gw{gameweek}_summary.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"\n💾 Summary saved to '{output_file}'")

if __name__ == "__main__":
    main()