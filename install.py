#!/usr/bin/env python3
"""
Installation script for the Intelligent Music Agent
Checks dependencies and guides the user through setup
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.8+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required. You have {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def check_platform():
    """Check if running on macOS"""
    system = platform.system()
    if system != "Darwin":
        print(f"⚠️  This music agent is designed for macOS. Detected: {system}")
        print("   AppleScript integration will not work on other platforms")
        return False
    print(f"✅ macOS detected ({platform.mac_ver()[0]})")
    return True


def check_spotify_app():
    """Check if Spotify app is installed"""
    spotify_paths = [
        "/Applications/Spotify.app",
        "/System/Applications/Spotify.app"
    ]
    
    for path in spotify_paths:
        if os.path.exists(path):
            print("✅ Spotify app found")
            return True
    
    print("⚠️  Spotify app not found. Please install from https://spotify.com")
    return False


def install_dependencies():
    """Install Python dependencies"""
    print("\n📦 Installing Python dependencies...")
    
    requirements = ["spotipy>=2.22.0"]
    
    try:
        for req in requirements:
            print(f"Installing {req}...")
            subprocess.run([sys.executable, "-m", "pip", "install", req], 
                         check=True, capture_output=True)
        
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def create_credentials_file():
    """Create example credentials file"""
    creds_example = Path(".spotify_credentials.example")
    creds_file = Path(".spotify_credentials")
    
    if creds_file.exists():
        print("✅ Credentials file already exists")
        return True
    
    if creds_example.exists():
        try:
            import shutil
            shutil.copy(creds_example, creds_file)
            print("📝 Created .spotify_credentials file from example")
            print("   Please edit it with your Spotify API credentials")
            return True
        except Exception as e:
            print(f"⚠️  Could not copy credentials example: {e}")
    
    # Create basic credentials file
    try:
        with open(creds_file, 'w') as f:
            f.write("# Spotify API Credentials\n")
            f.write("# Get these from https://developer.spotify.com/dashboard\n")
            f.write("SPOTIFY_CLIENT_ID=your_client_id_here\n")
            f.write("SPOTIFY_CLIENT_SECRET=your_client_secret_here\n")
            f.write("SPOTIFY_REDIRECT_URI=https://127.0.0.1:8888/callback\n")
        
        print("📝 Created basic .spotify_credentials file")
        print("   Please edit it with your Spotify API credentials")
        return True
    except Exception as e:
        print(f"❌ Could not create credentials file: {e}")
        return False


def make_scripts_executable():
    """Make Python and shell scripts executable"""
    scripts = [
        "music",
        "music_agent.py", 
        "music_daemon.py",
        "music_client.py",
        "spotify_oauth.py",
        "sync_playlists.py",
        "check_liked_songs.py"
    ]
    
    for script in scripts:
        script_path = Path(script)
        if script_path.exists():
            try:
                script_path.chmod(0o755)
                print(f"✅ Made {script} executable")
            except Exception as e:
                print(f"⚠️  Could not make {script} executable: {e}")
        else:
            print(f"⚠️  Script {script} not found")


def show_configuration_options():
    """Show configuration options"""
    print("\n🔧 Configuration Options:")
    print("=" * 50)
    
    print("\nEnvironment Variables:")
    print("  MUSIC_AGENT_DATA_DIR    - Base directory for data files")
    print("  MUSIC_AGENT_DB_PATH     - SQLite database file path")  
    print("  MUSIC_AGENT_SOCKET_PATH - Unix socket path")
    print("  MUSIC_AGENT_LOG_PATH    - Log file path")
    print("  MUSIC_AGENT_PYTHON      - Python executable to use")
    
    print("\nDefault locations:")
    config_dir = Path.home() / ".music_agent"
    print(f"  Data directory: {config_dir}")
    print(f"  Database: {config_dir}/music_agent.db")
    print(f"  Socket: {config_dir}/music_agent.sock") 
    print(f"  Logs: {config_dir}/music_agent.log")
    
    print(f"\nCredentials: {Path.cwd()}/.spotify_credentials")


def show_next_steps():
    """Show next steps for the user"""
    print("\n🚀 Next Steps:")
    print("=" * 50)
    
    print("\n1. Configure Spotify API:")
    print("   • Go to https://developer.spotify.com/dashboard")
    print("   • Create an app and get Client ID and Secret")
    print("   • Edit .spotify_credentials with your credentials")
    
    print("\n2. Test the installation:")
    print("   ./music status")
    print("   ./music \"what's playing\"")
    
    print("\n3. Optional OAuth setup (for full features):")
    print("   python3 spotify_oauth.py auth")
    
    print("\n4. Sync playlists (optional):")
    print("   python3 sync_playlists.py all")
    
    print("\n📖 See README.md for complete documentation")


def main():
    """Main installation function"""
    print("🎵 Intelligent Music Agent - Installation")
    print("=" * 50)
    
    # Check system requirements
    print("\n🔍 Checking system requirements...")
    
    checks_passed = True
    
    if not check_python_version():
        checks_passed = False
    
    if not check_platform():
        checks_passed = False
        print("   The agent may still work for Spotify API features")
    
    if not check_spotify_app():
        checks_passed = False
    
    if not checks_passed:
        print("\n⚠️  Some requirements are missing. Installation may not work correctly.")
        response = input("Continue anyway? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Installation cancelled.")
            sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies. Please check your Python/pip setup.")
        sys.exit(1)
    
    # Setup files
    create_credentials_file()
    make_scripts_executable()
    
    # Show configuration and next steps
    show_configuration_options()
    show_next_steps()
    
    print("\n✅ Installation completed!")
    print("🎵 Ready to use the Intelligent Music Agent!")


if __name__ == "__main__":
    main()
