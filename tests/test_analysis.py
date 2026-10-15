"""
Tests for analysis.py

Manager history and picks are supplied by monkeypatching fpl.fetch_manager_history
and fpl.fetch_manager_gameweek, so no real cache or FPL API is needed.

Run with: uv run pytest tests/test_analysis.py -v
"""

from __future__ import annotations

from typing import Callable
from unittest.mock import patch

from src import analysis


# Chip windows as the FPL bootstrap data describes them: one window per half of
# the season, with wildcard and free hit only playable from gameweek 2.
BOOTSTRAP = {
    'chips': [
        {'name': 'wildcard', 'start_event': 2, 'stop_event': 19},
        {'name': 'wildcard', 'start_event': 20, 'stop_event': 38},
        {'name': 'freehit', 'start_event': 2, 'stop_event': 19},
        {'name': 'freehit', 'start_event': 20, 'stop_event': 38},
        {'name': 'bboost', 'start_event': 1, 'stop_event': 19},
        {'name': 'bboost', 'start_event': 20, 'stop_event': 38},
        {'name': '3xc', 'start_event': 1, 'stop_event': 19},
        {'name': '3xc', 'start_event': 20, 'stop_event': 38},
    ]
}

STANDINGS = [
    {'entry': 1, 'player_name': 'Adam Smith'},
    {'entry': 2, 'player_name': 'Dave Jones'},
]


def histories(chips_by_entry: dict) -> Callable:
    """Build a fetch_manager_history stand-in from entry ID to chip usage."""
    def fetch(entry: int, gameweek: int) -> dict:
        return {'chips': chips_by_entry[entry]}
    return fetch


def test_unplayable_chips_are_still_available():
    """Wildcard and free hit are held in gameweek 1 even though they can't be played."""
    with patch.object(analysis.fpl, 'fetch_manager_history',
                      histories({1: [], 2: [{'name': 'bboost', 'event': 1}]})):
        result = analysis.analyze_chip_availability(STANDINGS, 1, BOOTSTRAP)

    assert result == {
        'BB, TC, WC, FH': ['Adam Smith'],
        'TC, WC, FH': ['Dave Jones'],
    }


def test_chips_are_restored_in_the_second_half():
    """A chip used in the first half doesn't count against the second half window."""
    with patch.object(analysis.fpl, 'fetch_manager_history',
                      histories({
                          1: [{'name': 'bboost', 'event': 5}],
                          2: [{'name': 'bboost', 'event': 25}],
                      })):
        result = analysis.analyze_chip_availability(STANDINGS, 30, BOOTSTRAP)

    assert result == {
        'BB, TC, WC, FH': ['Adam Smith'],
        'TC, WC, FH': ['Dave Jones'],
    }


def test_chips_played_after_the_gameweek_are_still_available():
    """History fetched after the gameweek lists later chips, which were still held then."""
    with patch.object(analysis.fpl, 'fetch_manager_history',
                      histories({
                          1: [{'name': 'freehit', 'event': 5}],
                          2: [{'name': 'freehit', 'event': 6}],
                      })):
        result = analysis.analyze_chip_availability(STANDINGS, 5, BOOTSTRAP)

    assert result == {
        'BB, TC, WC': ['Adam Smith'],
        'BB, TC, WC, FH': ['Dave Jones'],
    }


# Player data as the bootstrap describes it when fetched in a later gameweek, so
# event_points holds that later gameweek's points rather than this one's.
PLAYERS_BOOTSTRAP = {
    'elements': [
        {'id': 10, 'first_name': 'Erling', 'second_name': 'Haaland',
         'web_name': 'Haaland', 'element_type': 4, 'team': 1, 'event_points': 1},
        {'id': 20, 'first_name': 'Antoine', 'second_name': 'Semenyo',
         'web_name': 'Semenyo', 'element_type': 3, 'team': 2, 'event_points': 1},
    ]
}

# Live data for the gameweek being summarised
LIVE = {
    'elements': [
        {'id': 10, 'stats': {'total_points': 6}},
        {'id': 20, 'stats': {'total_points': 17}},
    ]
}


def picks(picks_by_entry: dict) -> Callable:
    """Build a fetch_manager_gameweek stand-in from entry ID to picks."""
    def fetch(entry: int, gameweek: int) -> dict:
        return {'active_chip': None, 'picks': picks_by_entry[entry]}
    return fetch


def test_get_player_points_reads_gameweek_points_from_live_data():
    assert analysis.fpl.get_player_points(LIVE) == {10: 6, 20: 17}


def test_player_points_come_from_live_data_not_bootstrap():
    """Captain and differential points are the gameweek's points, not the bootstrap's event_points."""
    with patch.object(analysis.fpl, 'fetch_manager_gameweek',
                      picks({
                          1: [{'element': 10, 'position': 1, 'multiplier': 2, 'is_vice_captain': False}],
                          2: [{'element': 10, 'position': 1, 'multiplier': 2, 'is_vice_captain': False},
                              {'element': 20, 'position': 2, 'multiplier': 1, 'is_vice_captain': False}],
                      })):
        player_points = analysis.fpl.get_player_points(LIVE)
        captains = analysis.analyze_captain_choices(STANDINGS, 5, PLAYERS_BOOTSTRAP, player_points)
        differential = analysis.analyze_best_differential(STANDINGS, 5, PLAYERS_BOOTSTRAP, player_points)

    assert captains == {'Erling Haaland': {'points': 6, 'managers': ['Adam Smith', 'Dave Jones']}}
    assert differential['result'] == {
        'manager': 'Dave Jones', 'points': 17, 'player_name': 'Antoine Semenyo',
    }


def test_get_bootstrap_gameweek_is_the_current_gameweek():
    bootstrap = {'events': [
        {'id': 5, 'is_current': False},
        {'id': 6, 'is_current': True},
        {'id': 7, 'is_current': False},
    ]}
    assert analysis.fpl.get_bootstrap_gameweek(bootstrap) == 6


def test_get_bootstrap_gameweek_before_the_season_starts():
    bootstrap = {'events': [{'id': 1, 'is_current': False}]}
    assert analysis.fpl.get_bootstrap_gameweek(bootstrap) is None
