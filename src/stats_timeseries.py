"""
Time Series Stats Module

Produces week-by-week data for line charts. All functions read purely from
the existing cache via load_gameweek_data — no additional API calls needed.

Complements stats.py (which produces aggregate season totals) by reshaping
the same underlying data into per-gameweek series suitable for line charts.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import fpl


# Type aliases for clarity
ManagerName = str
Gameweek = int
Points = int
Rank = int

WeeklySeries = Dict[ManagerName, List[Tuple[Gameweek, Points]]]
RankSeries = Dict[ManagerName, List[Tuple[Gameweek, Rank]]]


# ---------------------------------------------------------------------------
# Core time series functions
# ---------------------------------------------------------------------------

def calculate_weekly_scores(
    league_id: int,
    gameweeks: List[int],
) -> WeeklySeries:
    """
    Return each manager's points scored in each gameweek.

    Scores come from the gameweek-pinned manager picks cache via
    fpl.load_gameweek_scores, not the league standings' volatile event_total.

    Args:
        league_id: League ID.
        gameweeks: Sorted list of gameweeks to include.

    Returns:
        Dict mapping manager FPL name to a list of (gameweek, points) tuples,
        sorted chronologically. Managers missing from a gameweek's data are
        simply absent from that gameweek's entry rather than given a zero.
    """
    series: WeeklySeries = {}

    for gameweek in gameweeks:
        records = fpl.load_gameweek_scores(league_id, gameweek)
        if not records:
            continue

        for manager in records:
            name: ManagerName = manager["player_name"]
            gw_points: Points = manager["event_total"]
            series.setdefault(name, []).append((gameweek, gw_points))

    # Ensure each manager's list is sorted chronologically
    return {name: sorted(pts, key=lambda x: x[0]) for name, pts in series.items()}


def calculate_weekly_rankings(
    league_id: int,
    gameweeks: List[int],
) -> RankSeries:
    """
    Return each manager's league position at the end of each gameweek.

    Position is derived from cumulative total_points at each gameweek,
    not from the FPL API's rank field (which reflects the global rank).
    Ties share the higher rank: two managers tied on second place both
    receive rank 2, and rank 3 is skipped.

    Args:
        league_id: League ID.
        gameweeks: Sorted list of gameweeks to include.

    Returns:
        Dict mapping manager FPL name to a list of (gameweek, rank) tuples,
        sorted chronologically.
    """
    series: RankSeries = {}

    for gameweek in gameweeks:
        records = fpl.load_gameweek_scores(league_id, gameweek)
        if not records:
            continue

        # Sort by cumulative total descending to derive mini-league rank
        sorted_standings = sorted(
            records, key=lambda m: m["total"], reverse=True
        )

        rank = 1
        for i, manager in enumerate(sorted_standings):
            # When a manager's total is lower than the one above, rank advances
            # past all tied positions (standard competition ranking / 1224 ranking)
            if i > 0 and manager["total"] < sorted_standings[i - 1]["total"]:
                rank = i + 1

            name: ManagerName = manager["player_name"]
            series.setdefault(name, []).append((gameweek, rank))

    return {name: sorted(ranks, key=lambda x: x[0]) for name, ranks in series.items()}


def calculate_cumulative_points(
    weekly_scores: WeeklySeries,
) -> WeeklySeries:
    """
    Derive running cumulative totals from weekly scores.

    This is a pure transformation — it takes the output of
    calculate_weekly_scores and produces a running sum per manager.
    Keeping it separate means the weekly scores data isn't recalculated.

    Args:
        weekly_scores: Output of calculate_weekly_scores.

    Returns:
        Dict mapping manager FPL name to a list of (gameweek, cumulative_points)
        tuples, sorted chronologically.
    """
    cumulative: WeeklySeries = {}

    for manager, scores in weekly_scores.items():
        running = 0
        # Anchor every manager at (0, 0) so all lines start from the same
        # origin in the chart — easier to read close races at the start.
        cumulative[manager] = [(0, 0)]
        for gameweek, points in sorted(scores, key=lambda x: x[0]):
            running += points
            cumulative[manager].append((gameweek, running))

    return cumulative


def calculate_weekly_wins_losses(
    league_id: int,
    gameweeks: List[int],
) -> Dict[ManagerName, Dict[str, int]]:
    """
    Count wins, losses, and mid-table finishes per manager across all gameweeks.

    A "win" is the highest score in the league that week (ties count as wins
    for all tied managers). A "loss" is the lowest score (ties count as losses
    for all). Everything in between is "mid".

    Args:
        league_id: League ID.
        gameweeks: Sorted list of gameweeks to include.

    Returns:
        Dict mapping manager FPL name to a dict with keys:
            'wins':   int — number of gameweek wins
            'losses': int — number of gameweek losses
            'mid':    int — number of mid-table finishes
    """
    results: Dict[ManagerName, Dict[str, int]] = {}

    for gameweek in gameweeks:
        records = fpl.load_gameweek_scores(league_id, gameweek)
        if not records:
            continue

        scores = [(m["player_name"], m["event_total"]) for m in records]

        if not scores:
            continue

        max_score = max(s for _, s in scores)
        min_score = min(s for _, s in scores)

        for name, score in scores:
            if name not in results:
                results[name] = {"wins": 0, "losses": 0, "mid": 0}

            if score == max_score and score == min_score:
                # Only one manager, or all tied — count as win
                results[name]["wins"] += 1
            elif score == max_score:
                results[name]["wins"] += 1
            elif score == min_score:
                results[name]["losses"] += 1
            else:
                results[name]["mid"] += 1

    return results


def calculate_score_consistency(
    weekly_scores: WeeklySeries,
) -> Dict[ManagerName, Dict[str, float]]:
    """
    Calculate scoring consistency metrics per manager.

    Uses the weekly scores from calculate_weekly_scores. Useful for
    identifying managers who were reliably solid vs those who spiked
    and crashed.

    Args:
        weekly_scores: Output of calculate_weekly_scores.

    Returns:
        Dict mapping manager FPL name to a dict with keys:
            'mean':   float — average weekly score
            'std':    float — standard deviation of weekly scores
            'high':   float — best single gameweek score
            'low':    float — worst single gameweek score
            'range':  float — high minus low
    """
    consistency: Dict[ManagerName, Dict[str, float]] = {}

    for manager, scores in weekly_scores.items():
        if not scores:
            continue

        values = [pts for _, pts in scores]

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance ** 0.5
        high = float(max(values))
        low = float(min(values))

        consistency[manager] = {
            "mean": round(mean, 2),
            "std": round(std, 2),
            "high": high,
            "low": low,
            "range": high - low,
        }

    return consistency


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def calculate_all_timeseries(
    league_id: int,
    gameweeks: List[int],
) -> Dict[str, object]:
    """
    Calculate all time series data in one call.

    Computes weekly scores once and derives cumulative points from it,
    avoiding redundant cache reads.

    Args:
        league_id: League ID.
        gameweeks: Sorted list of gameweeks to include.

    Returns:
        Dict with keys:
            'weekly_scores':      WeeklySeries
            'weekly_rankings':    RankSeries
            'cumulative_points':  WeeklySeries
            'wins_losses':        Dict[str, Dict[str, int]]
            'consistency':        Dict[str, Dict[str, float]]
    """
    weekly_scores = calculate_weekly_scores(league_id, gameweeks)

    return {
        "weekly_scores": weekly_scores,
        "weekly_rankings": calculate_weekly_rankings(league_id, gameweeks),
        "cumulative_points": calculate_cumulative_points(weekly_scores),
        "wins_losses": calculate_weekly_wins_losses(league_id, gameweeks),
        "consistency": calculate_score_consistency(weekly_scores),
    }
