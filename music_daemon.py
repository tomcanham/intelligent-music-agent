#!/usr/bin/env python3
"""
Music Agent Daemon
Background service that handles music commands via Unix socket communication
"""

import socket
import os
import sys
import json
import threading
import time
import signal
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import sqlite3
from datetime import datetime

# Import the existing music agent functionality
from music_agent import ComprehensiveMusicAgent
from config import get_config

class MusicDaemon:
    """
    Background daemon that runs the music agent and handles Unix socket communication
    """
    
    def __init__(self, socket_path: str = None):
        self.config = get_config()
        
        if socket_path is None:
            socket_path = self.config.socket_path
        
        self.socket_path = socket_path
        self.running = False
        self.sock = None
        self.music_agent = None
        self.db_path = self.config.database_path
        
        # Auto-sync tracking
        self.auto_sync_enabled = True
        self.polling_interval = 30  # seconds
        self.last_known_track = None
        self.polling_thread = None
        
        # Set up logging
        log_path = self.config.log_path
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Handle shutdown signals
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info(f"Music Daemon initialized - Socket: {self.socket_path}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def _setup_socket(self) -> bool:
        """Set up the Unix socket for communication"""
        try:
            # Remove existing socket if it exists
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
            
            # Create socket
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.bind(self.socket_path)
            self.sock.listen(5)
            
            # Set permissions so user can access
            os.chmod(self.socket_path, 0o600)
            
            self.logger.info(f"Socket created at {self.socket_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set up socket: {e}")
            return False
    
    def _init_music_agent(self) -> bool:
        """Initialize the music agent"""
        try:
            self.music_agent = ComprehensiveMusicAgent(self.db_path)
            self.logger.info("Music agent initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize music agent: {e}")
            return False
    
    def _handle_client(self, client_socket: socket.socket, client_address: str):
        """Handle a client connection"""
        try:
            self.logger.info(f"Client connected: {client_address}")
            
            while True:
                # Receive command
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    # Parse JSON command
                    command_data = json.loads(data.decode('utf-8'))
                    command = command_data.get('command', '')
                    
                    self.logger.info(f"Received command: {command}")
                    
                    # Process command
                    if command == 'ping':
                        response = {'status': 'success', 'message': 'pong'}
                    elif command == 'status':
                        response = self._get_status()
                    elif command == 'shutdown':
                        response = {'status': 'success', 'message': 'shutting down'}
                        client_socket.send(json.dumps(response).encode('utf-8'))
                        client_socket.close()
                        self.stop()
                        break
                    elif command.startswith('music:'):
                        # Handle music commands
                        music_command = command[6:]  # Remove 'music:' prefix
                        
                        # Special handling for sync commands
                        if music_command == 'sync':
                            response = self._manual_sync()
                        else:
                            response = self._handle_music_command(music_command)
                    else:
                        response = {'status': 'error', 'message': f'Unknown command: {command}'}
                    
                    # Send response
                    client_socket.send(json.dumps(response).encode('utf-8'))
                    
                except json.JSONDecodeError:
                    error_response = {'status': 'error', 'message': 'Invalid JSON'}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                except Exception as e:
                    error_response = {'status': 'error', 'message': str(e)}
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                    self.logger.error(f"Error handling command: {e}")
        
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
        finally:
            client_socket.close()
            self.logger.info("Client disconnected")
    
    def _handle_music_command(self, command: str) -> Dict[str, Any]:
        """Handle music-specific commands"""
        try:
            if not self.music_agent:
                return {'status': 'error', 'message': 'Music agent not initialized'}
            
            # Use the existing music agent's handle_command method
            result = self.music_agent.handle_command(command)
            
            return {
                'status': 'success',
                'message': result,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error handling music command '{command}': {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _get_status(self) -> Dict[str, Any]:
        """Get daemon status"""
        try:
            # Get current track info if available
            current_track = None
            if self.music_agent:
                current_track = self.music_agent.get_current_track()
            
            return {
                'status': 'success',
                'daemon_running': self.running,
                'music_agent_ready': self.music_agent is not None,
                'current_track': current_track,
                'socket_path': self.socket_path,
                'db_path': self.db_path,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def start(self):
        """Start the daemon"""
        self.logger.info("Starting Music Daemon...")
        
        # Initialize music agent
        if not self._init_music_agent():
            self.logger.error("Failed to initialize music agent")
            return False
        
        # Set up socket
        if not self._setup_socket():
            self.logger.error("Failed to set up socket")
            return False
        
        self.running = True
        self.logger.info("Music Daemon started successfully")
        
        # Start auto-sync polling thread
        self._start_auto_sync_polling()
        
        # Main loop - accept connections
        try:
            while self.running:
                try:
                    client_socket, client_address = self.sock.accept()
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        self.logger.error(f"Error accepting connection: {e}")
                    break
                    
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the daemon"""
        self.logger.info("Stopping Music Daemon...")
        
        self.running = False
        
        # Close socket
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        
        # Remove socket file
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
                self.logger.info(f"Removed socket file: {self.socket_path}")
            except:
                pass
        
        self.logger.info("Music Daemon stopped")
    
    def _start_auto_sync_polling(self):
        """Start the background polling thread for auto-sync"""
        if not self.auto_sync_enabled:
            return
        
        self.polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.polling_thread.start()
        self.logger.info(f"Auto-sync polling started (interval: {self.polling_interval}s)")
    
    def _polling_loop(self):
        """Background polling loop to detect track changes"""
        while self.running and self.auto_sync_enabled:
            try:
                # Check current track
                if self.music_agent:
                    current = self.music_agent.get_current_track()
                    
                    # Check if track has changed
                    if self._has_track_changed(current):
                        self._handle_track_change(current)
                    
                    self.last_known_track = current
                
                # Sleep for the polling interval
                time.sleep(self.polling_interval)
                
            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                time.sleep(self.polling_interval)  # Continue polling even on error
    
    def _has_track_changed(self, current_track: Dict[str, str]) -> bool:
        """Check if the current track is different from the last known track"""
        if not current_track or current_track.get('status') != 'playing':
            return False
        
        if not self.last_known_track or self.last_known_track.get('status') != 'playing':
            return True  # Started playing something
        
        # Compare track name and artist
        current_key = f"{current_track.get('name', '')}-{current_track.get('artist', '')}"
        last_key = f"{self.last_known_track.get('name', '')}-{self.last_known_track.get('artist', '')}"
        
        return current_key != last_key
    
    def _handle_track_change(self, current_track: Dict[str, str]):
        """Handle when a track change is detected"""
        if not current_track or current_track.get('status') != 'playing':
            return
        
        track_name = current_track.get('name', 'Unknown')
        artist_name = current_track.get('artist', 'Unknown')
        
        self.logger.info(f"Track change detected: {track_name} by {artist_name}")
        
        try:
            # Auto-analyze the new track
            analysis_result = self.music_agent._analyze_current_music(current_track)
            
            # Log the auto-sync
            self.logger.info(f"Auto-synced tags for: {artist_name}")
            
        except Exception as e:
            self.logger.error(f"Error auto-syncing track {track_name} by {artist_name}: {e}")
    
    def _manual_sync(self) -> Dict[str, Any]:
        """Manually sync the current track (for 'sync' command)"""
        try:
            if not self.music_agent:
                return {'status': 'error', 'message': 'Music agent not initialized'}
            
            current = self.music_agent.get_current_track()
            if not current or current.get('status') != 'playing':
                return {'status': 'error', 'message': 'No track currently playing'}
            
            # Force analysis regardless of whether it's changed
            result = self.music_agent._analyze_current_music(current)
            
            return {
                'status': 'success',
                'message': f"Manual sync completed\n{result}",
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def is_running(self) -> bool:
        """Check if another instance is already running"""
        if not os.path.exists(self.socket_path):
            return False
        
        try:
            test_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_sock.connect(self.socket_path)
            test_sock.close()
            return True
        except:
            # Socket file exists but no daemon is listening
            os.unlink(self.socket_path)
            return False


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Music Agent Daemon')
    parser.add_argument('--socket', default=None, help='Socket path')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (detached)')
    parser.add_argument('--stop', action='store_true', help='Stop running daemon')
    parser.add_argument('--status', action='store_true', help='Get daemon status')
    
    args = parser.parse_args()
    
    daemon = MusicDaemon(args.socket)
    
    if args.stop:
        # Send shutdown command to running daemon
        if daemon.is_running():
            try:
                client = MusicClient(daemon.socket_path)
                response = client.send_command('shutdown')
                print(f"Daemon shutdown: {response}")
            except Exception as e:
                print(f"Error stopping daemon: {e}")
        else:
            print("Daemon is not running")
        return
    
    if args.status:
        # Get status from running daemon
        if daemon.is_running():
            try:
                client = MusicClient(daemon.socket_path)
                response = client.send_command('status')
                print(f"Daemon status: {json.dumps(response, indent=2)}")
            except Exception as e:
                print(f"Error getting status: {e}")
        else:
            print("Daemon is not running")
        return
    
    # Check if already running
    if daemon.is_running():
        print("Music daemon is already running")
        return
    
    if args.daemon:
        # Run as daemon (detached process)
        if os.fork() == 0:
            # Child process
            os.setsid()
            daemon.start()
        else:
            # Parent process
            print("Music daemon started in background")
    else:
        # Run in foreground
        daemon.start()


class MusicClient:
    """
    Client for communicating with the Music Daemon
    """
    
    def __init__(self, socket_path: str = None):
        if socket_path is None:
            socket_path = get_config().socket_path
        self.socket_path = socket_path
    
    def send_command(self, command: str) -> Dict[str, Any]:
        """Send a command to the daemon"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            # Send command
            command_data = {'command': command}
            sock.send(json.dumps(command_data).encode('utf-8'))
            
            # Receive response
            response_data = sock.recv(4096)
            response = json.loads(response_data.decode('utf-8'))
            
            sock.close()
            return response
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def music_command(self, command: str) -> Dict[str, Any]:
        """Send a music command (convenience method)"""
        return self.send_command(f'music:{command}')


if __name__ == "__main__":
    main()
