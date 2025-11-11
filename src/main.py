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
@click.option('--list-backups', is_flag=True, help='List all backup files')
@click.option('--export-backup', type=click.Path(), default=None,
              help='Export cache to backup file')
@click.option('--describe-backup', type=str, default=None,
              help='Show information about a backup (filename in backups directory)')
@click.option('--describe-backup-file', type=click.Path(exists=True), default=None,
              help='Show information about a backup (full path to backup file)')
@click.option('--import-backup', type=str, default=None,
              help='Import missing gameweeks from backup (filename in backups directory)')
@click.option('--import-backup-file', type=click.Path(exists=True), default=None,
              help='Import missing gameweeks from backup (full path to backup file)')
@click.option('--dry-run', is_flag=True,
              help='Show what would be imported without making changes')
def cli(league_id, gameweek, list_leagues, list_backups, export_backup, describe_backup, describe_backup_file,
        import_backup, import_backup_file, dry_run):
    """Generate FPL gameweek summary for a specific league and gameweek."""

    if list_leagues:
        # Call the function to list leagues
        league_data = storage.get_cached_league_data()
        display.format_admin_table(league_data)
        return

    if list_backups:
        # List backup archives
        backups = storage.list_backups()
        backups_dir = storage.get_backups_dir()
        display.format_backups_list(backups, backups_dir)
        return

    if export_backup:
        # Export cache to backup
        try:
            print("📦 Creating backup...")
            backup_path = storage.export_backup(export_backup)
            print(f"✓ Backup created: {backup_path}")
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Failed to create backup: {e}")
        return

    if describe_backup or describe_backup_file:
        # Check mutual exclusivity
        if describe_backup and describe_backup_file:
            print("❌ Error: Cannot use both --describe-backup and --describe-backup-file")
            return

        # Resolve backup path
        backup_path = describe_backup_file if describe_backup_file else storage.resolve_backup_name(describe_backup)

        # Describe backup archive contents
        try:
            # Read and display metadata
            metadata = storage.read_backup_metadata(backup_path)
            print(f"Backup Archive: {backup_path}")
            print(f"Exported: {metadata.get('export_date', 'Unknown')}")
            print(f"Tool Version: {metadata.get('tool_version', 'Unknown')}")
            print()

            # Display league data using existing format
            league_data = storage.describe_backup(backup_path)
            display.format_admin_table(league_data)
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Failed to describe backup: {e}")
        return

    if import_backup or import_backup_file:
        # Check mutual exclusivity
        if import_backup and import_backup_file:
            print("❌ Error: Cannot use both --import-backup and --import-backup-file")
            return

        # Resolve backup path
        backup_path = import_backup_file if import_backup_file else storage.resolve_backup_name(import_backup)

        # Import missing data from backup
        try:
            if dry_run:
                print("DRY RUN: No changes will be made\n")
                print(f"Would import from backup:\n{backup_path}\n")
            else:
                print(f"Importing from backup:\n{backup_path}\n")

            # Perform import (or dry-run)
            import_result = storage.import_backup(backup_path, dry_run=dry_run)

            # Get league metadata from archive for display
            league_data = storage.describe_backup(backup_path)

            # Show safety backup info (if created)
            if import_result['safety_backup'] and not dry_run:
                print(f"Created safety backup: {import_result['safety_backup']}\n")

            # Display import table
            display.format_import_table(league_data, import_result['league_status'])

            # Show summary
            print()
            if dry_run:
                print("Summary:")
                print(f"↓ Would import: {import_result['total_imported']} league/gameweek combinations")
                print(f"- Would skip: {import_result['total_skipped']} combinations (already exist)")
                print("\nRun without --dry-run to perform import")
            else:
                print("Summary:")
                print(f"↓ Total imported: {import_result['total_imported']} league/gameweek combinations ({import_result['file_count']} files)")
                print(f"- Total skipped: {import_result['total_skipped']} combinations (already exist)")

        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Failed to import backup: {e}")
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
