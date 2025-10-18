"""
League it Good - Fantasy Premier League Gameweek Summary Generator

Legacy entry point that imports from the new modular structure.
This file maintains backward compatibility.
"""

# Import the CLI from the new modular structure
from src.main import cli as main

if __name__ == "__main__":
    main()

