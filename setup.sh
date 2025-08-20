#!/bin/bash

# FPL Gameweek Summary Generator Setup Script
echo "🚀 Setting up FPL Gameweek Summary Generator..."

echo "📦 Creating virtual environment..."
python -m venv .venv

echo "⚡ Activating virtual environment..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    # Windows
    source .env/Scripts/activate
else
    # Linux/Mac
    source .env/bin/activate
fi

echo "📥 Installing requirements..."
pip install -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "To run the FPL summary generator:"
echo "1. Activate the virtual environment:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo "   source .env/Scripts/activate"
else
    echo "   source .env/bin/activate"
fi
echo "2. Run the script:"
echo "   python gameweek.py"
echo "3. When done, deactivate:"
echo "   deactivate"
echo ""
