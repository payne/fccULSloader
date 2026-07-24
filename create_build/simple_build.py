#!/usr/bin/env python3
"""
Simple build script for creating a standalone executable of Offline Callsign Lookup
"""

import os
import subprocess
import sys
import platform
import importlib.util

# Import version from callsign_lookup.py
def get_version():
    """Get version from callsign_lookup.py"""
    try:
        # Try to import from src directory first
        if os.path.exists(os.path.join("src", "callsign_lookup.py")):
            spec = importlib.util.spec_from_file_location("callsign_lookup", os.path.join("src", "callsign_lookup.py"))
            callsign_lookup = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(callsign_lookup)
            return callsign_lookup.__version__
        # Fall back to root directory
        elif os.path.exists("callsign_lookup.py"):
            spec = importlib.util.spec_from_file_location("callsign_lookup", "callsign_lookup.py")
            callsign_lookup = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(callsign_lookup)
            return callsign_lookup.__version__
        else:
            return "1.5.0"  # Default version if callsign_lookup.py not found
    except (ImportError, AttributeError):
        return "1.5.0"  # Default version if import fails

VERSION = get_version()
print(f"Building Offline Callsign Lookup version {VERSION}")

def build_executable():
    """Build the executable using PyInstaller with minimal options"""
    print("Building executable...")
    
    # Create dist directory if it doesn't exist
    if not os.path.exists("dist"):
        os.makedirs("dist")
    
    # Determine the path to callsign_lookup.py
    if os.path.exists(os.path.join("src", "callsign_lookup.py")):
        callsign_lookup_path = os.path.join("src", "callsign_lookup.py")
    elif os.path.exists("callsign_lookup.py"):
        callsign_lookup_path = "callsign_lookup.py"
    else:
        print("Error: callsign_lookup.py not found in src directory or root directory")
        return False
    
    print(f"Using source file: {callsign_lookup_path}")
    
    # Build command with minimal options - using --onefile for a single executable
    cmd = [
        "pyinstaller",
        f"--name=callsign-lookup-{VERSION}",  # Include version in executable name
        "--onefile",  # Single file executable
        "--clean",
        callsign_lookup_path
    ]
    
    try:
        subprocess.check_call(cmd)
        print("Build completed successfully!")
        print(f"Executable can be found in the 'dist' directory as 'callsign-lookup-{VERSION}.exe'")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error building executable: {e}")
        return False

if __name__ == "__main__":
    build_executable() 