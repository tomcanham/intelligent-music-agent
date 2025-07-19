#!/usr/bin/env python3
"""
Spotify OAuth Authentication Helper
Handles the OAuth flow for the music agent to get full API access
"""

import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
from pathlib import Path
from config import get_config

class SpotifyAuth:
    """Handle Spotify OAuth authentication"""
    
    def __init__(self, cache_path: str = None):
        if cache_path is None:
            cache_path = str(Path.home() / ".spotify_token_cache")
        
        self.cache_path = cache_path
        self._load_credentials()
        
    def _load_credentials(self):
        """Load credentials from file or environment variables"""
        # Try to load from .spotify_credentials file first
        config = get_config()
        creds_file = Path(config.credentials_file)
        
        if creds_file.exists():
            with open(creds_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        if key == 'SPOTIFY_CLIENT_ID':
                            self.client_id = value
                        elif key == 'SPOTIFY_CLIENT_SECRET':
                            self.client_secret = value
                        elif key == 'SPOTIFY_REDIRECT_URI':
                            self.redirect_uri = value
        else:
            # Fallback to environment variables
            self.client_id = os.getenv('SPOTIFY_CLIENT_ID')
            self.client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            self.redirect_uri = "https://127.0.0.1:8888/callback"
        
        # Scopes we need for full functionality
        self.scopes = [
            'user-read-currently-playing',     # Get current track info
            'user-read-playback-state',        # Get playback state
            'user-modify-playback-state',      # Control playback
            'user-read-recently-played',       # Get recently played tracks
            'user-library-read',               # Read user's library
            'playlist-read-private',           # Read private playlists
            'playlist-read-collaborative',     # Read collaborative playlists
            'user-top-read',                   # Get user's top tracks/artists
        ]
        
        self.scope_string = ' '.join(self.scopes)
    
    def get_auth_manager(self):
        """Get SpotifyOAuth manager"""
        if not self.client_id or not self.client_secret:
            raise ValueError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        
        return SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=self.scope_string,
            cache_path=self.cache_path,
            show_dialog=True  # Always show authorization dialog
        )
    
    def get_spotify_client(self):
        """Get authenticated Spotify client"""
        auth_manager = self.get_auth_manager()
        return spotipy.Spotify(auth_manager=auth_manager)
    
    def check_auth_status(self):
        """Check if we have valid authentication"""
        try:
            auth_manager = self.get_auth_manager()
            token_info = auth_manager.get_cached_token()
            
            if token_info:
                # Try to use the token
                sp = spotipy.Spotify(auth_manager=auth_manager)
                user = sp.current_user()
                return True, f"✅ Authenticated as: {user.get('display_name', user['id'])}"
            else:
                return False, "❌ No valid token found"
                
        except Exception as e:
            return False, f"❌ Authentication error: {e}"
    
    def start_auth_flow(self):
        """Start the OAuth flow"""
        print("🔐 Starting Spotify OAuth flow...")
        print("📝 Required scopes:", self.scope_string)
        print("🌐 Redirect URI:", self.redirect_uri)
        print("")
        
        try:
            auth_manager = self.get_auth_manager()
            sp = spotipy.Spotify(auth_manager=auth_manager)
            
            # This will trigger the OAuth flow
            user = sp.current_user()
            print(f"✅ Authentication successful!")
            print(f"👤 Logged in as: {user.get('display_name', user['id'])}")
            print(f"💾 Token cached at: {self.cache_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    def clear_cache(self):
        """Clear cached token"""
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
            print(f"🗑️  Cleared cached token: {self.cache_path}")
        else:
            print("ℹ️  No cached token to clear")

def main():
    """Main CLI for OAuth management"""
    import sys
    
    auth = SpotifyAuth()
    
    if len(sys.argv) < 2:
        print("🎵 Spotify OAuth Helper")
        print("")
        print("Usage:")
        print("  python3 spotify_oauth.py status    - Check authentication status")
        print("  python3 spotify_oauth.py auth      - Start OAuth flow")
        print("  python3 spotify_oauth.py clear     - Clear cached token")
        print("  python3 spotify_oauth.py test      - Test API access")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'status':
        is_valid, message = auth.check_auth_status()
        print(message)
        
    elif command == 'auth':
        print("🔐 Starting OAuth authentication...")
        print("")
        print("📋 Prerequisites:")
        print("1. Go to https://developer.spotify.com/dashboard")
        print("2. Create or edit your app")
        print("3. Add this redirect URI: https://127.0.0.1:8888/callback")
        print("4. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables")
        print("")
        input("Press Enter when ready to continue...")
        
        success = auth.start_auth_flow()
        if success:
            print("🎉 Ready to use full Spotify API!")
        
    elif command == 'clear':
        auth.clear_cache()
        
    elif command == 'test':
        try:
            sp = auth.get_spotify_client()
            
            # Test basic user info
            user = sp.current_user()
            print(f"✅ User: {user.get('display_name', user['id'])}")
            
            # Test current playback
            current = sp.current_playback()
            if current and current.get('is_playing'):
                track = current['item']
                print(f"🎵 Currently playing: {track['name']} by {track['artists'][0]['name']}")
                
                # Test audio features
                audio_features = sp.audio_features([track['id']])[0]
                if audio_features:
                    print(f"🎼 Audio features available: Energy={audio_features['energy']:.2f}, Valence={audio_features['valence']:.2f}")
                else:
                    print("⚠️  No audio features available")
            else:
                print("⏸️  No track currently playing")
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
