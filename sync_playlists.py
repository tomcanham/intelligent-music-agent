#!/Users/tom/scripts/slack/music_env/bin/python3
"""
Playlist Sync Script
Fetches all user playlists from Spotify and stores them locally
"""

try:
    from spotify_oauth import SpotifyAuth
    from music_agent import MusicDatabase
except ImportError as e:
    print(f"❌ Import error: {e}")
    exit(1)

import time
import sys

class PlaylistSyncer:
    """Handles syncing playlists from Spotify to local database"""
    
    def __init__(self):
        self.sp = None
        self.db = MusicDatabase()
        self.setup_spotify_connection()
    
    def setup_spotify_connection(self):
        """Set up Spotify API connection"""
        try:
            auth = SpotifyAuth()
            is_valid, message = auth.check_auth_status()
            if is_valid:
                self.sp = auth.get_spotify_client()
                print("✅ Spotify OAuth connection established")
            else:
                print(f"❌ {message}")
                exit(1)
        except Exception as e:
            print(f"❌ Error setting up Spotify connection: {e}")
            exit(1)
    
    def get_user_id(self):
        """Get the current user's Spotify ID"""
        try:
            user = self.sp.current_user()
            return user['id']
        except Exception as e:
            print(f"❌ Error getting user ID: {e}")
            return None
    
    def sync_all_playlists(self, include_tracks=True):
        """Sync all user playlists"""
        print("🔄 Starting playlist sync...")
        
        user_id = self.get_user_id()
        if not user_id:
            return False
        
        try:
            # Get all playlists (paginated)
            playlists = []
            results = self.sp.current_user_playlists(limit=50)
            
            while results:
                playlists.extend(results['items'])
                if results['next']:
                    results = self.sp.next(results)
                else:
                    break
            
            print(f"📦 Found {len(playlists)} playlists")
            
            synced_count = 0
            for i, playlist in enumerate(playlists, 1):
                print(f"🔄 [{i}/{len(playlists)}] {playlist['name']} ({playlist['tracks']['total']} tracks)")
                
                # Store playlist metadata
                success = self.db.store_playlist(playlist)
                if success:
                    synced_count += 1
                    
                    # Optionally sync tracks (can be slow for large playlists)
                    if include_tracks and playlist['tracks']['total'] > 0:
                        track_success = self.sync_playlist_tracks(playlist['id'])
                        if track_success:
                            print(f"  ✅ Synced {playlist['tracks']['total']} tracks")
                        else:
                            print(f"  ⚠️  Failed to sync tracks")
                else:
                    print(f"  ❌ Failed to store playlist")
                
                # Small delay to be nice to the API
                time.sleep(0.1)
            
            print(f"\n🎉 Sync completed: {synced_count}/{len(playlists)} playlists synced")
            return True
            
        except Exception as e:
            print(f"❌ Error during playlist sync: {e}")
            return False
    
    def sync_playlist_tracks(self, playlist_id):
        """Sync tracks for a specific playlist"""
        try:
            # Get all tracks from the playlist (paginated)
            tracks = []
            results = self.sp.playlist_tracks(playlist_id, limit=100)
            
            while results:
                tracks.extend(results['items'])
                if results['next']:
                    results = self.sp.next(results)
                else:
                    break
            
            # Store tracks in database
            return self.db.store_playlist_tracks(playlist_id, tracks)
            
        except Exception as e:
            print(f"❌ Error syncing playlist tracks: {e}")
            return False
    
    def sync_specific_playlist(self, playlist_name):
        """Sync a specific playlist by name"""
        print(f"🔍 Looking for playlist: '{playlist_name}'")
        
        try:
            # Search for the playlist
            results = self.sp.current_user_playlists(limit=50)
            found_playlist = None
            
            # Check all playlists for exact or fuzzy match
            while results:
                for playlist in results['items']:
                    if playlist['name'].lower() == playlist_name.lower():
                        found_playlist = playlist
                        break
                    elif playlist_name.lower() in playlist['name'].lower():
                        if found_playlist is None:  # First fuzzy match
                            found_playlist = playlist
                
                if found_playlist:
                    break
                
                if results['next']:
                    results = self.sp.next(results)
                else:
                    break
            
            if not found_playlist:
                print(f"❌ Playlist '{playlist_name}' not found")
                return False
            
            print(f"✅ Found: '{found_playlist['name']}' ({found_playlist['tracks']['total']} tracks)")
            
            # Store playlist
            success = self.db.store_playlist(found_playlist)
            if success:
                # Sync tracks
                track_success = self.sync_playlist_tracks(found_playlist['id'])
                if track_success:
                    print(f"🎉 Successfully synced '{found_playlist['name']}'")
                    return True
                else:
                    print(f"⚠️  Playlist stored but failed to sync tracks")
                    return False
            else:
                print(f"❌ Failed to store playlist")
                return False
                
        except Exception as e:
            print(f"❌ Error syncing specific playlist: {e}")
            return False
    
    def list_stored_playlists(self):
        """List all stored playlists"""
        playlists = self.db.get_playlists()
        
        if not playlists:
            print("📭 No playlists stored locally")
            return
        
        print(f"📚 {len(playlists)} stored playlists:")
        print("-" * 60)
        
        for i, playlist in enumerate(playlists, 1):
            owner_info = f" (by {playlist['owner_name']})" if playlist['owner_name'] else ""
            sync_info = f"(synced: {playlist['last_synced'][:10]})"
            
            print(f"{i:2d}. {playlist['name']}{owner_info}")
            print(f"    {playlist['track_count']} tracks {sync_info}")
            if playlist['description']:
                print(f"    {playlist['description']}")
            print()

def main():
    """Main CLI for playlist sync"""
    if len(sys.argv) < 2:
        print("🎵 Playlist Sync Tool")
        print()
        print("Usage:")
        print("  python3 sync_playlists.py all           - Sync all playlists (metadata only)")
        print("  python3 sync_playlists.py full          - Sync all playlists with tracks (slow)")
        print("  python3 sync_playlists.py sync 'name'   - Sync specific playlist")
        print("  python3 sync_playlists.py list          - List stored playlists")
        print()
        return
    
    syncer = PlaylistSyncer()
    command = sys.argv[1].lower()
    
    if command == 'all':
        print("🚀 Syncing all playlists (metadata only)...")
        syncer.sync_all_playlists(include_tracks=False)
        
    elif command == 'full':
        print("🚀 Full sync - this may take a while...")
        syncer.sync_all_playlists(include_tracks=True)
        
    elif command == 'sync':
        if len(sys.argv) < 3:
            print("❌ Please specify playlist name: python3 sync_playlists.py sync 'playlist name'")
            return
        
        playlist_name = sys.argv[2]
        syncer.sync_specific_playlist(playlist_name)
        
    elif command == 'list':
        syncer.list_stored_playlists()
        
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
