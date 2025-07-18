# Music Agent Project

A comprehensive music agent with Spotify integration, automatic track analysis, and reactive polling capabilities.

## Features

- 🎵 **Spotify Integration** - Search, play, and analyze tracks
- 🔍 **Fuzzy Search** - Find songs even with partial or incorrect titles
- 🎤 **Lyric Search** - Find songs by lyric fragments
- 🏷️ **Auto-tagging** - Automatically tag tracks with genres, moods, and characteristics
- 📊 **Music Analysis** - Analyze energy, mood, tempo, and danceability
- ⚡ **Reactive Polling** - Automatically detects and analyzes new tracks as they play
- 💾 **Local Database** - Stores favorites, tags, and play history
- 🔄 **Manual Sync** - Force analysis of current track with `sync` command
- 🔌 **Background Daemon** - Runs as a service with Unix socket communication

## Architecture

### Core Components

1. **`music_agent.py`** - Main music agent with comprehensive music handling
2. **`music_daemon.py`** - Background daemon that runs the music agent
3. **`music_client.py`** - Client for interacting with the daemon
4. **`music`** - Bash wrapper script for easy command-line usage

### Database Schema

The agent uses SQLite to store:
- **Favorite Artists** - User-liked artists with play counts
- **Tags** - Genres, moods, tempo, and custom tags for artists/tracks
- **Play History** - Track play history with timestamps
- **Lyric Patterns** - Known lyric fragments for song identification
- **Preferences** - User settings and configuration

## Setup

### Prerequisites

1. **Python 3.x** with required packages:
   ```bash
   pip install spotipy
   ```

2. **Spotify API credentials**:
   ```bash
   export SPOTIFY_CLIENT_ID="your_client_id"
   export SPOTIFY_CLIENT_SECRET="your_client_secret"
   ```

3. **macOS** with Spotify app installed (for AppleScript control)

### Installation

1. Set up Spotify credentials as environment variables
2. Make scripts executable:
   ```bash
   chmod +x music music_*.py
   ```
3. Start the daemon:
   ```bash
   python3 music_daemon.py --daemon
   ```

## Usage

### Starting the Service

```bash
# Start daemon in background
python3 music_daemon.py --daemon

# Start daemon in foreground (for debugging)
python3 music_daemon.py

# Check daemon status
python3 music_daemon.py --status

# Stop daemon
python3 music_daemon.py --stop
```

### Command-Line Interface

```bash
# Using the wrapper script
./music play bohemian rhapsody
./music sync  # Analyze current track
./music "what's playing"
./music "play some mellow music"
./music "like this artist"
./music favorites

# Using the client directly
python3 -c "
from music_daemon import MusicClient
client = MusicClient()
print(client.music_command('sync'))
"
```

### Supported Commands

- **Playback**: `play [song/artist]`, `play me some [artist]`
- **Search**: `search for [song]`, `find [song]`
- **Current Track**: `what's playing`, `sync`
- **Favorites**: `like this artist`, `favorites`
- **Tag-based**: `play some [mood] music`, `play something [genre]`
- **Lyric Search**: `what's that song where they say "[lyrics]"`
- **Analysis**: `what kind of music is this`, `describe this music`

## Auto-Sync Feature

The daemon automatically polls Spotify every 30 seconds to detect track changes. When a new track is detected:

1. **Track Analysis** - Retrieves detailed track information from Spotify
2. **Genre Tagging** - Automatically tags the artist with genres
3. **Database Storage** - Stores analysis results locally
4. **Logging** - Records all auto-sync activities

### Manual Sync

Force analysis of the current track:
```bash
./music sync
```

This provides detailed information including:
- Track and album details
- Release year
- Genres (auto-tagged)
- Audio characteristics (energy, mood, tempo, danceability) *when available*

## Database Location

- **Database**: `~/.music_agent.db`
- **Socket**: `~/.music_agent.sock`
- **Logs**: `~/.music_agent.log`

## API Limitations

The agent uses Spotify's Client Credentials flow, which has some limitations:
- Audio features (energy, valence, etc.) may not be available
- Some user-specific features are not accessible
- Rate limiting applies to API calls

## Recent Updates

### Reactivity Implementation (2025-07-18)
- Added hybrid polling approach for automatic track change detection
- Implemented background auto-sync functionality
- Added manual `sync` command for on-demand analysis
- Enhanced tagging system with automatic genre detection
- Improved error handling and logging throughout

The music agent now operates reactively, automatically building a comprehensive database of your music preferences and characteristics as you listen.

## Development

### Architecture Notes

The system uses a daemon/client architecture to maintain persistent state while allowing easy command-line interaction:

1. **Daemon Process** - Runs continuously, maintains Spotify connection and database
2. **Unix Socket** - Inter-process communication between daemon and clients
3. **Threaded Polling** - Background thread for automatic track change detection
4. **SQLite Database** - Persistent storage for all music data

### Adding New Features

To extend the music agent:

1. Add new command patterns to `handle_command()` in `music_agent.py`
2. Implement the feature logic in the appropriate class
3. Update the database schema if needed (see `init_database()`)
4. Add corresponding client commands in `music_daemon.py`
5. Update this README with new usage examples

## Troubleshooting

### Common Issues

1. **"No module named 'music_agent'"** - Run from the correct directory
2. **"Spotify API not available"** - Check environment variables
3. **"AppleScript timeout"** - Ensure Spotify is running
4. **"Socket connection failed"** - Restart the daemon

### Debug Mode

Run the daemon in foreground for debugging:
```bash
python3 music_daemon.py
```

Check logs:
```bash
tail -f ~/.music_agent.log
```
