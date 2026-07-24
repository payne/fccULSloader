#!/bin/bash
echo "Offline Callsign Lookup Installer"

# Check for Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH."
    echo "Please install Python 3.7 or higher."
    exit 1
fi

# Install required packages quietly
echo "Installing dependencies..."
pip3 install -q -r src/requirements.txt pyinstaller
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies."
    exit 1
fi

# Clean build artifacts but preserve dist folder
# Only remove build directory and spec files, NOT the dist folder
rm -rf build/ *.spec &> /dev/null

# Create dist directory if it doesn't exist
mkdir -p dist/callsign-lookup-linux

# Get version from build_executable.py directly
# Use a more reliable way to capture the version
VERSION=$(python3 -c "import sys; sys.path.insert(0, 'src'); from callsign_lookup import __version__; print(__version__)")
echo "Detected version: ${VERSION}"

# Create a spec file with increased recursion limit to avoid recursion errors
echo "Creating PyInstaller spec file with increased recursion limit..."
cat > "callsign-lookup-${VERSION}.spec" << 'EOF'
# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 10)  # Increase recursion limit

block_cipher = None

a = Analysis(
    ['src/callsign_lookup.py'],
    pathex=[],
    binaries=[],
    datas=[('src/modules', 'modules'), ('LICENSE', '.'), ('README.md', '.'), ('FCC_DATABASE_DOC.md', '.')],
    hiddenimports=['modules.config', 'modules.database', 'modules.updater', 'modules.logger', 'modules.filesystemtools', 'modules.fcc_code_defs'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='callsign-lookup-linux-VERSION',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF

# Replace VERSION placeholder with actual version in the spec file
sed -i "s/callsign-lookup-linux-VERSION/callsign-lookup-linux-${VERSION}/g" "callsign-lookup-${VERSION}.spec"

echo "Building executable..."
# Run PyInstaller directly with the spec file
pyinstaller --clean --noconfirm --distpath=dist/callsign-lookup-linux "callsign-lookup-${VERSION}.spec"
if [ $? -ne 0 ]; then
    echo "Error: Failed to build executable."
    exit 1
fi

# Clean up silently but preserve dist folder
echo "Cleaning up build artifacts..."
rm -rf build/ *.spec &> /dev/null
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
rm -f callsign-lookup-*.pkg callsign-lookup-*.manifest warn-callsign-lookup-*.txt &> /dev/null

# Double-check that build folder is gone (sometimes it's recreated)
sleep 1
rm -rf build/ &> /dev/null

echo "Build completed successfully."
echo "Executable: dist/callsign-lookup-linux/callsign-lookup-linux-${VERSION}" 