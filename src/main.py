"""
Main Module - Application Entry Point

Orchestrates the application workflow:
- CLI argument parsing using Click
- Coordinates between storage, fpl, analysis, and display modules
- Application-level error handling
- Progress logging

This is the glue that ties all the modules together.
"""

import os
from pathlib import Path

import click
from . import storage, fpl, analysis, display, stats


class GroupedCommands(click.Group):
    """Custom Click Group that organizes commands into sections."""

    def format_commands(self, ctx, formatter):
        """Format commands into grouped sections."""
        # Define command groups
        command_groups = {
            'FPL Commands': ['leagues', 'gen', 'fetch'],
            'Stats & Graphs': ['stats', 'graphs', 'graphs-config'],
            'Backup Commands': ['backups', 'export', 'import', 'describe']
        }

        # Get all commands
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None:
                continue
            if cmd.hidden:
                continue
            commands.append((subcommand, cmd))

        # If no commands, nothing to format
        if not commands:
            return

        # Format each group
        for group_name, group_commands in command_groups.items():
            # Filter commands for this group
            group_items = [(name, cmd) for name, cmd in commands if name in group_commands]
            if not group_items:
                continue

            with formatter.section(group_name):
                formatter.write_dl([(name, cmd.get_short_help_str(limit=formatter.width))
                                   for name, cmd in group_items])


@click.group(cls=GroupedCommands, invoke_without_command=True, context_settings={'help_option_names': ['-h', '--help']})
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

    # Identify current gameweek winner(s)
    highest_score_points = max(standings, key=lambda x: x['event_total'])['event_total']
    current_winners = [m for m in standings if m['event_total'] == highest_score_points]

    # Analyze winning streak
    print("🔄 Checking for winning streaks...")
    winning_streak = analysis.analyze_winning_streak(current_winners, league_id, gameweek)

    # Analyze captain choices
    print("🔄 Fetching captain details...")
    captain_choices = analysis.analyze_captain_choices(standings, gameweek, bootstrap_data)
    
    # Analyze bench and positions
    print("🔄 Analyzing bench points and position stats...")
    bench_position_data = analysis.analyze_bench_and_positions(standings, gameweek, bootstrap_data)
    
    # Analyze differential picks
    print("🔄 Analyzing differential picks...")
    best_differential = analysis.analyze_best_differential(standings, gameweek, bootstrap_data)

    # Analyze team overload violations
    print("🔄 Checking team overload violations...")
    team_overload = analysis.analyze_team_overload(standings, gameweek, bootstrap_data)

    # Analyze transfers (if applicable)
    transfer_stats = None
    if gameweek > 1:
        print("🔄 Analyzing transfers...")
        transfer_stats = analysis.analyze_transfers(standings, gameweek, bootstrap_data)

    # Analyze chip returns
    print("🔄 Analyzing chip performance...")
    chip_returns_data = analysis.analyze_chip_returns(standings, gameweek, bootstrap_data)

    # Analyze chip availability
    print("🔄 Checking chip availability...")
    chip_availability = analysis.analyze_chip_availability(standings, gameweek, bootstrap_data)

    # Generate formatted summary
    summary = display.format_gameweek_summary(
        league_name=league_name,
        gameweek=gameweek,
        standings=standings,
        position_changes=position_changes,
        captain_choices=captain_choices,
        bench_stats=bench_position_data['bench_stats'],
        position_leaders=bench_position_data['position_leaders'],
        best_differential=best_differential,
        team_overload=team_overload,
        transfer_stats=transfer_stats,
        chip_returns=chip_returns_data['chip_returns'],
        chip_returns_skipped=chip_returns_data['skipped_managers'],
        chip_availability=chip_availability,
        winning_streak=winning_streak
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


@cli.command('stats')
@click.option('--league-id', '-l', type=int, required=True, help='FPL league ID')
@click.option('--gameweek-range', '-r', type=str, help='Gameweek range: "all", "1-10", or "1,3,5" (defaults to "all")')
def stats_cmd(league_id, gameweek_range):
    """Analyze season-long aggregate statistics for a league.

    Calculates statistics across cached gameweeks:
    - Most gameweeks won
    - Best position scores (defence/midfield/attack)
    - Highest points on bench
    - Best chip returns
    - Most transfer points spent

    Examples:
      lig stats -l 123456              # All cached gameweeks
      lig stats -l 123456 -r all       # Explicit all gameweeks
      lig stats -l 123456 -r "1-10"    # Gameweeks 1-10
      lig stats -l 123456 -r "1,3,5"   # Specific gameweeks
    """
    try:
        print("📊 Analyzing season statistics...")

        # Get available gameweeks
        available_gameweeks = stats.get_available_gameweeks(league_id)
        if not available_gameweeks:
            print(f"❌ Error: No cached data found for league {league_id}")
            print(f"Run 'lig fetch -l {league_id} -g <gameweek>' to fetch data first")
            return

        # Parse gameweek range
        try:
            gameweeks = stats.parse_gameweek_range(gameweek_range, available_gameweeks)
        except ValueError as e:
            print(f"❌ Error: {e}")
            return

        print(f"Found {len(available_gameweeks)} cached gameweek(s) for league {league_id}")
        print(f"Analyzing {len(gameweeks)} gameweek(s)...\n")

        # Calculate statistics
        statistics = stats.calculate_season_statistics(league_id, gameweeks)

        # Format and display
        summary = stats.format_stats_summary(statistics)
        print(summary)

        # Save to file
        output_dir = storage.get_data_dir()
        summaries_dir = os.path.join(output_dir, "summaries")
        os.makedirs(summaries_dir, exist_ok=True)

        output_file = os.path.join(summaries_dir, f"league_{league_id}_season_stats.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(summary)

        print(f"💾 Stats saved to '{output_file}'")

    except Exception as e:
        print(f"❌ Error generating stats: {e}")
        import traceback
        traceback.print_exc()


# Stub config colour palette — keep in sync with example_config.toml.
_GRAPHS_CONFIG_COLOURS = (
    "#e63946", "#457b9d", "#2a9d8f", "#e9c46a",
    "#f4a261", "#a8dadc", "#c77dff", "#06d6a0",
    "#ef476f", "#ffd166", "#118ab2", "#8ecae6",
)


def _list_charts() -> None:
    """Print one line per chart: name and short description."""
    from .graphs import CHART_DESCRIPTIONS
    width = max(len(name) for name in CHART_DESCRIPTIONS)
    for name, desc in CHART_DESCRIPTIONS.items():
        click.echo(f"  {name.ljust(width)}  {desc}")


@cli.command('graphs')
@click.option('--league-id', '-l', type=int, required=False,
              help='FPL league ID (required unless --list is given).')
@click.option('--gameweeks', '-g', default='all', show_default=True,
              help='Gameweeks to include. "all", a range like "1-20", or a list "1,3,5".')
@click.option('--config-dir', '-c', default=None,
              type=click.Path(file_okay=False),
              help='Config directory (default: ~/.fpl-tools/config/).')
@click.option('--output-dir', '-o', default=None,
              type=click.Path(file_okay=False),
              help='Output directory (default: ~/.fpl-tools/graphs/<league-id>/).')
@click.option('--chart', 'chart_name', default=None,
              help='Render only this chart instead of all. See --list for names.')
@click.option('--season', default=None,
              help='Season label for the legend chart (e.g. "2025/26"). Derived if omitted.')
@click.option('--list', 'list_charts', is_flag=True,
              help='List available chart names and exit.')
@click.pass_context
def graphs_cmd(ctx, league_id, gameweeks, config_dir, output_dir,
               chart_name, season, list_charts):
    """Render PNG charts for a league.

    \b
    Examples:
      lig graphs --list                         # show available chart names
      lig graphs -l 123456                      # render every chart
      lig graphs -l 123456 --chart legend       # render just one chart
      lig graphs -l 123456 -g 1-20              # restrict to a gameweek range
    """
    if list_charts:
        _list_charts()
        ctx.exit(0)

    if league_id is None:
        raise click.UsageError("Missing option '-l' / '--league-id' (required unless --list is given).")

    from .graphs import CHART_NAMES, build_chart_dispatch
    from .graphs.config import load_league_config, ConfigError

    if chart_name is not None and chart_name not in CHART_NAMES:
        raise click.ClickException(
            f"Unknown chart '{chart_name}'. Valid options: {', '.join(CHART_NAMES)}"
        )

    config_path = Path(config_dir) if config_dir else Path(storage.get_config_dir())
    output_path = Path(output_dir) if output_dir else Path(storage.get_data_dir()) / "graphs" / str(league_id)

    try:
        league_config = load_league_config(config_path, league_id)
    except ConfigError as e:
        raise click.ClickException(str(e))

    available = stats.get_available_gameweeks(league_id)
    if not available:
        raise click.ClickException(
            f"No cached data found for league {league_id}. "
            f"Run 'lig fetch -l {league_id} -g <n>' first."
        )

    try:
        gw_list = stats.parse_gameweek_range(gameweeks, available)
    except ValueError as e:
        raise click.ClickException(str(e))

    # Display name precedence: config override → API name → "League <id>"
    first_gw_data = stats.load_gameweek_data(league_id, gw_list[0])
    api_name = (
        first_gw_data.get("league_data", {}).get("league", {}).get("name")
        if first_gw_data else None
    )
    league_name = league_config.name or api_name or f"League {league_id}"

    output_path.mkdir(parents=True, exist_ok=True)

    click.echo(f"Rendering graphs for {league_name}")
    click.echo(f"  Gameweeks: {gw_list[0]}–{gw_list[-1]} ({len(gw_list)} weeks)")
    click.echo(f"  Output:    {output_path}")
    click.echo()

    dispatch = build_chart_dispatch(
        league_id=league_id,
        gameweeks=gw_list,
        config=league_config,
        output_dir=output_path,
        league_name=league_name,
        season=season,
    )

    if chart_name:
        click.echo(f"  Rendering {chart_name}.png...")
        dispatch[chart_name]()
    else:
        for name, render_fn in dispatch.items():
            click.echo(f"  Rendering {name}.png...")
            render_fn()

    click.echo(f"\n  Done! Output: {output_path}")


@cli.command('graphs-config')
@click.option('--league-id', '-l', type=int, required=True, help='FPL league ID.')
@click.option('--gameweek', '-g', type=int, default=None,
              help='Gameweek to read manager list from (default: lowest cached).')
@click.option('--output-file', '-o', default=None,
              type=click.Path(dir_okay=False),
              help='Output TOML path (default: ~/.fpl-tools/config/leagues/<id>.toml).')
@click.option('--force', is_flag=True, help='Overwrite an existing config file.')
def graphs_config_cmd(league_id, gameweek, output_file, force):
    """Generate a stub TOML config file for a league.

    Reads cached league data and writes one [[managers]] entry per player,
    pre-filling fpl_name, a sensible display_name, and a cycled palette
    colour. Avatars are commented out — uncomment and supply paths to
    enable per-manager avatars.
    """
    available = stats.get_available_gameweeks(league_id)
    if not available:
        raise click.ClickException(
            f"No cached data found for league {league_id}. "
            f"Run 'lig fetch -l {league_id} -g <n>' first."
        )

    gw = gameweek if gameweek is not None else available[0]
    if gw not in available:
        raise click.ClickException(
            f"Gameweek {gw} is not cached for league {league_id}. "
            f"Available: {', '.join(str(g) for g in available)}"
        )

    gw_data = stats.load_gameweek_data(league_id, gw)
    if not gw_data:
        raise click.ClickException(f"Failed to read cached data for GW{gw}.")

    league_block = gw_data.get("league_data", {}).get("league", {})
    standings = gw_data.get("league_data", {}).get("standings", {}).get("results", [])
    if not standings:
        raise click.ClickException(f"No managers found in cached GW{gw} standings.")

    api_league_name = league_block.get("name", f"League {league_id}")

    if output_file:
        output_path = Path(output_file)
    else:
        output_path = Path(storage.get_config_dir()) / "leagues" / f"{league_id}.toml"

    if output_path.exists() and not force:
        raise click.ClickException(
            f"Config file already exists: {output_path}\n"
            f"Pass --force to overwrite."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# League graph config — generated by `lig graphs-config`.",
        "# Edit display_name, colour, and avatar to taste before running `lig graphs`.",
        "",
        "[league]",
        f"id = {league_id}",
        f'name = "{api_league_name}"',
        "",
    ]
    for i, manager in enumerate(standings):
        fpl_name = manager.get("player_name", "")
        display_name = fpl_name.split()[0] if fpl_name else f"Manager{i + 1}"
        colour = _GRAPHS_CONFIG_COLOURS[i % len(_GRAPHS_CONFIG_COLOURS)]
        avatar_slug = display_name.lower().replace(" ", "_")
        # TOML strings need double-quote escaping; FPL names are usually plain ASCII.
        escaped_fpl_name = fpl_name.replace('"', '\\"')
        escaped_display = display_name.replace('"', '\\"')
        lines.extend([
            "[[managers]]",
            f'fpl_name = "{escaped_fpl_name}"',
            f'display_name = "{escaped_display}"',
            f'colour = "{colour}"',
            f'# avatar = "avatars/{avatar_slug}.png"',
            "",
        ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    click.echo(f"Wrote stub config to {output_path}")
    click.echo(f"  Managers: {len(standings)}")
    click.echo(f"  Edit it then run: lig graphs -l {league_id}")


@cli.command()
@click.option('--league-id', '-l', type=int, help='FPL league ID to fetch')
@click.option('--gameweek', '-g', type=int, required=True, help='Gameweek number')
@click.option('--all', is_flag=True, help='Fetch for all cached leagues')
@click.option('--force', is_flag=True, help='Re-fetch even if data exists')
@click.option('--dry-run', is_flag=True, help='Show what would be fetched without making API calls')
def fetch(league_id, gameweek, all, force, dry_run):
    """Preload/refresh cache data without generating summary output.

    Useful for warming the cache before going offline, refreshing stale data,
    or testing API connectivity.

    Examples:
      lig fetch --league-id 123456 --gameweek 21
      lig fetch --gameweek 21 --all
      lig fetch --league-id 123456 --gameweek 21 --force
    """
    # Validate parameters
    if league_id and all:
        print("❌ Error: Cannot use both --league-id and --all")
        return

    if not league_id and not all:
        print("❌ Error: Must specify either --league-id or --all")
        return

    # Validate gameweek range
    if not (1 <= gameweek <= 38):
        print(f"❌ Error: Gameweek must be between 1 and 38 (got {gameweek})")
        return

    if dry_run:
        print("🔍 DRY RUN: No files will be fetched\n")

    print(f"🔄 Fetching data for Gameweek {gameweek}...\n")

    # Determine target leagues
    if all:
        league_data = storage.get_cached_league_data()
        if not league_data:
            print("❌ Error: No cached leagues found")
            return
        league_ids = list(league_data.keys())
        print(f"📊 Found {len(league_ids)} cached league(s)")
    else:
        league_ids = [league_id]

    # Track statistics
    total_files_fetched = 0
    total_files_skipped = 0
    failed_fetches = []

    # Fetch bootstrap data (once, shared across all leagues)
    bootstrap_path = storage.get_cache_path(gameweek, "bootstrap")
    if not dry_run and (force or not storage.cache_exists(bootstrap_path)):
        try:
            print("📊 Bootstrap data")
            fpl.fetch_bootstrap_data(gameweek)
            total_files_fetched += 1
            print("  ✓ Fetched bootstrap.json\n")
        except Exception as e:
            print(f"  ❌ Failed to fetch bootstrap: {e}\n")
            failed_fetches.append(("bootstrap", str(e)))
    elif dry_run:
        exists = storage.cache_exists(bootstrap_path)
        status = "exists, would skip" if exists and not force else "would fetch"
        print(f"📊 Bootstrap data ({status})\n")
    else:
        total_files_skipped += 1
        print("📊 Bootstrap data (cached)\n")

    # Fetch each league
    for idx, lid in enumerate(league_ids, 1):
        try:
            # Fetch league standings
            league_path = storage.get_cache_path(gameweek, "league", league_id=lid)

            if dry_run:
                exists = storage.cache_exists(league_path)
                status = "exists, would skip" if exists and not force else "would fetch"
                print(f"📊 League ID: {lid} ({status})")
            elif force or not storage.cache_exists(league_path):
                league_data = fpl.fetch_league_standings(lid, gameweek)
                if not league_data:
                    print(f"❌ League {lid}: Failed to fetch standings\n")
                    failed_fetches.append((f"league_{lid}", "Failed to fetch standings"))
                    continue

                league_name = league_data['league']['name']
                manager_count = len(league_data['standings']['results'])
                print(f"📊 League: {league_name} (ID: {lid})")
                print(f"  ✓ Fetched league standings ({manager_count} managers)")
                total_files_fetched += 1
            else:
                # Load from cache to get league name and manager count
                league_data = storage.load_from_cache(league_path)
                if league_data:
                    league_name = league_data['league']['name']
                    manager_count = len(league_data['standings']['results'])
                    print(f"📊 League: {league_name} (ID: {lid}) (cached)")
                    print(f"  • {manager_count} managers")
                    total_files_skipped += 1
                else:
                    print(f"📊 League ID: {lid} (cached)")
                    # Still need to fetch to get manager list
                    league_data = fpl.fetch_league_standings(lid, gameweek)
                    manager_count = len(league_data['standings']['results'])
                    total_files_fetched += 1

            if not dry_run:
                # Get manager list from league standings
                managers = league_data['standings']['results']

                # Fetch manager data
                print(f"  🔄 Fetching manager data...")
                manager_fetched = 0
                manager_skipped = 0

                for manager in managers:
                    manager_id = manager['entry']

                    # Fetch manager gameweek picks
                    manager_path = storage.get_cache_path(gameweek, "manager", manager_id=manager_id)
                    if force or not storage.cache_exists(manager_path):
                        try:
                            fpl.fetch_manager_gameweek(manager_id, gameweek)
                            manager_fetched += 1
                        except Exception as e:
                            failed_fetches.append((f"manager_{manager_id}_picks", str(e)))
                    else:
                        manager_skipped += 1

                    # Fetch manager history
                    history_path = storage.get_cache_path(gameweek, "history", manager_id=manager_id)
                    if force or not storage.cache_exists(history_path):
                        try:
                            fpl.fetch_manager_history(manager_id, gameweek)
                            manager_fetched += 1
                        except Exception as e:
                            failed_fetches.append((f"manager_{manager_id}_history", str(e)))
                    else:
                        manager_skipped += 1

                total_files_fetched += manager_fetched
                total_files_skipped += manager_skipped

                if manager_fetched > 0:
                    print(f"  ✓ {manager_fetched} file(s) fetched")
                if manager_skipped > 0:
                    print(f"  • {manager_skipped} file(s) skipped (already cached)")

            print()  # Blank line between leagues

        except Exception as e:
            print(f"❌ League {lid}: {e}\n")
            failed_fetches.append((f"league_{lid}", str(e)))

    # Summary
    print("="*50)
    if dry_run:
        print("🔍 Dry run complete - no files were fetched")
    else:
        print("✅ Fetch complete")
        print(f"  • {len(league_ids)} league(s)")
        print(f"  • {total_files_fetched} file(s) fetched")
        if total_files_skipped > 0:
            print(f"  • {total_files_skipped} file(s) skipped (use --force to refresh existing)")

    # Show failures if any
    if failed_fetches:
        print(f"\n⚠️  Some fetches failed:")
        for item, error in failed_fetches[:5]:  # Show first 5 failures
            print(f"  • {item}: {error}")
        if len(failed_fetches) > 5:
            print(f"  ... and {len(failed_fetches) - 5} more")


@cli.command('leagues')
def leagues_cmd():
    """List all cached league IDs and their available gameweeks."""
    league_data = storage.get_cached_league_data()
    display.format_admin_table(league_data)


@cli.command('backups')
def backups_cmd():
    """List all backup files in the backups directory."""
    backups = storage.list_backups()
    backups_dir = storage.get_backups_dir()
    display.format_backups_list(backups, backups_dir)


@cli.command()
@click.argument('path', required=False, default=None)
def export(path):
    """Export cache to a backup archive file.

    Creates a timestamped backup archive in the backups directory by default.
    Optionally specify a custom path for the backup file.

    Examples:
      lig export                    # Create timestamped backup in backups directory
      lig export /path/to/backup.tar.gz  # Create backup at custom path
    """
    try:
        print("📦 Creating backup...")
        backup_path = storage.export_backup(path)
        print(f"✓ Backup created: {backup_path}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")


@cli.command('import')
@click.argument('backup_name', required=True)
@click.option('--file', '-f', 'use_full_path', is_flag=True,
              help='Treat argument as full path instead of filename in backups directory')
@click.option('--dry-run', is_flag=True,
              help='Show what would be imported without making changes')
def import_backup_cmd(backup_name, use_full_path, dry_run):
    """Import missing gameweeks from a backup archive.

    By default, looks for the backup file in the backups directory by name.
    Use --file to specify a full path to the backup archive.

    Only imports gameweeks that don't already exist in your local cache.
    Creates a safety backup of your current cache before importing.

    Examples:
      lig import backup-2025-01-15.tar.gz       # Import from backups directory
      lig import backup-2025-01-15.tar.gz --dry-run  # Preview without importing
      lig import /path/to/backup.tar.gz --file  # Import from custom path
    """
    # Resolve backup path based on --file flag
    backup_path = backup_name if use_full_path else storage.resolve_backup_name(backup_name)

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


@cli.command()
@click.argument('backup_name', required=True)
@click.option('--file', '-f', 'use_full_path', is_flag=True,
              help='Treat argument as full path instead of filename in backups directory')
def describe(backup_name, use_full_path):
    """Show information about a backup archive.

    Displays metadata and league/gameweek contents of a backup file.

    Examples:
      lig describe backup-2025-01-15.tar.gz       # Describe backup in backups directory
      lig describe /path/to/backup.tar.gz --file  # Describe backup at custom path
    """
    # Resolve backup path based on --file flag
    backup_path = backup_name if use_full_path else storage.resolve_backup_name(backup_name)

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


if __name__ == "__main__":
    cli()
