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
    
    summary = f"🌟 *{league_name}* - Gameweek {gameweek} Summary\n\n"
    
    # Top 3
    summary += "🏆 *TOP 3*\n"
    for i, manager in enumerate(standings[:3]):
        medals = ["🥇", "🥈", "🥉"]
        summary += f"{medals[i]} {manager['player_name']} ({manager['entry_name']}) - {manager['event_total']} pts\n"
    
    summary += "\n"
    
    # Full standings
    summary += "📊 *FULL TABLE*\n"
    for manager in standings:
        summary += f"{manager['rank']}. {manager['player_name']} - {manager['event_total']} pts\n"
    
    summary += "\n"
    
    # Stats
    highest_score = max(standings, key=lambda x: x['event_total'])
    lowest_score = min(standings, key=lambda x: x['event_total'])
    
    summary += "📈 *GAMEWEEK STATS*\n"
    summary += f"Highest Score: {highest_score['player_name']} ({highest_score['event_total']} pts)\n"
    summary += f"Lowest Score: {lowest_score['player_name']} ({lowest_score['event_total']} pts)\n"
    summary += f"Average: {sum(m['event_total'] for m in standings) / len(standings):.1f} pts\n"
    
    # Get captain info for each manager
    print("🔄 Fetching captain details...")
    captain_info = []
    
    for manager in standings:
        manager_data = get_manager_gameweek_data(manager['entry'], gameweek)
        if manager_data:
            for pick in manager_data['picks']:
                if pick['is_captain']:
                    captain_name = get_player_name(pick['element'], bootstrap_data)
                    # Get the player's data properly
                    player_data = get_player_data(pick['element'], bootstrap_data)
                    if player_data:
                        player_gw_points = player_data['event_points']
                        # Apply captain multiplier (usually 2x)
                        captain_points = player_gw_points * pick.get('multiplier', 2)
                        captain_info.append({
                            'manager': manager['player_name'],
                            'captain': captain_name,
                            'points': captain_points,
                            'base_points': player_gw_points
                        })
                    break
    
    # Captain analysis
    if captain_info:
        summary += "\n👑 *CAPTAIN CHOICES*\n"
        captain_info.sort(key=lambda x: x['points'], reverse=True)
        
        for cap in captain_info:
            summary += f"{cap['manager']}: {cap['captain']} ({cap['base_points']} x2 = {cap['points']} pts)\n"
        
        # Most popular captain
        from collections import Counter
        captain_counts = Counter([cap['captain'] for cap in captain_info])
        most_popular = captain_counts.most_common(1)[0]
        
        summary += f"\nMost Popular Captain: {most_popular[0]} ({most_popular[1]} managers)\n"
    
    # Get detailed data for fun categories
    print("🔄 Analyzing bench points and position stats...")
    detailed_stats = analyze_detailed_stats(standings, gameweek, bootstrap_data)
    
    # Bench points
    summary += "\n🪑 *BENCH WARMERS*\n"
    if detailed_stats['bench_stats']:
        bench_leader = max(detailed_stats['bench_stats'], key=lambda x: x['bench_points'])
        summary += f"Most Points on Bench: {bench_leader['manager']} ({bench_leader['bench_points']} pts)\n"
    
    # Best by position
    summary += "\n⚽ *POSITIONAL KINGS*\n"
    if detailed_stats['position_leaders']:
        for pos, leader in detailed_stats['position_leaders'].items():
            summary += f"Best {pos.title()}: {leader['manager']} ({leader['points']} pts)\n"
    
    # Transfer analysis (for future weeks)
    if gameweek > 1 and detailed_stats['best_transfer']:
        transfer = detailed_stats['best_transfer']
        summary += f"\n💰 *TRANSFER MASTERCLASS*\n"
        summary += f"Best New Signing: {transfer['player']} ({transfer['points']} pts) - {transfer['manager']}\n"
    
    return summary

def analyze_detailed_stats(standings, gameweek, bootstrap_data):
    """Analyze bench points, positional performance, and transfers"""
    bench_stats = []
    position_stats = {'defence': [], 'midfield': [], 'attack': []}
    transfer_stats = []
    
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
        
        # Transfer analysis (for future implementation)
        # This would require comparing with previous gameweek data
    
    # Find position leaders
    position_leaders = {}
    for pos, stats in position_stats.items():
        if stats:
            leader = max(stats, key=lambda x: x['points'])
            position_leaders[pos] = leader
    
    return {
        'bench_stats': bench_stats,
        'position_leaders': position_leaders,
        'best_transfer': None  # Will implement for future gameweeks
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