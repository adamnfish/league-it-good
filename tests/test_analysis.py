"""
Tests for analysis.py

Manager history is supplied by monkeypatching fpl.fetch_manager_history, so no
real cache or FPL API is needed.

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
