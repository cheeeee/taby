#!/bin/bash

# Script to build a standalone executable for Taby GUI using PyInstaller

SCRIPT_NAME="gui_qt.py"
EXECUTABLE_NAME="TabyGUI"
DIST_PATH="dist"
BUILD_PATH="build"
ICON_PATH="assets/icon.png" # Optional: Define a path for an icon

# --- Helper Functions ---
cleanup() {
    echo "Cleaning up build artifacts..."
    rm -rf "$BUILD_PATH"
    # Optionally remove .spec file if you want a completely clean build next time
    # rm -f "${EXECUTABLE_NAME}.spec" 
    echo "Cleanup complete."
}

# --- Pre-flight Checks ---
echo "Taby GUI Executable Builder"
echo "---------------------------"

# 1. Check for PyInstaller
if ! python3 -m pip show pyinstaller &>/dev/null; then
    echo "PyInstaller not found."
    read -p "Do you want to install PyInstaller now? (y/N): " choice
    if [[ "$choice" == "Y" || "$choice" == "y" ]]; then
        echo "Installing PyInstaller..."
        python3 -m pip install pyinstaller
        if ! python3 -m pip show pyinstaller &>/dev/null; then
            echo "ERROR: PyInstaller installation failed. Please install it manually and try again."
            exit 1
        fi
        echo "PyInstaller installed successfully."
    else
        echo "Please install PyInstaller (e.g., 'pip install pyinstaller') and try again."
        exit 1
    fi
else
    echo "PyInstaller found."
fi

# 2. Check for the main script
if [ ! -f "$SCRIPT_NAME" ]; then
    echo "ERROR: Main GUI script '$SCRIPT_NAME' not found in the current directory."
    exit 1
fi

# 3. Check for taby.sh (as it needs to be bundled)
TABY_SH_PATH="taby.sh"
if [ ! -f "$TABY_SH_PATH" ]; then
    echo "ERROR: Required script '$TABY_SH_PATH' not found in the current directory."
    echo "This script is essential for Taby to function and needs to be bundled."
    exit 1
fi
echo "'$TABY_SH_PATH' found for bundling."

# 4. Optional: Check for icon
ICON_OPTION=""
if [ -f "$ICON_PATH" ]; then
    echo "Icon found at '$ICON_PATH'."
    ICON_OPTION="--icon=$ICON_PATH"
else
    echo "Optional icon '$ICON_PATH' not found, building without a custom icon."
fi


# --- Build Process ---
echo "Starting PyInstaller build process..."

# Clean previous builds (optional, but good for a fresh build)
# cleanup # Uncomment if you want to clean before every build by default
# Or, offer as an option:
read -p "Clean previous build artifacts (if any)? (y/N): " clean_choice
if [[ "$clean_choice" == "Y" || "$clean_choice" == "y" ]]; then
    cleanup
fi


# PyInstaller command
# --noconfirm: Overwrite output directory without asking
# --add-data: Bundles taby.sh into the executable's root.
#             Syntax: <SRC_PATH_ON_DISK>:<DEST_PATH_IN_BUNDLE>
#             '.' for DEST_PATH_IN_BUNDLE means the root of the bundle.
PYINSTALLER_CMD="python3 -m PyInstaller --noconfirm \
    --name \"$EXECUTABLE_NAME\" \
    --onefile \
    --windowed \
    $ICON_OPTION \
    --add-data \"$TABY_SH_PATH:.\" \
    $SCRIPT_NAME"

echo "Running PyInstaller with command:"
echo "$PYINSTALLER_CMD"

if eval "$PYINSTALLER_CMD"; then
    echo "-----------------------------------------------------"
    echo "✓ PyInstaller build successful!"
    echo "  Executable created at: $DIST_PATH/$EXECUTABLE_NAME"
    echo "-----------------------------------------------------"
    
    # Optional: Offer to clean up build directory and .spec file
    read -p "Clean temporary build files ($BUILD_PATH and ${EXECUTABLE_NAME}.spec)? (y/N): " final_clean_choice
    if [[ "$final_clean_choice" == "Y" || "$final_clean_choice" == "y" ]]; then
        rm -rf "$BUILD_PATH"
        rm -f "${EXECUTABLE_NAME}.spec"
        echo "Temporary build files cleaned."
    fi
else
    echo "-----------------------------------------------------"
    echo "✗ PyInstaller build FAILED."
    echo "  Check the output above for errors."
    echo "  Build artifacts (if any) are in '$BUILD_PATH' and '$DIST_PATH'."
    echo "-----------------------------------------------------"
    exit 1
fi

exit 0
