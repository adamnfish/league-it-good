import requests
import json
from datetime import datetime

def get_fpl_league_data(league_id):
    """Fetch FPL league standings data"""
    url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

def get_manager_gameweek_data(manager_id, gameweek):
    """Get detailed gameweek data for a specific manager"""
    url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/event/{gameweek}/picks/"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manager data: {e}")
        return None

def get_bootstrap_data():
    """Get general FPL data including player names"""
    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
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
    league_data = get_fpl_league_data(league_id)
    if not league_data:
        return "❌ Could not fetch league data"
    
    print("🔄 Fetching player database...")
    bootstrap_data = get_bootstrap_data()
    if not bootstrap_data:
        return "❌ Could not fetch player data"
    
    league_name = league_data['league']['name']
    standings = league_data['standings']['results']
    
    # Sort by rank
    standings.sort(key=lambda x: x['rank'])
    
    summary = f"🏆 **{league_name}** - Gameweek {gameweek} Summary\n\n"
    
    # Top 3
    summary += "🥇🥈🥉 **TOP 3** 🥉🥈🥇\n"
    for i, manager in enumerate(standings[:3]):
        medals = ["🥇", "🥈", "🥉"]
        summary += f"{medals[i]} {manager['player_name']} ({manager['entry_name']}) - {manager['event_total']} pts\n"
    
    summary += "\n"
    
    # Full standings
    summary += "📊 **FULL TABLE**\n"
    for manager in standings:
        rank_emoji = "🔺" if manager['rank'] <= 3 else "🔻" if manager['rank'] >= len(standings) - 2 else "➖"
        summary += f"{manager['rank']}. {rank_emoji} {manager['player_name']} - {manager['event_total']} pts\n"
    
    summary += "\n"
    
    # Stats
    highest_score = max(standings, key=lambda x: x['event_total'])
    lowest_score = min(standings, key=lambda x: x['event_total'])
    
    summary += "📈 **GAMEWEEK STATS**\n"
    summary += f"🎯 Highest Score: {highest_score['player_name']} ({highest_score['event_total']} pts)\n"
    summary += f"😬 Lowest Score: {lowest_score['player_name']} ({lowest_score['event_total']} pts)\n"
    summary += f"📊 Average: {sum(m['event_total'] for m in standings) / len(standings):.1f} pts\n"
    
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
        summary += "\n⚡ **CAPTAIN CHOICES**\n"
        captain_info.sort(key=lambda x: x['points'], reverse=True)
        
        for cap in captain_info:
            summary += f"👑 {cap['manager']}: {cap['captain']} ({cap['base_points']} x2 = {cap['points']} pts)\n"
        
        # Most popular captain
        from collections import Counter
        captain_counts = Counter([cap['captain'] for cap in captain_info])
        most_popular = captain_counts.most_common(1)[0]
        
        summary += f"\n📊 Most Popular Captain: {most_popular[0]} ({most_popular[1]} managers)\n"
    
    summary += f"\n🗓️ Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    summary += f"\n🤖 Next gameweek predictions coming soon! 📈"
    
    return summary

# Main execution
if __name__ == "__main__":
    league_id = 892307
    gameweek = 1
    
    print("🚀 Generating FPL Gameweek Summary...")
    summary = generate_gameweek_summary(league_id, gameweek)
    print("\n" + "="*50)
    print("WHATSAPP READY SUMMARY:")
    print("="*50)
    print(summary)
    
    # Save to file
    with open(f"gw{gameweek}_summary.txt", "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"\n💾 Summary saved to 'gw{gameweek}_summary.txt'")