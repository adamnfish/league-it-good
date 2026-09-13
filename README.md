# League it Good

A Python tool for generating comprehensive Fantasy Premier League gameweek summaries and statistics.

## Features

- Fetches data from the official FPL API
- Generates detailed gameweek summaries with:
  - League standings with position changes
  - Chip usage overview
  - Captain analysis with triple captain indicators
  - Positional performance breakdown
  - Bench points tracking with bench boost highlights
  - Best differential picks
  - Transfer analysis with wildcard indicators (requires previous gameweek data)
- Season-long statistics (`lig stats`) across all cached gameweeks:
  - Most gameweek wins
  - Best positional scores (defence / midfield / attack)
  - Highest points left on the bench
  - Best chip returns
  - Most points spent on transfer hits
- Visual charts (`lig graphs`) rendered as PNGs:
  - Weekly scores, league position, and cumulative points across the season
  - Wins/losses, bench points, transfer costs, positional and consistency breakdowns
  - Per-chip return charts
- Administrative tools:
  - League cache management
  - Skipped section notifications
- Caches API responses to minimize requests
- Outputs WhatsApp-ready formatted text

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency and
environment management, and needs Python 3.11 or newer.

The toolchain is pinned in `mise.toml` and `.python-version`, so if you use
[mise](https://mise.jdx.dev/) both Python 3.13 and uv are provisioned for you:

```bash
mise install
```

Otherwise install uv 0.11 or newer yourself, and make sure Python 3.13 is
available. Then:

```bash
uv sync
```

That creates `.venv`, installs the project and its dependencies from
`uv.lock`, and makes the `lig` and `league-it-good` commands available.

Run commands either through uv:

```bash
uv run lig --help
```

Or activate the virtual environment first:

```bash
source .venv/bin/activate
lig --help
```

### Development

`uv sync` installs the `dev` dependency group (pytest) by default. Run the
test suite with:

```bash
uv run pytest
```

To add or remove a dependency, use `uv add <package>` or `uv remove <package>`
rather than editing `pyproject.toml` by hand. This keeps `uv.lock` in step.
Commit the updated `uv.lock` alongside the `pyproject.toml` change.

## Usage

```bash
# Generate gameweek summary
lig gen --league-id YOUR_LEAGUE_ID --gameweek 1

# Or use the full name
league-it-good gen --league-id YOUR_LEAGUE_ID --gameweek 1

# Fetch and cache data for a gameweek (a single league, or all cached leagues with --all)
lig fetch --league-id YOUR_LEAGUE_ID --gameweek 1

# Season-long aggregate statistics across cached gameweeks
lig stats --league-id YOUR_LEAGUE_ID

# List cached leagues and their available gameweeks
lig leagues

# Show help
lig --help
```

### Graphs

`lig graphs` renders a folder of PNG charts (cover-sheet legend, weekly
scores, league position, cumulative points, global standing, wins/losses,
bench points, transfer costs, positional breakdown, consistency, and one
chart per chip) for a league. Output goes to
`~/.fpl-tools/graphs/<league-id>/`. The global standing chart places every
manager on the worldwide field as a percentile (with top 25/50/75% reference
lines), so you can see where the league sits among all FPL players.

Each league needs a small TOML config holding display names and per-manager
colours. Bootstrap one from cached data:

```bash
# Writes ~/.fpl-tools/config/leagues/YOUR_LEAGUE_ID.toml
lig graphs-config -l YOUR_LEAGUE_ID
```

Open the file and edit `display_name`, `colour`, and (optionally)
`avatar` for each manager. Avatars are local PNG files placed at
`~/.fpl-tools/config/avatars/<name>.png` and referenced as
`avatar = "avatars/<name>.png"` in the TOML. Managers without an avatar
fall back to a coloured circle with their initials.

Then render:

```bash
# All charts (the default)
lig graphs -l YOUR_LEAGUE_ID

# Just one chart — see `lig graphs --list` for available names
lig graphs -l YOUR_LEAGUE_ID --chart cumulative_points

# Restrict to a gameweek range
lig graphs -l YOUR_LEAGUE_ID -g 1-20
```

Charts read only from `~/.fpl-tools/cache/` — populate it with `lig fetch`
or `lig gen` first.

### Syncing backups to S3

`lig sync` keeps the cache in step with an S3 bucket, so several machines can
share the same data.

Deploy the bucket and IAM role once:

```bash
aws cloudformation deploy \
  --stack-name league-it-good-backups \
  --template-file cloudformation/league-it-good-backups.yaml \
  --capabilities CAPABILITY_NAMED_IAM

aws cloudformation describe-stacks --stack-name league-it-good-backups \
  --query 'Stacks[0].Outputs'
```

The outputs give the bucket name, the role ARN, and a link for switching to
the role in the AWS console. Add a profile that assumes the role to
`~/.aws/config`:

```ini
[profile lig]
role_arn = arn:aws:iam::123456789012:role/lig-backup-sync
source_profile = default
```

The source profile's user or role needs permission to call `sts:AssumeRole`
on `lig-backup-sync`.

Give the profile and bucket as options (`--profile`, `--bucket`) or
environment variables:

```bash
export LIG_AWS_PROFILE=lig
export LIG_S3_BUCKET=<bucket name from the stack outputs>

lig sync --dry-run    # Preview
lig sync              # Copy files missing on either side
lig sync save         # Upload only
lig sync load         # Download only
```

Files are stored under `<season>/cache/` in the bucket. The season defaults to
the current one (e.g. `2026-27`, changing each July). Use `--season` or
`LIG_SEASON` to choose another.

Sync never deletes files. A file that exists on both sides with different
contents is listed in the report and left unchanged. To replace these files,
give a direction:

- `lig sync save --overwrite` replaces the S3 copies with the local ones. The
  bucket keeps previous versions for 90 days.
- `lig sync load --overwrite` replaces the local copies with the S3 ones,
  after writing a `pre-sync-*.zip` backup to the backups directory.

## Output

### Gameweek Summaries
The script generates:
- Console output with the formatted summary
- A saved file in `~/.fpl-tools/summaries/` directory
- Cached API responses in `~/.fpl-tools/cache/` for faster subsequent runs

### Graphs
- PNG charts written to `~/.fpl-tools/graphs/<league-id>/`
- League configs at `~/.fpl-tools/config/leagues/<league-id>.toml`
- Avatars at `~/.fpl-tools/config/avatars/<name>.png`

### Administrative Commands
- `leagues` shows a comprehensive table of cached league data including:
  - League IDs and names
  - Number of teams in each league
  - Available gameweeks with missing weeks highlighted
