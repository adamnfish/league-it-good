"""
Main Module - Application Entry Point

Orchestrates the application workflow:
- CLI argument parsing using Click
- Coordinates between storage, fpl, analysis, and display modules
- Application-level error handling
- Progress logging

This is the glue that ties all the modules together.
"""

import click
from . import storage, fpl, analysis, display


def generate_summary(league_id: int, gameweek: int) -> str:
    """
    Generate a comprehensive gameweek summary.
    
    Orchestrates the entire process of fetching data, analyzing it,
    and formatting the output.
    
    Args:
        league_id: FPL league ID
        gameweek: Gameweek number
    
    Returns:
        str: Formatted gameweek summary
    """
    print("🔄 Fetching league data...")
    league_data = fpl.fetch_league_standings(league_id, gameweek)
    if not league_data:
        return "❌ Could not fetch league data"
    
    print("🔄 Fetching player database...")
    bootstrap_data = fpl.fetch_bootstrap_data(gameweek)
    if not bootstrap_data:
        return "❌ Could not fetch player data"
    
    league_name = league_data['league']['name']
    standings = league_data['standings']['results']
    
    # Sort by rank
    standings.sort(key=lambda x: x['rank'])
    
    # Get position changes from previous gameweek
    previous_standings = fpl.get_previous_league_standings(league_id, gameweek)
    position_changes = analysis.calculate_position_changes(standings, previous_standings)
    
    # Analyze captain choices
    print("🔄 Fetching captain details...")
    captain_choices = analysis.analyze_captain_choices(standings, gameweek, bootstrap_data)
    
    # Analyze bench and positions
    print("🔄 Analyzing bench points and position stats...")
    bench_position_data = analysis.analyze_bench_and_positions(standings, gameweek, bootstrap_data)
    
    # Analyze chip usage
    print("🔄 Checking chip usage...")
    chip_usage = analysis.analyze_chip_usage(standings, gameweek)
    
    # Analyze differential picks
    print("🔄 Analyzing differential picks...")
    best_differential = analysis.analyze_best_differential(standings, gameweek, bootstrap_data)
    
    # Analyze transfers (if applicable)
    transfer_stats = None
    if gameweek > 1:
        print("🔄 Analyzing transfers...")
        transfer_stats = analysis.analyze_transfers(standings, gameweek, bootstrap_data)
    
    # Generate formatted summary
    summary = display.format_gameweek_summary(
        league_name=league_name,
        gameweek=gameweek,
        standings=standings,
        position_changes=position_changes,
        captain_choices=captain_choices,
        bench_stats=bench_position_data['bench_stats'],
        position_leaders=bench_position_data['position_leaders'],
        chip_usage=chip_usage,
        best_differential=best_differential,
        transfer_stats=transfer_stats
    )
    
    return summary


@click.command()
@click.option('--league-id', '-l', type=int, help='FPL league ID')
@click.option('--gameweek', '-g', type=int, help='Gameweek number')
@click.option('--list-leagues', is_flag=True, help='List all cached league IDs')
@click.option('--export-cache', type=click.Path(), default=None,
              help='Export cache to archive file')
@click.option('--describe-backup', type=click.Path(exists=True), default=None,
              help='Show information about a backup archive')
def cli(league_id, gameweek, list_leagues, export_cache, describe_backup):
    """Generate FPL gameweek summary for a specific league and gameweek."""

    if list_leagues:
        # Call the function to list leagues
        league_data = storage.get_cached_league_data()
        display.format_admin_table(league_data)
        return

    if export_cache:
        # Export cache to archive
        try:
            print("📦 Exporting cache...")
            archive_path = storage.export_cache(export_cache)
            print(f"✓ Cache exported to: {archive_path}")
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Failed to export cache: {e}")
        return

    if describe_backup:
        # Describe backup archive contents
        try:
            # Read and display metadata
            metadata = storage.read_backup_metadata(describe_backup)
            print(f"Backup Archive: {describe_backup}")
            print(f"Exported: {metadata.get('export_date', 'Unknown')}")
            print(f"Tool Version: {metadata.get('tool_version', 'Unknown')}")
            print()

            # Display league data using existing format
            league_data = storage.describe_backup(describe_backup)
            display.format_admin_table(league_data)
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Failed to describe backup: {e}")
        return

    # Validate required arguments for summary generation
    if not league_id or not gameweek:
        print("Error: --league-id (-l) and --gameweek (-g) are required for generating summaries")
        print("Use --help for usage information")
        return
    
    print("🚀 Generating FPL Gameweek Summary...")
    summary = generate_summary(league_id, gameweek)
    print("\n" + "="*50)
    print(summary)
    
    # Save to file
    output_file = storage.save_summary(summary, league_id, gameweek)
    print(f"\n💾 Summary saved to '{output_file}'")


if __name__ == "__main__":
    cli()
