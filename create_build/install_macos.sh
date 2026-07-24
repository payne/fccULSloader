#!/bin/bash
echo "Offline Callsign Lookup Installer for macOS"
echo "==========================="
echo

# Check for Python installation
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed or not in PATH."
    echo "Please install Python 3.7 or higher."
    exit 1
fi

echo "Installing required packages..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install required packages."
    exit 1
fi

echo "Building executable..."
python3 create_build/build_executable.py --platform macos
if [ $? -ne 0 ]; then
    echo "Failed to build executable."
    exit 1
fi

echo
echo "Installation completed successfully!"
echo "The executable is located in the dist/callsign-lookup-macos directory."
echo
echo "You can run the application by executing dist/callsign-lookup-macos/callsign-lookup"
echo 