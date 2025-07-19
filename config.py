#!/usr/bin/env python3
"""
Configuration module for the Intelligent Music Agent
Centralizes all file paths and settings for easy customization
"""

import os
from pathlib import Path
from typing import Optional


class MusicAgentConfig:
    """
    Configuration class that handles all paths and settings for the music agent.
    Supports environment variable overrides and provides sensible defaults.
    """
    
    def __init__(self):
        # Base directory for the music agent installation
        self.base_dir = Path(__file__).parent.absolute()
        
        # User's home directory
        self.home_dir = Path.home()
        
        # Data directory - can be overridden with environment variable
        data_dir_env = os.getenv('MUSIC_AGENT_DATA_DIR')
        if data_dir_env:
            self.data_dir = Path(data_dir_env).expanduser()
        else:
            # Default to a .music_agent directory in user's home
            self.data_dir = self.home_dir / '.music_agent'
        
        # Create data directory if it doesn't exist
        self.data_dir.mkdir(exist_ok=True)
    
    @property
    def database_path(self) -> str:
        """Path to the SQLite database file"""
        db_path = os.getenv('MUSIC_AGENT_DB_PATH')
        if db_path:
            return str(Path(db_path).expanduser())
        return str(self.data_dir / 'music_agent.db')
    
    @property
    def socket_path(self) -> str:
        """Path to the Unix socket for daemon communication"""
        socket_path = os.getenv('MUSIC_AGENT_SOCKET_PATH')
        if socket_path:
            return str(Path(socket_path).expanduser())
        return str(self.data_dir / 'music_agent.sock')
    
    @property
    def log_path(self) -> str:
        """Path to the log file"""
        log_path = os.getenv('MUSIC_AGENT_LOG_PATH')
        if log_path:
            return str(Path(log_path).expanduser())
        return str(self.data_dir / 'music_agent.log')
    
    @property
    def credentials_file(self) -> str:
        """Path to the Spotify credentials file"""
        creds_path = os.getenv('MUSIC_AGENT_CREDENTIALS')
        if creds_path:
            return str(Path(creds_path).expanduser())
        return str(self.base_dir / '.spotify_credentials')
    
    @property
    def virtual_env_path(self) -> Optional[str]:
        """Path to the virtual environment, if it exists"""
        venv_path = self.base_dir / 'music_env'
        if venv_path.exists():
            return str(venv_path)
        return None
    
    @property
    def python_executable(self) -> str:
        """Path to the Python executable to use"""
        # Check for virtual environment first
        if self.virtual_env_path:
            venv_python = Path(self.virtual_env_path) / 'bin' / 'python3'
            if venv_python.exists():
                return str(venv_python)
        
        # Check environment variable
        python_path = os.getenv('MUSIC_AGENT_PYTHON')
        if python_path:
            return python_path
        
        # Fall back to system python3
        return 'python3'


# Global configuration instance
config = MusicAgentConfig()


def get_config() -> MusicAgentConfig:
    """Get the global configuration instance"""
    return config
