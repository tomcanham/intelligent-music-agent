#!/bin/bash
# Music Agent Virtual Environment Setup
# This script ensures the virtual environment is properly set up

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/music_env"

echo "🔧 Setting up Music Agent virtual environment..."

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Install requirements
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "📥 Installing dependencies..."
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
else
    echo "⚠️  No requirements.txt found, installing basic dependencies..."
    "$VENV_DIR/bin/pip" install spotipy requests
fi

echo "✅ Virtual environment setup complete!"
echo "📍 Location: $VENV_DIR"
echo "🐍 Python: $VENV_DIR/bin/python3"

# Check if the environment works
echo ""
echo "🧪 Testing environment..."
if "$VENV_DIR/bin/python3" -c "import spotipy; print('✅ spotipy imported successfully')" 2>/dev/null; then
    echo "✅ Environment is ready!"
else
    echo "❌ Environment test failed"
    exit 1
fi
