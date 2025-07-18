#!/usr/bin/env python3
"""
Comprehensive Music Agent
Combines web search, AppleScript control, and all learned strategies for robust music handling
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import subprocess
try:
    from spotify_oauth import SpotifyAuth
except ImportError:
    SpotifyAuth = None
import os
import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from config import get_config

class MusicDatabase:
    """
    SQLite database for managing music agent local state
    Stores favorites, mood mappings, play history, and preferences
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Use configurable path
            db_path = get_config().database_path
        
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
                
                # Table for playlists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS playlists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        spotify_id TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT,
                        owner_id TEXT,
                        owner_name TEXT,
                        is_public BOOLEAN DEFAULT 0,
                        is_collaborative BOOLEAN DEFAULT 0,
                        track_count INTEGER DEFAULT 0,
                        spotify_uri TEXT,
                        last_synced TEXT NOT NULL,
                        added_date TEXT NOT NULL
                    )
                ''')
                
                # Table for playlist tracks
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS playlist_tracks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        playlist_id INTEGER NOT NULL,
                        spotify_track_id TEXT NOT NULL,
                        track_name TEXT NOT NULL,
                        artist_name TEXT NOT NULL,
                        album_name TEXT,
                        spotify_uri TEXT NOT NULL,
                        duration_ms INTEGER,
                        added_at TEXT NOT NULL,
                        track_position INTEGER NOT NULL,
                        FOREIGN KEY (playlist_id) REFERENCES playlists (id),
                        UNIQUE(playlist_id, spotify_track_id)
                    )
                ''')
                
                # Table for musical relationships
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS musical_relationships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_type TEXT NOT NULL,       -- 'track', 'album', 'artist'
                        source_name TEXT NOT NULL,       -- Name of source entity
                        source_artist TEXT,              -- Artist if source is track/album
                        source_id TEXT,                  -- Spotify URI or other ID
                        target_type TEXT NOT NULL,       -- 'track', 'album', 'artist'
                        target_name TEXT NOT NULL,       -- Name of target entity
                        target_artist TEXT,              -- Artist if target is track/album
                        target_id TEXT,                  -- Spotify URI or other ID
                        relationship_type TEXT NOT NULL, -- 'remix_of', 'cover_of', 'influenced_by', 'sampled_by', 'similar_to', etc.
                        confidence REAL DEFAULT 1.0,    -- How confident we are in this relationship
                        notes TEXT,                      -- Optional human notes
                        added_date TEXT NOT NULL,
                        added_by TEXT DEFAULT 'user',   -- 'user', 'system', 'api'
                        UNIQUE(source_type, source_name, source_artist, target_type, target_name, target_artist, relationship_type)
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
    
    # Playlist management methods
    def store_playlist(self, playlist_data: Dict[str, Any]) -> bool:
        """Store a playlist in the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or update playlist
                cursor.execute('''
                    INSERT OR REPLACE INTO playlists 
                    (spotify_id, name, description, owner_id, owner_name, is_public, 
                     is_collaborative, track_count, spotify_uri, last_synced, added_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 
                            COALESCE((SELECT added_date FROM playlists WHERE spotify_id = ?), datetime('now')))
                ''', (
                    playlist_data['id'],
                    playlist_data['name'],
                    playlist_data.get('description', ''),
                    playlist_data['owner']['id'],
                    playlist_data['owner']['display_name'] or playlist_data['owner']['id'],
                    playlist_data.get('public', False),
                    playlist_data.get('collaborative', False),
                    playlist_data['tracks']['total'],
                    playlist_data['uri'],
                    playlist_data['id']  # For the COALESCE check
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Error storing playlist: {e}")
            return False
    
    def store_playlist_tracks(self, playlist_id: str, tracks: List[Dict[str, Any]]) -> bool:
        """Store tracks for a playlist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get the database playlist ID
                cursor.execute('SELECT id FROM playlists WHERE spotify_id = ?', (playlist_id,))
                result = cursor.fetchone()
                if not result:
                    print(f"❌ Playlist {playlist_id} not found in database")
                    return False
                
                db_playlist_id = result[0]
                
                # Clear existing tracks for this playlist
                cursor.execute('DELETE FROM playlist_tracks WHERE playlist_id = ?', (db_playlist_id,))
                
                # Insert new tracks
                for position, item in enumerate(tracks):
                    track = item['track']
                    if track:  # Some tracks might be None (removed tracks)
                        cursor.execute('''
                            INSERT OR IGNORE INTO playlist_tracks 
                            (playlist_id, spotify_track_id, track_name, artist_name, album_name, 
                             spotify_uri, duration_ms, added_at, track_position)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            db_playlist_id,
                            track['id'],
                            track['name'],
                            track['artists'][0]['name'] if track['artists'] else 'Unknown',
                            track['album']['name'] if track.get('album') else 'Unknown',
                            track['uri'],
                            track.get('duration_ms', 0),
                            item['added_at'],
                            position
                        ))
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"❌ Error storing playlist tracks: {e}")
            return False
    
    def get_playlists(self, owner_only: bool = True) -> List[Dict[str, Any]]:
        """Get stored playlists"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if owner_only:
                    # This would need the current user's ID - for now, get all
                    query = '''
                        SELECT spotify_id, name, description, owner_name, track_count, 
                               spotify_uri, last_synced, is_public, is_collaborative
                        FROM playlists
                        ORDER BY name
                    '''
                    cursor.execute(query)
                else:
                    cursor.execute('''
                        SELECT spotify_id, name, description, owner_name, track_count, 
                               spotify_uri, last_synced, is_public, is_collaborative
                        FROM playlists
                        ORDER BY name
                    ''')
                
                return [{
                    'spotify_id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'owner_name': row[3],
                    'track_count': row[4],
                    'spotify_uri': row[5],
                    'last_synced': row[6],
                    'is_public': bool(row[7]),
                    'is_collaborative': bool(row[8])
                } for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"❌ Error getting playlists: {e}")
            return []
    
    def find_playlist_by_name(self, name: str, fuzzy: bool = True) -> Optional[Dict[str, Any]]:
        """Find a playlist by name (exact or fuzzy match)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Try exact match first
                cursor.execute('''
                    SELECT spotify_id, name, description, owner_name, track_count, 
                           spotify_uri, last_synced
                    FROM playlists
                    WHERE LOWER(name) = LOWER(?)
                    LIMIT 1
                ''', (name,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'spotify_id': result[0],
                        'name': result[1],
                        'description': result[2],
                        'owner_name': result[3],
                        'track_count': result[4],
                        'spotify_uri': result[5],
                        'last_synced': result[6]
                    }
                
                # Try fuzzy match if enabled
                if fuzzy:
                    cursor.execute('''
                        SELECT spotify_id, name, description, owner_name, track_count, 
                               spotify_uri, last_synced
                        FROM playlists
                        WHERE LOWER(name) LIKE LOWER(?)
                        ORDER BY LENGTH(name)
                        LIMIT 1
                    ''', (f'%{name}%',))
                    
                    result = cursor.fetchone()
                    if result:
                        return {
                            'spotify_id': result[0],
                            'name': result[1],
                            'description': result[2],
                            'owner_name': result[3],
                            'track_count': result[4],
                            'spotify_uri': result[5],
                            'last_synced': result[6]
                        }
                
                return None
                
        except Exception as e:
            print(f"❌ Error finding playlist: {e}")
            return None
    
    def get_playlist_tracks(self, playlist_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get tracks from a playlist by name"""
        try:
            playlist = self.find_playlist_by_name(playlist_name)
            if not playlist:
                return []
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT pt.track_name, pt.artist_name, pt.album_name, pt.spotify_uri, pt.duration_ms
                    FROM playlist_tracks pt
                    JOIN playlists p ON pt.playlist_id = p.id
                    WHERE p.spotify_id = ?
                    ORDER BY pt.track_position
                    LIMIT ?
                ''', (playlist['spotify_id'], limit))
                
                return [{
                    'name': row[0],
                    'artist': row[1],
                    'album': row[2],
                    'uri': row[3],
                    'duration_ms': row[4]
                } for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"❌ Error getting playlist tracks: {e}")
            return []
    
    # Musical relationships methods
    def add_relationship(self, source_type: str, source_name: str, source_artist: str,
                        target_type: str, target_name: str, target_artist: str, 
                        relationship_type: str, notes: str = None, confidence: float = 1.0,
                        source_id: str = None, target_id: str = None, added_by: str = 'user') -> bool:
        """Add a musical relationship between two entities"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO musical_relationships 
                    (source_type, source_name, source_artist, source_id,
                     target_type, target_name, target_artist, target_id,
                     relationship_type, confidence, notes, added_date, added_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
                ''', (source_type, source_name, source_artist, source_id,
                      target_type, target_name, target_artist, target_id,
                      relationship_type, confidence, notes, added_by))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Error adding relationship: {e}")
            return False
    
    def get_relationships_for_entity(self, entity_type: str, entity_name: str, entity_artist: str = None) -> List[Dict[str, Any]]:
        """Get all relationships for a specific entity (as source or target)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get relationships where this entity is the source
                cursor.execute('''
                    SELECT target_type, target_name, target_artist, relationship_type, 
                           confidence, notes, added_date, added_by, 'outgoing' as direction
                    FROM musical_relationships
                    WHERE source_type = ? AND source_name = ? AND 
                          (source_artist = ? OR source_artist IS NULL OR ? IS NULL)
                    
                    UNION ALL
                    
                    SELECT source_type, source_name, source_artist, relationship_type,
                           confidence, notes, added_date, added_by, 'incoming' as direction
                    FROM musical_relationships
                    WHERE target_type = ? AND target_name = ? AND 
                          (target_artist = ? OR target_artist IS NULL OR ? IS NULL)
                    
                    ORDER BY added_date DESC
                ''', (entity_type, entity_name, entity_artist, entity_artist,
                      entity_type, entity_name, entity_artist, entity_artist))
                
                return [{
                    'related_type': row[0],
                    'related_name': row[1], 
                    'related_artist': row[2],
                    'relationship_type': row[3],
                    'confidence': row[4],
                    'notes': row[5],
                    'added_date': row[6],
                    'added_by': row[7],
                    'direction': row[8]
                } for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"❌ Error getting relationships: {e}")
            return []
    
    def get_relationships_by_type(self, relationship_type: str) -> List[Dict[str, Any]]:
        """Get all relationships of a specific type"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT source_type, source_name, source_artist,
                           target_type, target_name, target_artist,
                           relationship_type, confidence, notes, added_date
                    FROM musical_relationships
                    WHERE relationship_type = ?
                    ORDER BY added_date DESC
                ''', (relationship_type,))
                
                return [{
                    'source_type': row[0],
                    'source_name': row[1],
                    'source_artist': row[2],
                    'target_type': row[3],
                    'target_name': row[4],
                    'target_artist': row[5],
                    'relationship_type': row[6],
                    'confidence': row[7],
                    'notes': row[8],
                    'added_date': row[9]
                } for row in cursor.fetchall()]
                
        except Exception as e:
            print(f"❌ Error getting relationships by type: {e}")
            return []
    
    # Convenience methods for common relationship types
    def add_remix_relationship(self, remix_name: str, remix_artist: str, original_name: str, original_artist: str, notes: str = None) -> bool:
        """Add a remix relationship"""
        return self.add_relationship('track', remix_name, remix_artist, 
                                   'track', original_name, original_artist, 
                                   'remix_of', notes)
    
    def add_cover_relationship(self, cover_name: str, cover_artist: str, original_name: str, original_artist: str, notes: str = None) -> bool:
        """Add a cover relationship"""
        return self.add_relationship('track', cover_name, cover_artist,
                                   'track', original_name, original_artist,
                                   'cover_of', notes)
    
    def add_influence_relationship(self, influenced_name: str, influenced_artist: str, influencer_name: str, influencer_artist: str, notes: str = None) -> bool:
        """Add an influence relationship"""
        return self.add_relationship('track', influenced_name, influenced_artist,
                                   'track', influencer_name, influencer_artist,
                                   'influenced_by', notes)

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
            # Try OAuth first (provides full API access)
            if SpotifyAuth:
                try:
                    auth = SpotifyAuth()
                    is_valid, message = auth.check_auth_status()
                    if is_valid:
                        self.sp = auth.get_spotify_client()
                        print("✅ Spotify OAuth connection established (full API access)")
                        return
                    else:
                        print(f"⚠️  OAuth not available: {message}")
                except Exception as e:
                    print(f"⚠️  OAuth failed: {e}")
            
            # Fallback to Client Credentials (limited access)
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                print("⚠️  Spotify credentials not found. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
                return
            
            auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            print("✅ Spotify Client Credentials connection established (limited API access)")
            
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
    
    def play_playlist_by_name(self, playlist_name: str) -> bool:
        """Play a playlist by name from local database"""
        print(f"🔍 Looking for playlist: '{playlist_name}'")
        
        # First, try to find the playlist in our database
        playlist = self.db.find_playlist_by_name(playlist_name)
        if playlist:
            print(f"✅ Found playlist: '{playlist['name']}' ({playlist['track_count']} tracks)")
            
            # Play the playlist using its Spotify URI
            script = f'tell application "Spotify" to play track "{playlist['spotify_uri']}"'
            result = self.run_applescript(script)
            
            if "❌" not in result:
                time.sleep(3)  # Give it time to start
                current = self.get_current_track()
                if current.get("status") == "playing":
                    print(f"🎵 Now playing from playlist: {playlist['name']}")
                    return True
        
        # Fallback to searching Spotify directly
        return self.play_artist_collection(playlist_name)
    
    def play_random_from_playlist(self, playlist_name: str) -> bool:
        """Play a random track from a playlist"""
        print(f"🎲 Looking for random track from playlist: '{playlist_name}'")
        
        tracks = self.db.get_playlist_tracks(playlist_name, limit=100)
        if not tracks:
            print(f"❌ No tracks found in playlist '{playlist_name}'")
            return False
        
        import random
        track = random.choice(tracks)
        
        print(f"🎲 Selected: {track['name']} by {track['artist']}")
        success = self.play_track(track['uri'])
        
        if success:
            # Log the play
            self.db.log_play_history(track['name'], track['artist'], track['album'], track['uri'])
            return True
        
        return False
    
    def shuffle_liked_songs(self) -> bool:
        """Shuffle play liked songs from Spotify"""
        if not self.sp:
            return False

        print("🔀 Shuffling liked songs...")

        try:
            # Get the user's liked songs
            results = self.sp.current_user_saved_tracks(limit=50)
            if not results['items']:
                print("❌ No liked songs found")
                return False

            import random
            track = random.choice(results['items'])['track']
            print(f"🔀 Selected: {track['name']} by {track['artists'][0]['name']}")
            
            success = self.play_track(track['uri'])

            if success:
                # Log the play
                self.db.log_play_history(track['name'], track['artists'][0]['name'], track['album']['name'], track['uri'])
                return True

        except Exception as e:
            print(f"❌ Error accessing liked songs: {e}")

        return False

    def shuffle_playlist_by_name(self, playlist_name: str) -> bool:
        """Shuffle play a playlist by name"""
        print(f"🔀 Looking for playlist to shuffle: '{playlist_name}'")
        
        # First, try to find the playlist in our database
        playlist = self.db.find_playlist_by_name(playlist_name)
        if playlist:
            print(f"✅ Found playlist: '{playlist['name']}' ({playlist['track_count']} tracks)")
            
            # Play the playlist using its Spotify URI
            script = f'tell application "Spotify" to play track "{playlist['spotify_uri']}"'
            result = self.run_applescript(script)
            
            if "❌" not in result:
                time.sleep(3)  # Give it time to start
                
                # Turn on shuffle mode
                shuffle_script = 'tell application "Spotify" to set shuffling to true'
                shuffle_result = self.run_applescript(shuffle_script)
                
                current = self.get_current_track()
                if current.get("status") == "playing":
                    print(f"🔀 Now shuffling playlist: {playlist['name']}")
                    return True
        
        return False

    def list_playlists(self) -> str:
        """List available playlists"""
        playlists = self.db.get_playlists()
        
        if not playlists:
            return "📭 No playlists stored locally. Run 'python3 sync_playlists.py all' to sync from Spotify."
        
        result = f"📚 {len(playlists)} available playlists:\n"
        result += "-" * 40 + "\n"
        
        for i, playlist in enumerate(playlists[:20], 1):  # Show first 20
            result += f"{i:2d}. {playlist['name']} ({playlist['track_count']} tracks)\n"
            if playlist['description']:
                result += f"    {playlist['description'][:50]}...\n"
        
        if len(playlists) > 20:
            result += f"\n... and {len(playlists) - 20} more playlists"
        
        return result
    
    def next_track(self) -> str:
        """Skip to the next track using AppleScript"""
        print("⏭️ Skipping to next track...")
        
        script = 'tell application "Spotify" to next track'
        result = self.run_applescript(script)
        
        if "❌" in result:
            return f"❌ Failed to skip to next track: {result}"
        
        # Give it a moment to change tracks, then get the new track info
        time.sleep(2)
        current = self.get_current_track()
        if current.get("status") == "playing":
            return f"⏭️ Skipped to: {current['name']} by {current['artist']}"
        else:
            return f"⏭️ Skipped to next track (status: {current.get('status', 'Unknown')})"
    
    def previous_track(self) -> str:
        """Skip to the previous track using AppleScript"""
        print("⏮️ Skipping to previous track...")
        
        script = 'tell application "Spotify" to previous track'
        result = self.run_applescript(script)
        
        if "❌" in result:
            return f"❌ Failed to skip to previous track: {result}"
        
        # Give it a moment to change tracks, then get the new track info
        time.sleep(2)
        current = self.get_current_track()
        if current.get("status") == "playing":
            return f"⏮️ Skipped to: {current['name']} by {current['artist']}"
        else:
            return f"⏮️ Skipped to previous track (status: {current.get('status', 'Unknown')})"
    
    def pause_playback(self) -> str:
        """Pause playback using AppleScript"""
        print("⏸️ Pausing playback...")
        
        script = 'tell application "Spotify" to pause'
        result = self.run_applescript(script)
        
        if "❌" in result:
            return f"❌ Failed to pause: {result}"
        
        return "⏸️ Playback paused"
    
    def resume_playback(self) -> str:
        """Resume playback using AppleScript"""
        print("▶️ Resuming playback...")
        
        script = 'tell application "Spotify" to play'
        result = self.run_applescript(script)
        
        if "❌" in result:
            return f"❌ Failed to resume: {result}"
        
        # Get current track info
        time.sleep(1)
        current = self.get_current_track()
        if current.get("status") == "playing":
            return f"▶️ Resumed: {current['name']} by {current['artist']}"
        else:
            return "▶️ Playback resumed"
    
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
        
        # Handle playback control commands
        elif "next track" in command_lower or "skip" in command_lower or "next" in command_lower:
            return self.next_track()
        
        elif "previous track" in command_lower or "back" in command_lower or "previous" in command_lower:
            return self.previous_track()
        
        elif "pause" in command_lower:
            return self.pause_playback()
        
        elif "resume" in command_lower or "unpause" in command_lower:
            return self.resume_playback()
        
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
        
        # Handle tagging commands
        elif "tag this" in command_lower or "add tag" in command_lower:
            current = self.get_current_track()
            if current.get("status") != "playing":
                return "❌ No track currently playing to tag"
            
            # Extract tag from command
            import re
            patterns = [
                r'tag this (?:as |with )?"([^"]+)"',  # "tag this as "high energy""
                r'tag this (?:as |with )?(.+)',        # "tag this as high energy"
                r'add tag "([^"]+)"',                   # "add tag "high energy""
                r'add tag (.+)'                        # "add tag high energy"
            ]
            
            tag_text = None
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    tag_text = match.group(1).strip()
                    break
            
            if not tag_text:
                return "❌ Could not extract tag. Try 'tag this as high energy' or 'add tag \"workout music\"'"
            
            # Determine tag category (mood, genre, energy, etc.)
            tag_category = 'mood'  # Default
            energy_words = ['energy', 'energetic', 'pump', 'intense', 'powerful', 'driving']
            genre_words = ['rock', 'jazz', 'electronic', 'pop', 'classical', 'hip hop', 'country', 'blues', 'metal', 'punk', 'folk']
            mood_words = ['happy', 'sad', 'mellow', 'chill', 'upbeat', 'relaxing', 'peaceful', 'aggressive', 'romantic', 'nostalgic']
            
            if any(word in tag_text.lower() for word in energy_words):
                tag_category = 'energy'
            elif any(word in tag_text.lower() for word in genre_words):
                tag_category = 'genre'
            elif any(word in tag_text.lower() for word in mood_words):
                tag_category = 'mood'
            
            # Add tag to current track
            success = self.db.add_tag('track', current['name'], tag_category, tag_text, added_by='user')
            if success:
                return f"🏷️ Tagged '{current['name']}' by {current['artist']} as: {tag_text}"
            else:
                return f"❌ Failed to add tag"
        
        # Handle "show tags" command
        elif "show tags" in command_lower or "what tags" in command_lower:
            current = self.get_current_track()
            if current.get("status") != "playing":
                return "❌ No track currently playing to show tags for"
            
            tags = self.db.get_tags_for_entity('track', current['name'])
            if tags:
                result = f"🏷️ Tags for '{current['name']}' by {current['artist']}:\n"
                for tag in tags:
                    result += f"  • {tag['category']}: {tag['value']} (added {tag['added_date'][:10]})\n"
                return result.strip()
            else:
                return f"🏷️ No tags found for '{current['name']}' by {current['artist']}"
        
        # Handle "find songs tagged" command
        elif "find songs tagged" in command_lower or "play songs tagged" in command_lower:
            import re
            patterns = [
                r'(?:find|play) songs tagged (?:as |with )?"([^"]+)"',
                r'(?:find|play) songs tagged (?:as |with )?(.+)'
            ]
            
            tag_text = None
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    tag_text = match.group(1).strip()
                    break
            
            if not tag_text:
                return "❌ Could not extract tag. Try 'find songs tagged high energy'"
            
            # Search for tracks with this tag
            tracks = self.db.get_entities_by_tag('mood', tag_text, 'track')
            if not tracks:
                tracks = self.db.get_entities_by_tag('energy', tag_text, 'track')
            if not tracks:
                tracks = self.db.get_entities_by_tag('genre', tag_text, 'track')
            
            if tracks:
                if "play" in command_lower:
                    # Play the first/highest confidence track
                    track = tracks[0]
                    # Try to find and play the track
                    found_track = self.search_track_fuzzy(track['entity_name'])
                    if found_track:
                        success = self.play_track(found_track['uri'])
                        if success:
                            return f"🎵 Playing '{tag_text}' tagged song: {found_track['name']} by {found_track['artist']}"
                        else:
                            return f"❌ Failed to play {found_track['name']}"
                    else:
                        return f"❌ Could not find track: {track['entity_name']}"
                else:
                    # Just list the tracks
                    result = f"🏷️ Songs tagged '{tag_text}':\n"
                    for i, track in enumerate(tracks[:10], 1):
                        result += f"{i}. {track['entity_name']} (confidence: {track['confidence']:.1f})\n"
                    return result.strip()
            else:
                return f"❌ No songs found with tag: '{tag_text}'"
        
        
        # Handle "shuffle" commands
        elif "shuffle" in command_lower and ("liked songs" in command_lower or "my liked" in command_lower):
            success = self.shuffle_liked_songs()
            if success:
                return "🔀 Now shuffling your liked songs!"
            else:
                return "❌ Could not access your liked songs. Make sure you're authenticated with Spotify."
        
        elif "shuffle" in command_lower and "playlist" in command_lower:
            # Extract playlist name
            import re
            patterns = [
                r'shuffle playlist (.+)',
                r'shuffle (.+?) playlist',
                r'shuffle (.+)'
            ]
            
            playlist_name = None
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    playlist_name = match.group(1).strip()
                    # Skip words that don't look like playlist names
                    if playlist_name not in ['playlist', 'the', 'my']:
                        break
            
            if playlist_name:
                success = self.shuffle_playlist_by_name(playlist_name)
                if success:
                    return f"🔀 Now shuffling playlist: {playlist_name}"
                else:
                    return f"❌ Could not find or shuffle playlist: '{playlist_name}'"
            else:
                return "❌ Please specify a playlist name. Try 'shuffle my favorites playlist'"
        
        # Handle playlist commands
        elif "list playlists" in command_lower or "show playlists" in command_lower:
            return self.list_playlists()
        
        elif "play playlist" in command_lower or "play the playlist" in command_lower:
            # Extract playlist name
            playlist_name = command_lower.replace("play playlist", "").replace("play the playlist", "").strip()
            if playlist_name:
                success = self.play_playlist_by_name(playlist_name)
                if success:
                    return f"🎵 Now playing playlist: {playlist_name}"
                else:
                    return f"❌ Could not find or play playlist: '{playlist_name}'"
            else:
                return "❌ Please specify a playlist name. Try 'play playlist my favorites'"
        
        elif "random from" in command_lower:
            # Extract playlist name from various "random from [name]" patterns
            import re
            patterns = [
                r'random from (.+?) playlist',
                r'random from playlist (.+)',
                r'play random from (.+?) playlist', 
                r'play random from playlist (.+)',
                r'random from (.+)',  # More flexible - just "random from [name]"
                r'play random from (.+)'
            ]
            
            playlist_name = None
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    playlist_name = match.group(1).strip()
                    # Skip if it looks like a tag-based request
                    if not any(word in playlist_name for word in ['music', 'song', 'track']):
                        break
            
            if playlist_name:
                success = self.play_random_from_playlist(playlist_name)
                if success:
                    return f"🎲 Playing random track from playlist: {playlist_name}"
                else:
                    return f"❌ Could not find tracks in playlist: '{playlist_name}'"
            else:
                return "❌ Please specify a playlist name. Try 'random from odesza' or 'random from my favorites playlist'"
        
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
        
        # Handle relationship commands
        elif "add relationship" in command_lower or "this is" in command_lower:
            current = self.get_current_track()
            if current.get("status") != "playing":
                return "❌ No track currently playing to add relationship for"
            
            # Parse relationship patterns
            import re
            patterns = [
                r'this is (?:a )?remix of ([^"]+) by ([^"]+)',
                r'this is (?:a )?cover of ([^"]+) by ([^"]+)',
                r'this (?:was )?influenced by ([^"]+) by ([^"]+)',
                r'add relationship this is remix of ([^"]+) by ([^"]+)',
                r'add relationship this is cover of ([^"]+) by ([^"]+)',
            ]
            
            relationship_type = None
            target_name = None
            target_artist = None
            
            for pattern in patterns:
                match = re.search(pattern, command_lower)
                if match:
                    target_name = match.group(1).strip()
                    target_artist = match.group(2).strip()
                    
                    if "remix" in pattern:
                        relationship_type = "remix_of"
                    elif "cover" in pattern:
                        relationship_type = "cover_of"
                    elif "influenced" in pattern:
                        relationship_type = "influenced_by"
                    break
            
            if not (relationship_type and target_name and target_artist):
                return "❌ Could not parse relationship. Try: 'this is remix of sweet home alabama by lynyrd skynyrd'"
            
            # Add the relationship
            success = self.db.add_relationship(
                source_type='track',
                source_name=current['name'],
                source_artist=current['artist'],
                target_type='track', 
                target_name=target_name,
                target_artist=target_artist,
                relationship_type=relationship_type,
                notes=f"Added via voice command: {command}"
            )
            
            if success:
                return f"🔗 Added relationship: '{current['name']}' by {current['artist']} is {relationship_type.replace('_', ' ')} '{target_name}' by {target_artist}"
            else:
                return "❌ Failed to add relationship"
        
        # Handle "show relationships" command  
        elif "show relationships" in command_lower or "what relationships" in command_lower:
            current = self.get_current_track()
            if current.get("status") != "playing":
                return "❌ No track currently playing to show relationships for"
            
            relationships = self.db.get_relationships_for_entity('track', current['name'], current['artist'])
            if relationships:
                result = f"🔗 Relationships for '{current['name']}' by {current['artist']}:\n"
                for rel in relationships:
                    direction = "➡️" if rel['direction'] == 'outgoing' else "⬅️"
                    result += f"  {direction} {rel['relationship_type'].replace('_', ' ')}: {rel['related_name']} by {rel['related_artist']}\n"
                return result.strip()
            else:
                return f"🔗 No relationships found for '{current['name']}' by {current['artist']}"
        
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
        
        return f"❓ I don't understand: '{command}'\n\nTry:\n• play high hopes pink floyd\n• play me some enya\n• next track / skip\n• previous track / back\n• pause / resume\n• what's playing\n• what's that song where they say 'encumbered forever'\n• search for bohemian rhapsody\n• lyrics"

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
