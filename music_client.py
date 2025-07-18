#!/usr/bin/env python3
"""
Music Client
Simple client for sending commands to the Music Daemon
"""

import sys
import json
from pathlib import Path
from music_daemon import MusicClient

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: music_client.py <command>")
        print("\nExamples:")
        print("  music_client.py 'play high hopes pink floyd'")
        print("  music_client.py 'what\\'s playing'")
        print("  music_client.py 'play me some enya'")
        print("  music_client.py 'play some mellow music'")
        print("  music_client.py 'status'")
        print("  music_client.py 'ping'")
        return
    
    command = ' '.join(sys.argv[1:])
    
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
