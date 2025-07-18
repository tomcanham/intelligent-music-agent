#!/usr/bin/env python3
"""
Comprehensive Music Agent
Combines web search, AppleScript control, and all learned strategies for robust music handling
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import subprocess
import os
import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any

class MusicDatabase:
    """
    SQLite database for managing music agent local state
    Stores favorites, mood mappings, play history, and preferences
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to storing in user's home directory
            db_path = str(Path.home() / ".music_agent.db")
        
        self.db_path = db_path
        self.init_database()
        print(f"📁 Database initialized: {self.db_path}")
    
    def init_database(self):
        """Initialize the SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Table for favorite artists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS favorite_artists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        artist_name TEXT UNIQUE NOT NULL,
                        added_date TEXT NOT NULL,
                        play_count INTEGER DEFAULT 0
                    )
                ''')
                
                # Table for tags (replaces mood_mappings with more generic system)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tags (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        entity_type TEXT NOT NULL,  -- 'artist', 'track', 'album'
                        entity_name TEXT NOT NULL,  -- Artist name, track name, etc.
                        entity_id TEXT,             -- Spotify URI or other unique ID
                        tag_category TEXT NOT NULL, -- 'mood', 'genre', 'tempo', 'key', 'decade', etc.
                        tag_value TEXT NOT NULL,    -- 'mellow', 'rock', 'fast', 'G minor', '1980s', etc.
                        confidence REAL DEFAULT 1.0,
                        added_date TEXT NOT NULL,
                        added_by TEXT DEFAULT 'user',  -- 'user', 'system', 'api'
                        UNIQUE(entity_type, entity_name, tag_category, tag_value)
                    )
                ''')
                
                # Table for play history
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS play_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        track_name TEXT NOT NULL,
                        artist_name TEXT NOT NULL,
                        album_name TEXT,
                        spotify_uri TEXT,
                        played_at TEXT NOT NULL,
                        play_duration INTEGER DEFAULT 0
                    )
                ''')
                
                # Table for lyric patterns (extend the hardcoded ones)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS lyric_patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lyric_fragment TEXT NOT NULL,
                        track_name TEXT NOT NULL,
                        artist_name TEXT NOT NULL,
                        spotify_uri TEXT,
                        confidence REAL DEFAULT 1.0,
                        added_date TEXT NOT NULL
                    )
                ''')
                
                # Table for user preferences
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS preferences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key TEXT UNIQUE NOT NULL,
                        value TEXT NOT NULL,
                        updated_date TEXT NOT NULL
                    )
                ''')
                
                conn.commit()
                print("✅ Database tables initialized")
                
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
    
    def add_favorite_artist(self, artist_name: str) -> bool:
        """Add an artist to favorites"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO favorite_artists (artist_name, added_date)
                    VALUES (?, datetime('now'))
                ''', (artist_name,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"❌ Error adding favorite artist: {e}")
            return False
    
    def get_favorite_artists(self) -> List[Dict[str, Any]]:
        """Get all favorite artists"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT artist_name, added_date, play_count
                    FROM favorite_artists
                    ORDER BY play_count DESC, added_date DESC
                ''')
                return [{
                    'artist': row[0],
                    'added_date': row[1],
                    'play_count': row[2]
                } for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error getting favorite artists: {e}")
            return []
    
    def add_tag(self, entity_type: str, entity_name: str, tag_category: str, tag_value: str, 
                entity_id: str = None, confidence: float = 1.0, added_by: str = 'user') -> bool:
        """Add a tag to an entity (artist, track, album)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO tags 
                    (entity_type, entity_name, entity_id, tag_category, tag_value, confidence, added_date, added_by)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                ''', (entity_type, entity_name, entity_id, tag_category, tag_value, confidence, added_by))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error adding tag: {e}")
            return False
    
    def get_entities_by_tag(self, tag_category: str, tag_value: str, entity_type: str = None) -> List[Dict[str, Any]]:
        """Get entities that match a specific tag"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if entity_type:
                    cursor.execute('''
                        SELECT entity_name, entity_id, confidence
                        FROM tags
                        WHERE tag_category = ? AND tag_value LIKE ? AND entity_type = ?
                        ORDER BY confidence DESC
                    ''', (tag_category, f'%{tag_value}%', entity_type))
                else:
                    cursor.execute('''
                        SELECT entity_name, entity_id, entity_type, confidence
                        FROM tags
                        WHERE tag_category = ? AND tag_value LIKE ?
                        ORDER BY confidence DESC
                    ''', (tag_category, f'%{tag_value}%'))
                
                return [{
                    'entity_name': row[0],
                    'entity_id': row[1] if len(row) > 2 else None,
                    'entity_type': row[2] if len(row) > 3 else entity_type,
                    'confidence': row[-1]
                } for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error getting entities by tag: {e}")
            return []
    
    def get_tags_for_entity(self, entity_type: str, entity_name: str) -> List[Dict[str, Any]]:
        """Get all tags for a specific entity"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT tag_category, tag_value, confidence, added_date
                    FROM tags
                    WHERE entity_type = ? AND entity_name = ?
                    ORDER BY tag_category, confidence DESC
                ''', (entity_type, entity_name))
                return [{
                    'category': row[0],
                    'value': row[1],
                    'confidence': row[2],
                    'added_date': row[3]
                } for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error getting tags for entity: {e}")
            return []
    
    # Convenience methods for common tag operations
    def add_mood_tag(self, entity_type: str, entity_name: str, mood: str, confidence: float = 1.0) -> bool:
        """Add a mood tag - convenience method"""
        return self.add_tag(entity_type, entity_name, 'mood', mood, confidence=confidence)
    
    def add_genre_tag(self, entity_type: str, entity_name: str, genre: str, confidence: float = 1.0) -> bool:
        """Add a genre tag - convenience method"""
        return self.add_tag(entity_type, entity_name, 'genre', genre, confidence=confidence)
    
    def add_tempo_tag(self, entity_type: str, entity_name: str, tempo: str, confidence: float = 1.0) -> bool:
        """Add a tempo tag - convenience method"""
        return self.add_tag(entity_type, entity_name, 'tempo', tempo, confidence=confidence)
    
    def get_artists_by_mood(self, mood: str) -> List[Dict[str, Any]]:
        """Get artists that match a specific mood - backward compatibility"""
        entities = self.get_entities_by_tag('mood', mood, 'artist')
        return [{'artist': e['entity_name'], 'confidence': e['confidence']} for e in entities]
    
    def get_artists_by_genre(self, genre: str) -> List[Dict[str, Any]]:
        """Get artists that match a specific genre"""
        entities = self.get_entities_by_tag('genre', genre, 'artist')
        return [{'artist': e['entity_name'], 'confidence': e['confidence']} for e in entities]
    
    def log_play_history(self, track_name: str, artist_name: str, album_name: str = None, spotify_uri: str = None) -> bool:
        """Log a track play to history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO play_history (track_name, artist_name, album_name, spotify_uri, played_at)
                    VALUES (?, ?, ?, ?, datetime('now'))
                ''', (track_name, artist_name, album_name, spotify_uri))
                
                # Also increment play count for favorite artists
                cursor.execute('''
                    UPDATE favorite_artists
                    SET play_count = play_count + 1
                    WHERE artist_name = ?
                ''', (artist_name,))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error logging play history: {e}")
            return False
    
    def get_recent_plays(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent play history"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT track_name, artist_name, album_name, played_at
                    FROM play_history
                    ORDER BY played_at DESC
                    LIMIT ?
                ''', (limit,))
                return [{
                    'track': row[0],
                    'artist': row[1],
                    'album': row[2],
                    'played_at': row[3]
                } for row in cursor.fetchall()]
        except Exception as e:
            print(f"❌ Error getting recent plays: {e}")
            return []
    
    def set_preference(self, key: str, value: str) -> bool:
        """Set a user preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO preferences (key, value, updated_date)
                    VALUES (?, ?, datetime('now'))
                ''', (key, value))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error setting preference: {e}")
            return False
    
    def get_preference(self, key: str, default: str = None) -> Optional[str]:
        """Get a user preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM preferences WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else default
        except Exception as e:
            print(f"❌ Error getting preference: {e}")
            return default

class ComprehensiveMusicAgent:
    """
    A robust music agent that combines:
    - Web-based search for track identification
    - AppleScript for local player control
    - Fuzzy search capabilities
    - Error handling and timeouts
    - Progress indicators
    """
    
    def __init__(self, db_path: str = None):
        self.sp = None
        self.db = MusicDatabase(db_path)
        self.setup_spotify_connection()
        
    def setup_spotify_connection(self):
        """Set up Spotify API connection with proper error handling"""
        try:
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                print("⚠️  Spotify credentials not found. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
                return
            
            auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            print("✅ Spotify connection established")
            
        except Exception as e:
            print(f"❌ Error setting up Spotify connection: {e}")
    
    def run_applescript(self, script: str) -> str:
        """Execute AppleScript with timeout and error handling"""
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return "❌ AppleScript timeout"
        except subprocess.CalledProcessError as e:
            return f"❌ AppleScript error: {e.stderr.strip()}"
        except Exception as e:
            return f"❌ Unexpected error: {e}"
    
    def get_current_track(self) -> Dict[str, str]:
        """Get currently playing track info via AppleScript"""
        script = '''
        tell application "Spotify"
            if player state is playing then
                set trackName to name of current track
                set artistName to artist of current track
                return trackName & " | " & artistName
            else
                return "Not playing"
            end if
        end tell
        '''
        
        result = self.run_applescript(script)
        if "Not playing" in result or "❌" in result:
            return {"status": result}
        
        try:
            parts = result.split(" | ")
            return {
                "name": parts[0],
                "artist": parts[1],
                "status": "playing"
            }
        except:
            return {"status": "Error parsing track info"}
    
    def search_track_fuzzy(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Fuzzy search for tracks using multiple strategies
        Handles partial lyrics, typos, and missing punctuation
        """
        if not self.sp:
            return None
        
        print(f"🔍 Searching for: '{query}'")
        
        # Strategy 1: Direct search
        search_queries = [
            query,
            f'"{query}"',  # Exact phrase
            query.replace(" ", " AND "),  # Boolean search
        ]
        
        for search_query in search_queries:
            try:
                results = self.sp.search(q=search_query, type='track', limit=5)
                if results['tracks']['items']:
                    track = results['tracks']['items'][0]
                    print(f"✅ Found: {track['name']} by {track['artists'][0]['name']}")
                    return {
                        'name': track['name'],
                        'artist': track['artists'][0]['name'],
                        'album': track['album']['name'],
                        'uri': track['uri'],
                        'is_playable': track.get('is_playable', True)
                    }
            except Exception as e:
                print(f"❌ Search failed for '{search_query}': {e}")
                continue
        
        # Strategy 2: Artist-specific search if query contains artist hints
        potential_artists = ["Pink Floyd", "Oingo Boingo", "The Beatles", "Queen"]  # Extend as needed
        for artist in potential_artists:
            if artist.lower() in query.lower():
                try:
                    artist_query = f'artist:"{artist}" {query.replace(artist, "").strip()}'
                    results = self.sp.search(q=artist_query, type='track', limit=3)
                    if results['tracks']['items']:
                        track = results['tracks']['items'][0]
                        print(f"✅ Found via artist search: {track['name']} by {track['artists'][0]['name']}")
                        return {
                            'name': track['name'],
                            'artist': track['artists'][0]['name'],
                            'album': track['album']['name'],
                            'uri': track['uri'],
                            'is_playable': track.get('is_playable', True)
                        }
                except Exception as e:
                    continue
        
        print("❌ No tracks found")
        return None
    
    def search_by_lyrics(self, lyric_fragment: str) -> Optional[Dict[str, Any]]:
        """
        Search for songs by lyric fragments
        Uses web search and pattern matching
        """
        print(f"🔍 Searching by lyrics: '{lyric_fragment}'")
        
        # Known lyric patterns (extend this as you discover more)
        lyric_patterns = {
            "encumbered forever by desire and ambition": {
                "artist": "Pink Floyd",
                "song": "High Hopes",
                "uri": "spotify:track:5a4MgIUSf9K8wXLSm6xPEx"
            },
            "wish real hard when I close my eyes": {
                "artist": "Oingo Boingo", 
                "song": "Try To Believe",
                "uri": "spotify:track:7kVcbpFqcqBixHV73tNFns"
            }
        }
        
        # Check for exact or partial matches
        for pattern, song_info in lyric_patterns.items():
            if pattern.lower() in lyric_fragment.lower() or any(
                word in lyric_fragment.lower() for word in pattern.lower().split()
            ):
                print(f"✅ Found via lyric pattern: {song_info['song']} by {song_info['artist']}")
                return {
                    'name': song_info['song'],
                    'artist': song_info['artist'],
                    'uri': song_info['uri'],
                    'is_playable': True
                }
        
        # Fallback: Try to search by key words from the lyric
        key_words = [word for word in lyric_fragment.split() if len(word) > 3]
        if key_words:
            search_query = " ".join(key_words[:3])  # Use first 3 significant words
            return self.search_track_fuzzy(search_query)
        
        return None
    
    def play_artist_collection(self, artist_name: str) -> bool:
        """
        Play an artist's collection - tries playlists first, then top tracks
        Handles "play me some [artist]" requests
        """
        if not self.sp:
            return False
            
        print(f"🔍 Looking for {artist_name} collection...")
        
        # Strategy 1: Search for artist playlists (greatest hits, etc.)
        try:
            playlist_queries = [
                f'{artist_name} greatest hits',
                f'{artist_name} best of',
                f'{artist_name} collection',
                f'{artist_name}'
            ]
            
            for query in playlist_queries:
                playlist_results = self.sp.search(q=query, type='playlist', limit=3)
                
                if playlist_results['playlists']['items']:
                    playlist = playlist_results['playlists']['items'][0]
                    print(f"✅ Found playlist: {playlist['name']} ({playlist['tracks']['total']} tracks)")
                    
                    # Try to play the playlist
                    script = f'tell application "Spotify" to play track "{playlist["uri"]}"'
                    result = self.run_applescript(script)
                    
                    if "❌" not in result:
                        time.sleep(3)  # Give it time to start
                        current = self.get_current_track()
                        if current.get("status") == "playing":
                            print(f"🎵 Now playing from {playlist['name']}")
                            return True
                    break
        except Exception as e:
            print(f"❌ Playlist search failed: {e}")
        
        # Strategy 2: Fallback to artist's top track
        try:
            print(f"🔍 Falling back to {artist_name}'s top tracks...")
            artist_results = self.sp.search(q=artist_name, type='artist', limit=1)
            
            if artist_results['artists']['items']:
                artist = artist_results['artists']['items'][0]
                top_tracks = self.sp.artist_top_tracks(artist['id'])
                
                if top_tracks['tracks']:
                    track = top_tracks['tracks'][0]
                    print(f"🎵 Playing top track: {track['name']}")
                    return self.play_track(track['uri'])
        except Exception as e:
            print(f"❌ Top tracks fallback failed: {e}")
        
        return False
    
    def play_by_tags(self, tag_category: str, tag_value: str) -> bool:
        """
        Play music based on tags - handles "play some mellow music" requests
        Searches for both artists and tracks with matching tags
        """
        print(f"🔍 Looking for {tag_value} {tag_category} music...")
        
        # Get entities (artists and tracks) with matching tags
        entities = self.db.get_entities_by_tag(tag_category, tag_value)
        
        if not entities:
            print(f"❌ No {tag_value} {tag_category} music found in database")
            return False
        
        # Separate artists and tracks
        artists = [e for e in entities if e['entity_type'] == 'artist']
        tracks = [e for e in entities if e['entity_type'] == 'track']
        
        print(f"✅ Found {len(artists)} artists and {len(tracks)} tracks with {tag_value} {tag_category} tags")
        
        # Strategy 1: If we have specific tracks tagged, try to play one
        if tracks:
            # Sort by confidence and pick the highest confidence track
            track = max(tracks, key=lambda x: x['confidence'])
            print(f"🎵 Trying to play tagged track: {track['entity_name']}")
            
            if track['entity_id']:  # We have a Spotify URI
                success = self.play_track(track['entity_id'])
                if success:
                    # Log the play with tag info
                    self.db.log_play_history(track['entity_name'], 'Unknown', spotify_uri=track['entity_id'])
                    return True
            else:
                # No URI, try to search for the track
                found_track = self.search_track_fuzzy(track['entity_name'])
                if found_track:
                    success = self.play_track(found_track['uri'])
                    if success:
                        self.db.log_play_history(found_track['name'], found_track['artist'], found_track['album'], found_track['uri'])
                        return True
        
        # Strategy 2: Play from tagged artists
        if artists:
            # Sort by confidence and pick the highest confidence artist
            artist = max(artists, key=lambda x: x['confidence'])
            print(f"🎵 Trying to play from tagged artist: {artist['entity_name']}")
            
            success = self.play_artist_collection(artist['entity_name'])
            if success:
                return True
        
        print(f"❌ Could not play any {tag_value} {tag_category} music")
        return False
    
    def play_track(self, track_uri: str) -> bool:
        """Play a track using AppleScript with verification"""
        print(f"🎵 Playing track: {track_uri}")
        
        script = f'tell application "Spotify" to play track "{track_uri}"'
        result = self.run_applescript(script)
        
        if "❌" in result:
            print(f"❌ Failed to play track: {result}")
            return False
        
        # Verify playback started
        time.sleep(2)  # Give it a moment to start
        current = self.get_current_track()
        if current.get("status") == "playing":
            print(f"✅ Now playing: {current['name']} by {current['artist']}")
            return True
        else:
            print(f"❌ Playback verification failed: {current.get('status', 'Unknown')}")
            return False
    
    def get_track_lyrics(self, artist: str, song: str) -> Optional[str]:
        """
        Get lyrics for a song using web APIs with timeout
        """
        print(f"🔍 Getting lyrics for: {song} by {artist}")
        
        try:
            # Use curl with timeout to fetch lyrics
            cmd = f'timeout 10s curl -s "https://api.lyrics.ovh/v1/{artist}/{song}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    if 'lyrics' in data:
                        lines = data['lyrics'].split('\n')[:4]  # First 4 lines
                        print("✅ Lyrics found")
                        return '\n'.join(line.strip() for line in lines if line.strip())
                except:
                    pass
            
            print("❌ Lyrics API timeout/failed")
            return None
            
        except Exception as e:
            print(f"❌ Error getting lyrics: {e}")
            return None
    
    def _analyze_current_music(self, current_track: Dict[str, str]) -> str:
        """
        Analyze the currently playing music and provide genre/mood information
        """
        if not self.sp:
            return "❌ Spotify API not available for analysis"
        
        track_name = current_track['name']
        artist_name = current_track['artist']
        
        try:
            print(f"🔍 Analyzing: {track_name} by {artist_name}")
            
            # Search for the track to get detailed info
            search_results = self.sp.search(q=f'track:"{track_name}" artist:"{artist_name}"', type='track', limit=1)
            
            if not search_results['tracks']['items']:
                # Fallback to simpler search
                search_results = self.sp.search(q=f'{track_name} {artist_name}', type='track', limit=1)
            
            if search_results['tracks']['items']:
                track = search_results['tracks']['items'][0]
                track_id = track['id']
                
                # Get audio features (may fail with Client Credentials)
                audio_features = None
                try:
                    audio_features = self.sp.audio_features([track_id])[0]
                except Exception as e:
                    print(f"⚠️  Audio features not available: {e}")
                
                # Get artist info for genres
                artist_info = None
                try:
                    artist_info = self.sp.artist(track['artists'][0]['id'])
                except Exception as e:
                    print(f"⚠️  Artist info not available: {e}")
                
                # Build analysis
                analysis = f"🎵 **{track_name}** by **{artist_name}**\n\n"
                
                # Add basic track info
                analysis += f"🎤 **Album**: {track['album']['name']}\n"
                
                # Add release year if available
                release_date = track['album']['release_date']
                if release_date:
                    year = release_date.split('-')[0]
                    analysis += f"📅 **Released**: {year}\n"
                
                # Add genres if available and automatically tag them
                if artist_info and artist_info.get('genres'):
                    genres = artist_info['genres'][:3]  # Top 3 genres
                    analysis += f"🎸 **Genres**: {', '.join(genres)}\n"
                    
                    # Automatically add genre tags to the database
                    tags_added = []
                    for i, genre in enumerate(genres):
                        confidence = 1.0 - (i * 0.1)  # First genre gets 1.0, second gets 0.9, etc.
                        success = self.db.add_tag('artist', artist_name, 'genre', genre, 
                                                 confidence=confidence, added_by='api')
                        if success:
                            tags_added.append(genre)
                    
                    if tags_added:
                        analysis += f"🏷️ **Auto-tagged**: {', '.join(tags_added)}\n"
                else:
                    analysis += f"⚠️ **Genres**: Not available (API limitations)\n"
                
                # Add audio characteristics
                if audio_features:
                    # Energy (0-1)
                    energy = audio_features['energy']
                    if energy > 0.8:
                        energy_desc = "very energetic"
                    elif energy > 0.6:
                        energy_desc = "energetic"
                    elif energy > 0.4:
                        energy_desc = "moderate energy"
                    else:
                        energy_desc = "low energy"
                    
                    # Valence (0-1) - positivity
                    valence = audio_features['valence']
                    if valence > 0.7:
                        mood_desc = "happy/upbeat"
                    elif valence > 0.5:
                        mood_desc = "neutral/balanced"
                    elif valence > 0.3:
                        mood_desc = "somewhat melancholic"
                    else:
                        mood_desc = "sad/dark"
                    
                    # Danceability
                    danceability = audio_features['danceability']
                    if danceability > 0.7:
                        dance_desc = "very danceable"
                    elif danceability > 0.5:
                        dance_desc = "danceable"
                    else:
                        dance_desc = "not very danceable"
                    
                    # Tempo
                    tempo = audio_features['tempo']
                    if tempo > 140:
                        tempo_desc = "fast tempo"
                    elif tempo > 100:
                        tempo_desc = "medium tempo"
                    else:
                        tempo_desc = "slow tempo"
                    
                    analysis += f"⚡ **Energy**: {energy_desc}\n"
                    analysis += f"😊 **Mood**: {mood_desc}\n"
                    analysis += f"💃 **Danceability**: {dance_desc}\n"
                    analysis += f"🥁 **Tempo**: {tempo_desc} ({int(tempo)} BPM)\n"
                    
                    # Add release year if available
                    release_date = track['album']['release_date']
                    if release_date:
                        year = release_date.split('-')[0]
                        analysis += f"📅 **Released**: {year}\n"
                
                # Suggest some tags based on the analysis
                suggested_tags = []
                if audio_features:
                    if energy > 0.7:
                        suggested_tags.append("energetic")
                    if energy < 0.4:
                        suggested_tags.append("mellow")
                    if valence > 0.7:
                        suggested_tags.append("upbeat")
                    if valence < 0.4:
                        suggested_tags.append("melancholic")
                    if danceability > 0.7:
                        suggested_tags.append("danceable")
                
                if suggested_tags:
                    analysis += f"\n🏷️ **Suggested tags**: {', '.join(suggested_tags)}"
                
                return analysis
                
            else:
                return f"❌ Could not find detailed info for {track_name} by {artist_name}"
                
        except Exception as e:
            print(f"❌ Error analyzing music: {e}")
            return f"❌ Error analyzing {track_name} by {artist_name}: {str(e)}"
        
        return "❌ Could not analyze current music"
    
    def handle_command(self, command: str) -> str:
        """Handle natural language music commands"""
        command_lower = command.lower()
        
        # Handle "sync" command (analyze current track)
        if command_lower == "sync":
            current = self.get_current_track()
            if current.get("status") == "playing":
                analysis = self._analyze_current_music(current)
                return f"🔄 **Manual sync completed**\n\n{analysis}"
            else:
                return "❌ No track currently playing to sync"
        
        # Handle "what's playing"
        elif "what's playing" in command_lower or "current track" in command_lower:
            current = self.get_current_track()
            if current.get("status") == "playing":
                return f"🎵 Now playing: {current['name']} by {current['artist']}"
            else:
                return f"ℹ️ {current.get('status', 'Unknown status')}"
        
        # Handle "like" commands
        elif "like" in command_lower and ("artist" in command_lower or "this" in command_lower):
            if "this" in command_lower:
                # Like current playing artist
                current = self.get_current_track()
                if current.get("status") == "playing":
                    artist_name = current['artist']
                    success = self.db.add_favorite_artist(artist_name)
                    if success:
                        return f"❤️ Added {artist_name} to your favorites!"
                    else:
                        return f"ℹ️ {artist_name} is already in your favorites"
                else:
                    return "❌ No track currently playing to like"
            else:
                # Extract artist name from command
                # Look for patterns like "like john hiatt" or "I like artist john hiatt"
                import re
                patterns = [
                    r'like\s+(?:artist\s+)?([a-zA-Z\s]+?)(?:\s*$|\s+artist)',
                    r'i\s+like\s+([a-zA-Z\s]+?)(?:\s*$|\s+artist)',
                    r'like\s+([a-zA-Z\s]+?)\s*$'
                ]
                
                artist_name = None
                for pattern in patterns:
                    match = re.search(pattern, command_lower)
                    if match:
                        artist_name = match.group(1).strip()
                        break
                
                if artist_name:
                    success = self.db.add_favorite_artist(artist_name)
                    if success:
                        return f"❤️ Added {artist_name} to your favorites!"
                    else:
                        return f"ℹ️ {artist_name} is already in your favorites"
                else:
                    return "❌ Could not determine which artist to like. Try 'like john hiatt' or 'I like this artist'"
        
        # Handle "favorites" or "show favorites" commands
        elif "favorites" in command_lower or "favourite" in command_lower:
            favorites = self.db.get_favorite_artists()
            if favorites:
                result = "❤️ Your favorite artists:\n"
                for i, fav in enumerate(favorites[:10], 1):  # Show top 10
                    result += f"{i}. {fav['artist']} (played {fav['play_count']} times)\n"
                return result.strip()
            else:
                return "ℹ️ You haven't liked any artists yet. Try 'like john hiatt' or 'I like this artist'"
        
        # Handle "what kind of music is this" or "what genre is this"
        elif any(phrase in command_lower for phrase in ["what kind of music", "what genre", "what style", "describe this music"]):
            current = self.get_current_track()
            if current.get("status") == "playing":
                return self._analyze_current_music(current)
            else:
                return "❌ No track currently playing to analyze"
        
        # Handle lyric search
        elif "where they say" in command_lower or "lyrics" in command_lower:
            # Extract the lyric fragment
            if "where they say" in command_lower:
                lyric_fragment = command_lower.split("where they say")[1].strip().strip('"\'')
            else:
                lyric_fragment = command_lower.replace("lyrics", "").strip()
            
            track = self.search_by_lyrics(lyric_fragment)
            if track:
                return f"🎯 Found: {track['name']} by {track['artist']}"
            else:
                return f"❌ Could not find song with lyrics: '{lyric_fragment}'"
        
        # Handle tag-based requests like "play some mellow music" or "play something rock"
        elif any(phrase in command_lower for phrase in ["play some", "play something", "i want to hear", "put on some"]) and any(tag in command_lower for tag in ["music", "song", "track"]):
            # Extract the tag value (mood, genre, etc.)
            tag_value = None
            tag_category = None
            
            # Common mood/genre words to look for
            mood_words = ['mellow', 'chill', 'relaxing', 'calm', 'peaceful', 'energetic', 'upbeat', 'sad', 'happy', 'aggressive']
            genre_words = ['rock', 'jazz', 'classical', 'pop', 'electronic', 'country', 'blues', 'folk', 'metal', 'punk', 'americana', 'roots']
            tempo_words = ['fast', 'slow', 'medium', 'quick', 'upbeat', 'downtempo']
            
            # Check for mood words
            for word in mood_words:
                if word in command_lower:
                    tag_value = word
                    tag_category = 'mood'
                    break
            
            # Check for genre words if no mood found
            if not tag_value:
                for word in genre_words:
                    if word in command_lower:
                        tag_value = word
                        tag_category = 'genre'
                        break
            
            # Check for tempo words if no genre found
            if not tag_value:
                for word in tempo_words:
                    if word in command_lower:
                        tag_value = word
                        tag_category = 'tempo'
                        break
            
            if tag_value and tag_category:
                success = self.play_by_tags(tag_category, tag_value)
                if success:
                    return f"🎵 Now playing some {tag_value} music!"
                else:
                    return f"❌ Could not find any {tag_value} music. Try adding some tags first!"
            else:
                return f"❌ Could not identify the type of music you want. Try being more specific (e.g., 'play some rock music')"
        
        # Handle "play me some [artist]" requests
        elif "play me some" in command_lower or "play some" in command_lower:
            # Extract artist name
            if "play me some" in command_lower:
                artist_name = command_lower.replace("play me some", "").strip()
            else:
                artist_name = command_lower.replace("play some", "").strip()
            
            # Skip if this looks like a tag-based request
            if any(word in artist_name for word in ['music', 'song', 'track']):
                return f"❌ Could not understand the request. Try 'play some mellow music' or 'play me some Enya'"
            
            success = self.play_artist_collection(artist_name)
            if success:
                return f"🎵 Now playing some {artist_name}!"
            else:
                return f"❌ Could not find collection for: '{artist_name}'"
        
        # Handle regular play requests
        elif "play" in command_lower and not "playing" in command_lower:
            query = command_lower.replace("play", "").strip()
            track = self.search_track_fuzzy(query)
            
            if track:
                if track.get('is_playable', True):
                    success = self.play_track(track['uri'])
                    if success:
                        return f"🎵 Now playing: {track['name']} by {track['artist']}"
                    else:
                        return f"❌ Failed to play: {track['name']} by {track['artist']}"
                else:
                    return f"❌ Track not available for playback: {track['name']} by {track['artist']}"
            else:
                return f"❌ Could not find track: '{query}'"
        
        # Handle search requests
        elif "search" in command_lower or "find" in command_lower:
            query = command_lower.replace("search for", "").replace("find", "").strip()
            track = self.search_track_fuzzy(query)
            
            if track:
                return f"🎵 Found: {track['name']} by {track['artist']} from {track['album']}"
            else:
                return f"❌ Could not find: '{query}'"
        
        # Handle lyrics requests
        elif "lyrics" in command_lower:
            # Try to get lyrics for current track
            current = self.get_current_track()
            if current.get("status") == "playing":
                lyrics = self.get_track_lyrics(current['artist'], current['name'])
                if lyrics:
                    return f"🎵 First few lines of {current['name']} by {current['artist']}:\n{lyrics}"
                else:
                    return f"❌ Could not find lyrics for {current['name']} by {current['artist']}"
            else:
                return "❌ No track currently playing"
        
        return f"❓ I don't understand: '{command}'\n\nTry:\n• play high hopes pink floyd\n• play me some enya\n• what's that song where they say 'encumbered forever'\n• what's playing\n• search for bohemian rhapsody\n• lyrics"

def main():
    """Test the comprehensive music agent"""
    agent = ComprehensiveMusicAgent()
    
    print("🎵 Comprehensive Music Agent")
    print("✨ Features: fuzzy search, lyric search, AppleScript control")
    print("\nCommands:")
    print("• play [song/artist]")
    print("• search for [song]")
    print("• what's that song where they say '[lyrics]'")
    print("• what's playing")
    print("• lyrics")
    print("\nType 'quit' to exit\n")
    
    while True:
        try:
            command = input("🎵 > ").strip()
            if command.lower() in ['quit', 'exit', 'q']:
                break
            
            if command:
                response = agent.handle_command(command)
                print(response)
                print()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()
