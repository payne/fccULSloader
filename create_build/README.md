# Offline Callsign Lookup Build Scripts

This directory contains scripts for building standalone executables of the Offline Callsign Lookup application.

## Available Scripts

- **build_executable.py**: Main build script that supports building for Windows, Linux, and macOS
- **simple_build.py**: Simplified build script for quick builds
- **install.bat**: Windows installation script
- **install.sh**: Linux installation script
- **install_macos.sh**: macOS installation script
- **setup.py**: Setup script for packaging the application

## Building Executables

### Using the Installation Scripts

The easiest way to build the executable is to use the installation scripts:

#### Windows

Open Command Prompt or PowerShell and run:

```
cd <project_root>
create_build\install.bat
```

Alternatively, you can double-click the `install.bat` file in Windows Explorer.

#### Linux

Open a terminal and run:

```
cd <project_root>
chmod +x ./create_build/install.sh  # Make the script executable (first time only)
./create_build/install.sh
```

#### Windows Subsystem for Linux (WSL)

If you're using WSL, navigate to the project directory and run:

```
cd <project_root>
bash ./create_build/install.sh
```

Note: When building on WSL, you may need to increase the recursion limit if you encounter recursion errors. The updated script now handles this automatically.

#### macOS

Open Terminal and run:

```
cd <project_root>
chmod +x ./create_build/install_macos.sh  # Make the script executable (first time only)
./create_build/install_macos.sh
```

### Troubleshooting Build Issues

#### Recursion Errors
If you encounter recursion errors during the build process, the updated scripts now automatically increase Python's recursion limit to handle complex dependency trees.

#### Missing Dependencies
Make sure all required packages are installed:

```
pip install -r requirements.txt pyinstaller
```

#### Permission Issues
If you encounter permission issues when running the scripts, make sure they are executable:

```
chmod +x ./create_build/install.sh
chmod +x ./create_build/install_macos.sh
```

### Using the Build Scripts Directly

You can also use the build scripts directly:

#### Building for a Specific Platform

```
cd <project_root>
python create_build/build_executable.py --platform <platform>
```

Where `<platform>` is one of: `windows`, `linux`, or `macos`.

#### Building for All Platforms

```
cd <project_root>
python create_build/build_executable.py --platform all
```

#### Quick Build

```
cd <project_root>
python create_build/simple_build.py
```

## Output

The executables will be created in the following directories:

- Windows: `dist/callsign-lookup-windows/callsign-lookup-<version>.exe`
- Linux: `dist/callsign-lookup-linux/callsign-lookup-<version>`
- macOS: `dist/callsign-lookup-macos/callsign-lookup-<version>`

Where `<version>` is the version number defined in `src/callsign_lookup.py`.

## Running the Built Executables

### Windows
Double-click the executable file or run from Command Prompt:
```
dist\callsign-lookup-windows\callsign-lookup-<version>.exe
```

### Linux
Run from terminal:
```
./dist/callsign-lookup-linux/callsign-lookup-<version>
```

### macOS
Run from terminal:
```
./dist/callsign-lookup-macos/callsign-lookup-<version>
``` 