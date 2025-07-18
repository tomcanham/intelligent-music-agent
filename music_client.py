#!/Users/tom/scripts/slack/music_env/bin/python3
"""
Music Client
Simple client for sending commands to the Music Daemon with auto-start functionality
"""

import sys
import json
import time
import subprocess
from pathlib import Path
from music_daemon import MusicClient, MusicDaemon

def start_daemon_if_needed():
    """Start the music daemon if it's not already running"""
    daemon = MusicDaemon()
    if not daemon.is_running():
        print("🎵 Starting music daemon...")
        # Start daemon in background
        subprocess.Popen([
            sys.executable, 
            str(Path(__file__).parent / "music_daemon.py"), 
            "--daemon"
        ])
        # Wait a moment for it to start
        time.sleep(2)
        
        # Verify it started
        if daemon.is_running():
            print("✅ Music daemon started successfully")
            return True
        else:
            print("❌ Failed to start music daemon")
            return False
    return True

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: music_client.py <command>")
        print("\nExamples:")
        print("  music_client.py 'play high hopes pink floyd'")
        print("  music_client.py 'what\\'s playing'")
        print("  music_client.py 'play me some enya'")
        print("  music_client.py 'play some mellow music'")
        print("  music_client.py 'shuffle liked songs'")
        print("  music_client.py 'status'")
        print("  music_client.py 'ping'")
        return
    
    command = ' '.join(sys.argv[1:])
    
    # Ensure daemon is running
    if not start_daemon_if_needed():
        sys.exit(1)
    
    # Create client
    client = MusicClient()
    
    # Determine command type
    if command in ['ping', 'status', 'shutdown']:
        response = client.send_command(command)
    else:
        # Assume it's a music command
        response = client.music_command(command)
    
    # Display response
    if response.get('status') == 'success':
        print(response.get('message', 'Success'))
    else:
        print(f"Error: {response.get('message', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()
