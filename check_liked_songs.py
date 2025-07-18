#!/Users/tom/scripts/slack/music_env/bin/python3
"""
Quick script to check user's liked songs
"""

try:
    from spotify_oauth import SpotifyAuth
except ImportError:
    print("❌ Could not import SpotifyAuth")
    exit(1)

def main():
    try:
        # Get authenticated Spotify client
        auth = SpotifyAuth()
        sp = auth.get_spotify_client()
        
        print("🎵 Checking your Liked Songs...")
        
        # Get liked songs (saved tracks)
        results = sp.current_user_saved_tracks(limit=10)
        
        if not results['items']:
            print("📭 No liked songs found")
            return
        
        print(f"❤️ Found {results['total']} liked songs total")
        print("\n🎵 First 10 liked songs:")
        print("-" * 50)
        
        for i, item in enumerate(results['items'], 1):
            track = item['track']
            artist = track['artists'][0]['name']
            name = track['name']
            album = track['album']['name']
            added_at = item['added_at'][:10]  # Just the date part
            
            print(f"{i:2d}. {name}")
            print(f"    by {artist}")
            print(f"    from '{album}' (liked: {added_at})")
            print()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
