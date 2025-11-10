"""
Display Module - Output Formatting Layer

Handles all text formatting and output generation:
- WhatsApp-ready formatted text
- Section headings with emojis
- League table formatting
- Captain/bench/transfer displays
- Admin table display

This module has no data fetching (delegates to fpl module)
and no calculations (delegates to analysis module).
"""

import click
from typing import Dict, List, Optional, Any


def format_gameweek_summary(
    league_name: str,
    gameweek: int,
    standings: list,
    position_changes: Dict[int, Optional[int]],
    captain_choices: Dict[str, Dict[str, Any]],
    bench_stats: List[Dict[str, Any]],
    position_leaders: Dict[str, Dict[str, Any]],
    chip_usage: Dict[str, List[str]],
    best_differential: Dict[str, Any],
    transfer_stats: Optional[List[Dict[str, Any]]]
) -> str:
    """
    Generate complete gameweek summary text.
    
    Args:
        league_name: Name of the league
        gameweek: Gameweek number (1 - 38)
        standings: League standings (sorted by rank)
        position_changes: Position change data
        captain_choices: Captain analysis results
        bench_stats: Bench points analysis
        position_leaders: Best performers by position
        chip_usage: Chip usage data
        best_differential: Differential pick analysis
        transfer_stats: Transfer analysis (None for GW1)
    
    Returns:
        str: Formatted summary text ready for WhatsApp
    """
    # Find highest and lowest scores for highlighting
    highest_score = max(standings, key=lambda x: x['event_total'])
    highest_points = highest_score['event_total']

    # Find all managers tied at the top
    top_scorers = [m for m in standings if m['event_total'] == highest_points]

    lowest_score = min(standings, key=lambda x: x['event_total'])

    summary = f"🌟 *{league_name}* - Gameweek {gameweek} Summary\n\n"

    # Gameweek highlights
    average_score = sum(m['event_total'] for m in standings) / len(standings)
    summary += "🏆 *WEEK AS I AM*\n"

    # Display winner(s) - handle ties
    if len(top_scorers) == 1:
        summary += f"Week {gameweek} winner: {highest_score['player_name']} ({highest_score['entry_name']}) - {highest_score['event_total']} pts\n"
    else:
        # Multiple tied winners - use more compact format
        winner_names = ", ".join([f"{m['player_name']}" for m in top_scorers])
        summary += f"Week {gameweek} tied winners ({highest_points} pts): {winner_names}\n"
    summary += f"Wooden spoon: {lowest_score['player_name']} ({lowest_score['entry_name']}) - {lowest_score['event_total']} pts\n"
    summary += f"League average: {average_score:.1f} pts\n"
    summary += "\n"
    
    # League standings
    highest_ids = [m['entry'] for m in top_scorers]
    summary += format_league_standings(standings, position_changes, highest_ids, lowest_score['entry'], gameweek)
    
    # Captain analysis
    if captain_choices:
        summary += format_captain_analysis(captain_choices)
    
    # Position performance
    if position_leaders:
        summary += format_position_analysis(position_leaders)
    
    # Bench points
    if bench_stats:
        summary += format_bench_analysis(bench_stats)
    
    # Chip usage
    chips_used = any(managers for managers in chip_usage.values())
    if chips_used:
        summary += format_chip_usage(chip_usage)
    else:
        print(click.style("ℹ️  No chips used this gameweek - skipping 'chips' section", fg='yellow'))
    
    # Best differential
    if best_differential['result']:
        summary += format_differential_analysis(best_differential['result'])
    else:
        if best_differential['reason'] == 'tie':
            print(click.style(f"ℹ️  Tie for best differential ({best_differential['tied_count']} players with {best_differential['tied_points']} pts) - skipping 'differential' section", fg='yellow'))
        else:
            print(click.style("ℹ️  No qualifying differential picks found - skipping 'differential' section", fg='yellow'))
            print(click.style("    (requires unique player with 6+ points, no ties)", fg='cyan', dim=True))
    
    # Transfer analysis
    if gameweek > 1 and transfer_stats:
        summary += format_transfer_analysis(transfer_stats, standings, gameweek)
    elif gameweek <= 1:
        print(click.style("ℹ️  Transfer analysis not available for gameweek 1 - skipping 'WHEELER DEALER' section", fg='yellow'))
    elif not transfer_stats:
        print(click.style("ℹ️  No transfer data available - skipping 'WHEELER DEALER' section", fg='yellow'))
    
    return summary


def get_standings_title(gameweek: int) -> str:
    """Get the league standings title based on gameweek number."""
    titles = {
        1: "LET'S GO!",
        2: "TWO GOOD TO BE TRUE",
        3: "HAT TRICK HEROES",
        4: "STANDINGS FOUR NOW",
        5: "FAMOUS (GAMEWEEK) FIVE",
        6: "YOU SIX-Y THINGS",
        7: "SEVEN DEADLY WINS",
        8: "WHO DO WE APPRECI-8?",
        9: "CLOUD (GAMEWEEK) NINE",
        10: "PERFECT TEN",
        11: "THESE GO TO (GW) ELEVEN",
        12: "TWELFTH GAMEWEEK",
        13: "UNLUCKY FOR SOME?",
        16: "SWEET SIXTEEN",
        17: "DANCING QUEENS",
        18: "🔞",
        20: "HINDSIGHT IS GAMEWEEK TWENTY",
        21: "21 SECONDS TO GO",
        38: "THE FINAL COUNTDOWN"
    }
    return titles.get(gameweek, "LEAGUE IT GOOD")


def format_league_standings(standings: list, position_changes: Dict[int, Optional[int]],
                            highest_ids: List[int], lowest_id: int, gameweek: int) -> str:
    """Format the league standings table."""
    title = get_standings_title(gameweek)
    output = f"📊 *{title}*\n"

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

        # Format awards
        awards = ""
        if manager['entry'] in highest_ids:
            awards = " ⭐"
        elif manager['entry'] == lowest_id:
            awards = " 💩"
        
        # Two-line format
        gw_points = manager['event_total']
        output += f"{manager['rank']}. {change_str}{manager['player_name']} - {manager['total']} pts (+{gw_points})\n"
        output += f"      {manager['entry_name']}{awards}\n"
    
    return output


def format_captain_analysis(captain_choices: Dict[str, Dict[str, Any]]) -> str:
    """Format the captain analysis section."""
    output = "\n👑 *CAPTAINS LOG*\n"
    
    # Sort by points, then by popularity
    sorted_captains = sorted(captain_choices.items(), 
                            key=lambda x: (x[1]['points'], len(x[1]['managers'])), 
                            reverse=True)
    
    for captain_name, data in sorted_captains:
        managers_str = ", ".join([f"_{manager}_" for manager in data['managers']])
        output += f"{captain_name} ({data['points']} pts):\n  {managers_str}\n"
    
    return output


def format_position_analysis(position_leaders: Dict[str, Dict[str, Any]]) -> str:
    """Format the positional performance section."""
    output = "\n⚽ *DOING ZONE GOOD*\n"
    
    for pos, leader in position_leaders.items():
        output += f"Best {pos.title()}: {leader['manager']} ({leader['points']} pts)\n"
    
    return output


def format_bench_analysis(bench_stats: List[Dict[str, Any]]) -> str:
    """Format the bench points section."""
    output = "\n🪑 *BENCH PRESS*\n"
    
    bench_leader = max(bench_stats, key=lambda x: x['bench_points'])
    output += f"Most Points on Bench: {bench_leader['manager']} ({bench_leader['bench_points']} pts)"
    
    # Add bench boost callout if applicable
    if bench_leader.get('used_bench_boost'):
        output += " 💪"
    
    output += "\n"
    
    return output


def format_chip_usage(chip_usage: Dict[str, List[str]]) -> str:
    """Format the chip usage section."""
    output = "\n🎰 *CHIP AWAY*\n"
    
    chip_names = {
        'wildcard': 'Wildcard',
        'freehit': 'Free Hit', 
        'bboost': 'Bench Boost',
        '3xc': 'Triple Captain'
    }
    
    for chip_key, managers in chip_usage.items():
        if managers:
            chip_name = chip_names.get(chip_key, chip_key.title())
            managers_str = ", ".join([f"_{manager}_" for manager in managers])
            output += f"{chip_name}:\n  {managers_str}\n"
    
    return output


def format_differential_analysis(result: Dict[str, Any]) -> str:
    """Format the differential pick section."""
    output = "\n🎯 *HIGHCONOCLAST*\n"
    output += f"Best Differential: _{result['manager']}_\n"
    output += f"  {result['player_name']} ({result['points']} pts)\n"
    return output


def format_transfer_analysis(transfer_stats: List[Dict[str, Any]], standings: list, gameweek: int) -> str:
    """Format the transfer analysis section."""
    from . import fpl
    
    output = "\n💸 *WHEELER DEALER*\n"
    
    active_managers = [t for t in transfer_stats if t['transfers_made'] > 0]
    
    if active_managers:
        # Best and worst transfer performance
        best = max(transfer_stats, key=lambda x: x['new_player_points'])
        output += f"Best Transfers: {best['manager']} ({best['new_player_points']} pts from new signings)\n"
        
        worst = min(transfer_stats, key=lambda x: x['new_player_points'] - x['net_cost'])
        if worst != best:
            net_return = worst['new_player_points'] - worst['net_cost']
            output += f"Worst Transfers: {worst['manager']} ({net_return} pts net return)\n"
        
        # Group managers by number of transfers
        transfer_groups = {}
        for manager_transfer in active_managers:
            transfers = manager_transfer['transfers_made']
            if transfers not in transfer_groups:
                transfer_groups[transfers] = []
            
            # Format manager name with indicators
            cost_str = f" (-{manager_transfer['transfer_cost']} pts)" if manager_transfer['transfer_cost'] > 0 else ""
            wc_str = " *(wc)*" if manager_transfer['used_wildcard'] else ""
            manager_display = f"_{manager_transfer['manager']}{cost_str}{wc_str}_"
            transfer_groups[transfers].append(manager_display)
        
        # Display grouped transfers
        output += "\n"
        for transfer_count in sorted(transfer_groups.keys(), reverse=True):
            managers_str = ", ".join(transfer_groups[transfer_count])
            plural = "transfers" if transfer_count > 1 else "transfer"
            output += f"{transfer_count} {plural}:\n  {managers_str}\n"
        
        # Show managers who didn't make any transfers
        no_transfer_managers = []
        for manager in standings:
            manager_data = fpl.fetch_manager_gameweek(manager['entry'], gameweek)
            if manager_data:
                transfers_made = manager_data['entry_history']['event_transfers']
                active_chip = manager_data.get('active_chip')
                if transfers_made == 0 and active_chip not in ['wildcard', 'freehit']:
                    no_transfer_managers.append(f"_{manager['player_name']}_")
        
        if no_transfer_managers:
            managers_str = ", ".join(no_transfer_managers)
            output += f"If it ain't broke...\n  {managers_str}\n"
    
    return output


def format_admin_table(league_data: Dict[int, Dict[str, Any]]) -> None:
    """
    Display administrative table of cached leagues.
    
    Args:
        league_data: Cached league data from storage module
    """
    if not league_data:
        print("No cached league data found")
        return
    
    print("📊 Cached League Data")
    print("=" * 80)
    
    # Find the maximum gameweek across all leagues
    all_gameweeks = set()
    for data in league_data.values():
        all_gameweeks.update(data['gameweeks'])
    
    if not all_gameweeks:
        print("No gameweek data found")
        return
    
    max_gw = max(all_gameweeks)
    min_gw = min(all_gameweeks)

    # Check if any league has 50+ teams to determine column width
    has_large_league = any(
        data['team_count'] is not None and data['team_count'] >= 50
        for data in league_data.values()
    )
    team_col_width = 3 if has_large_league else 2

    # Build gameweek numbers for header
    gw_numbers = " ".join(str(gw) for gw in range(min_gw, max_gw + 1))

    # Header with 👥 emoji and GW prefix
    # Note: emoji takes 2 display columns but Python counts it as 1 char, so we need less spacing
    print(f"{'League ID':<10} {'League Name':<25} {'👥':<{team_col_width}} GW {gw_numbers}")
    print("-" * 80)

    for league_id in sorted(league_data.keys()):
        data = league_data[league_id]
        gameweeks = data['gameweeks']
        team_count = data['team_count']
        league_name = data['league_name'] or 'Unknown'

        # Truncate league name if too long
        if len(league_name) > 23:
            league_name = league_name[:20] + "..."

        if team_count is None:
            team_count_str = '?'
        elif team_count >= 50:
            team_count_str = '50+'
        else:
            team_count_str = str(team_count)

        # Build gameweek display with ✓ for present, x for missing
        # Pad icons to match width of gameweek numbers (2 chars for 10+, 1 char for 1-9)
        # Left-align so icons line up with first digit of gameweek number
        gw_display = []
        for gw in range(min_gw, max_gw + 1):
            gw_width = len(str(gw))
            if gw in gameweeks:
                gw_display.append(f"{'✓':<{gw_width}}")
            else:
                gw_display.append(click.style(f"{'x':<{gw_width}}", bold=True))

        gw_string = " ".join(gw_display)
        print(f"{league_id:<10} {league_name:<25} {team_count_str:<{team_col_width}}     {gw_string}")

    print(f"\nLegend: ✓ = gameweek cached, {click.style('x', bold=True)} = missing gameweek data")
