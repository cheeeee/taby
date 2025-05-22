#!/bin/bash

# Script to download and install TeamSpeak 3 Client for Linux (64-bit)

# --- Configuration ---
# Note: TeamSpeak download URLs are version specific. This might need updating.
TS_VERSION="3.6.2" # As of a recent check, update if a newer stable version is preferred.
TS_DOWNLOAD_URL="https://files.teamspeak-services.com/releases/client/${TS_VERSION}/TeamSpeak3-Client-linux_amd64-${TS_VERSION}.run"
TS_RUN_FILENAME="TeamSpeak3-Client-linux_amd64-${TS_VERSION}.run"
INSTALL_DIR_PARENT="/opt" # System-wide installation
INSTALL_DIR_NAME="TeamSpeak3-Client" # The folder name TS creates after extraction
FINAL_INSTALL_PATH="${INSTALL_DIR_PARENT}/${INSTALL_DIR_NAME}"
SYMLINK_PATH="/usr/local/bin/teamspeak3-client"

# --- Helper Functions ---
check_command() {
    command -v "$1" &>/dev/null
}

# --- Pre-flight Checks ---
echo "TeamSpeak 3 Client Installer for Linux"
echo "--------------------------------------"

# Check for root/sudo if installing system-wide
if [ "$EUID" -ne 0 ] && [ "$INSTALL_DIR_PARENT" == "/opt" ]; then
    echo "This script needs to install TeamSpeak to $FINAL_INSTALL_PATH and create symlinks."
    echo "Please run as root or with sudo."
    exit 1
fi

# Check for curl or wget
DOWNLOAD_CMD=""
if check_command "curl"; then
    DOWNLOAD_CMD="curl -L -o"
elif check_command "wget"; then
    DOWNLOAD_CMD="wget -O"
else
    echo "ERROR: Neither curl nor wget found. Please install one of them."
    exit 1
fi

# --- Main Installation ---
TEMP_DOWNLOAD_DIR=$(mktemp -d -t ts3_installer_XXXXXX)
if [ ! -d "$TEMP_DOWNLOAD_DIR" ]; then # mktemp should exit on error, but double check
    echo "ERROR: Failed to create temporary download directory."
    exit 1
fi
echo "Temporary download directory: $TEMP_DOWNLOAD_DIR"
cd "$TEMP_DOWNLOAD_DIR" || { echo "ERROR: Failed to cd into $TEMP_DOWNLOAD_DIR"; exit 1; }

# Download
echo "Downloading TeamSpeak Client ${TS_VERSION} from $TS_DOWNLOAD_URL..."
if ! $DOWNLOAD_CMD "$TS_RUN_FILENAME" "$TS_DOWNLOAD_URL"; then
    echo "ERROR: Failed to download TeamSpeak client."
    rm -rf "$TEMP_DOWNLOAD_DIR"
    exit 1
fi
echo "Download complete."

# Make executable
chmod +x "$TS_RUN_FILENAME"

# Instructions for the user
echo ""
echo "The TeamSpeak 3 Client installer will now run."
echo "You will need to read and accept the license agreement."
echo "The client files will be extracted into a directory named '$INSTALL_DIR_NAME' inside '$TEMP_DOWNLOAD_DIR'."
echo "Press Enter to continue with the TeamSpeak installer..."
read -r

# Run the installer - this part requires user interaction for license
clear # Clear screen for TS installer
"./$TS_RUN_FILENAME"

# Check if the extraction directory was created
EXTRACTED_DIR_PATH="${TEMP_DOWNLOAD_DIR}/${INSTALL_DIR_NAME}"
if [ -d "$EXTRACTED_DIR_PATH" ]; then
    echo "TeamSpeak client extracted to $EXTRACTED_DIR_PATH"
else
    echo "ERROR: TeamSpeak extraction directory '$EXTRACTED_DIR_PATH' not found after running installer."
    echo "The installer might have failed, or extracted to an unexpected location."
    echo "Please check the output above. Temporary files are in $TEMP_DOWNLOAD_DIR"
    exit 1
fi

# Move to final installation location
echo "Moving extracted files to $FINAL_INSTALL_PATH..."
if [ -d "$FINAL_INSTALL_PATH" ]; then
    echo "Warning: Existing installation found at $FINAL_INSTALL_PATH. Removing it first."
    if ! rm -rf "$FINAL_INSTALL_PATH"; then
        echo "ERROR: Failed to remove existing installation at $FINAL_INSTALL_PATH."
        rm -rf "$TEMP_DOWNLOAD_DIR"
        exit 1
    fi
fi
if ! mv "$EXTRACTED_DIR_PATH" "$INSTALL_DIR_PARENT/"; then # mv extracts to PARENT of target
    echo "ERROR: Failed to move TeamSpeak client to $FINAL_INSTALL_PATH."
    echo "You might need to run this script with sudo if you haven't already."
    rm -rf "$TEMP_DOWNLOAD_DIR"
    exit 1
fi
echo "TeamSpeak client installed to $FINAL_INSTALL_PATH."

# Create symlink
TS_RUNSCRIPT_PATH="${FINAL_INSTALL_PATH}/ts3client_runscript.sh"
if [ -f "$TS_RUNSCRIPT_PATH" ]; then
    echo "Creating symlink from $TS_RUNSCRIPT_PATH to $SYMLINK_PATH..."
    # Remove existing symlink if it exists
    if [ -L "$SYMLINK_PATH" ] || [ -f "$SYMLINK_PATH" ]; then
        rm -f "$SYMLINK_PATH"
    fi
    if ! ln -s "$TS_RUNSCRIPT_PATH" "$SYMLINK_PATH"; then
        echo "WARNING: Failed to create symlink at $SYMLINK_PATH."
        echo "You can try creating it manually: sudo ln -s $TS_RUNSCRIPT_PATH $SYMLINK_PATH"
    else
        echo "Symlink created. You can now try running 'teamspeak3-client' from your terminal."
    fi
else
    echo "WARNING: Could not find ts3client_runscript.sh at $TS_RUNSCRIPT_PATH. Cannot create symlink."
fi

# Create .desktop file (optional)
DESKTOP_FILE_CONTENT="[Desktop Entry]
Version=1.0
Name=TeamSpeak 3 Client
GenericName=Voice Chat Client
Comment=TeamSpeak 3 Client
Exec=${SYMLINK_PATH} %U
Terminal=false
Type=Application
Icon=${FINAL_INSTALL_PATH}/pluginsdk/docs/logo_32x32.png
Categories=Network;Chat;Voice;
StartupWMClass=teamspeak3
"
DESKTOP_FILE_PATH="/usr/share/applications/teamspeak3-client.desktop"

echo "Attempting to create .desktop file at $DESKTOP_FILE_PATH..."
if ! echo "$DESKTOP_FILE_CONTENT" > "$DESKTOP_FILE_PATH"; then
    echo "WARNING: Failed to create .desktop file. Missing permissions or path does not exist?"
    echo "You can create it manually with the following content:"
    echo "---"
    echo "$DESKTOP_FILE_CONTENT"
    echo "---"
else
    echo ".desktop file created successfully."
    # Update desktop database
    if check_command "update-desktop-database"; then
        echo "Updating desktop database..."
        update-desktop-database /usr/share/applications
    fi
fi

# Cleanup
echo "Cleaning up temporary files..."
rm -rf "$TEMP_DOWNLOAD_DIR"

echo ""
echo "✓ TeamSpeak 3 Client installation process finished."
echo "  Installed to: $FINAL_INSTALL_PATH"
if [ -L "$SYMLINK_PATH" ] && [ -x "$SYMLINK_PATH" ]; then
    echo "  Run command: teamspeak3-client"
fi
echo "  Please check for any warnings above."
echo "  You might need to adjust sound system settings within TeamSpeak after first launch."

exit 0
