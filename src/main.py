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


@click.group(invoke_without_command=True, context_settings={'help_option_names': ['-h', '--help']})
@click.pass_context
def cli(ctx):
    """
    League it Good - Fantasy Premier League gameweek summary generator.

    \b
    Generate gameweek 11 summary for league ID 123456:
        lig gen -l 123456 -g 11
    """
    # If no subcommand is provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


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

    # Analyze chip availability
    print("🔄 Checking chip availability...")
    chip_availability = analysis.analyze_chip_availability(standings, gameweek)

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
        transfer_stats=transfer_stats,
        chip_availability=chip_availability
    )
    
    return summary


@cli.command()
@click.option('--league-id', '-l', type=int, required=True, help='FPL league ID')
@click.option('--gameweek', '-g', type=int, required=True, help='Gameweek number')
def gen(league_id, gameweek):
    """Generate FPL gameweek summary for a specific league and gameweek."""
    print("🚀 Generating FPL Gameweek Summary...")
    summary = generate_summary(league_id, gameweek)
    print("\n" + "="*50)
    print(summary)

    # Save to file
    output_file = storage.save_summary(summary, league_id, gameweek)
    print(f"\n💾 Summary saved to '{output_file}'")


@cli.command('list-leagues')
def list_leagues_cmd():
    """List all cached league IDs and their available gameweeks."""
    league_data = storage.get_cached_league_data()
    display.format_admin_table(league_data)


@cli.command('list-backups')
def list_backups_cmd():
    """List all backup files in the backups directory."""
    backups = storage.list_backups()
    backups_dir = storage.get_backups_dir()
    display.format_backups_list(backups, backups_dir)


@cli.command()
@click.option('--export', '-e', 'export_path', is_flag=False, flag_value='', default=None,
              help='Export cache to backup file (optionally specify path)')
@click.option('--import', '-i', 'import_name', type=str, default=None,
              help='Import missing gameweeks from backup')
@click.option('--describe', '-d', 'describe_name', type=str, default=None,
              help='Show information about a backup')
@click.option('--file', '-f', 'use_full_path', is_flag=True,
              help='Treat argument as full path instead of filename in backups directory')
@click.option('--dry-run', is_flag=True,
              help='Show what would be imported without making changes (import only)')
def backup(export_path, import_name, describe_name, use_full_path, dry_run):
    """Manage backup archives (export, import, or describe)."""

    # Determine if export was requested (None = not requested, '' = requested with default, other = custom path)
    export_requested = export_path is not None

    # Normalize export_path: empty string means use default (None to storage.export_backup)
    if export_path == '':
        export_path = None

    # Count how many operations were requested
    operations = sum([export_requested, import_name is not None, describe_name is not None])

    if operations == 0:
        print("❌ Error: Must specify one of --export, --import, or --describe")
        print("Use 'lig backup --help' for usage information")
        return

    if operations > 1:
        print("❌ Error: Cannot use --export, --import, and --describe together")
        print("Please specify only one operation")
        return

    # Export operation
    if export_requested:
        try:
            print("📦 Creating backup...")
            backup_path = storage.export_backup(export_path if export_path else None)
            print(f"✓ Backup created: {backup_path}")
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Failed to create backup: {e}")
        return

    # Describe operation
    if describe_name:
        # Resolve backup path based on --file flag
        backup_path = describe_name if use_full_path else storage.resolve_backup_name(describe_name)

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

    # Import operation
    if import_name:
        # Resolve backup path based on --file flag
        backup_path = import_name if use_full_path else storage.resolve_backup_name(import_name)

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


if __name__ == "__main__":
    cli()
