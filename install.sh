#!/bin/bash

# Installer for Taby - TeamSpeak YouTube Audio Streamer dependencies
# Supports Debian/Ubuntu, Fedora, and Arch Linux

# Check for root privileges
[[ "$(id -u)" -ne 0 ]] && { echo "This script must be run as root or with sudo."; exit 1; }

# --- Variables ---
DISTRO_ID=""
PKG_MANAGER_CMD=""
UPDATE_CMD=""
INSTALL_CMD="" # Main install command part
COMMON_PKGS="git curl python3 python3-pip" # Common across most, adjust as needed

VLC_PKG=""
YTDLP_METHOD="manual" # Default to manual install via curl
YTDLP_PKG="" # For distros where package manager is preferred
PULSE_PKG=""
PYTHON_TK_PKG=""
CURL_PKG="curl" # Usually 'curl'

# --- Distribution Detection ---
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO_ID=$ID
    # For distros like Linux Mint that are 'like' ubuntu
    if [ -n "$ID_LIKE" ]; then
        case "$ID_LIKE" in
            *debian*|*ubuntu*) DISTRO_ID="ubuntu";; # Treat Mint as Ubuntu for packages
            *fedora*) DISTRO_ID="fedora";;
            *arch*) DISTRO_ID="arch";;
        esac
    fi
elif [ -f /etc/lsb-release ]; then
    . /etc/lsb-release
    DISTRO_ID=$DISTRIB_ID
    if [[ "$DISTRO_ID" == "Ubuntu" || "$DISTRO_ID" == "Debian" || "$DISTRO_ID" == "LinuxMint" ]]; then
        DISTRO_ID="ubuntu"
    fi
elif type lsb_release >/dev/null 2>&1; then
    distro_lower=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
    if [[ "$distro_lower" == "ubuntu" || "$distro_lower" == "debian" || "$distro_lower" == "linuxmint" ]]; then
        DISTRO_ID="ubuntu"
    fi
fi

echo "Detected distribution: $DISTRO_ID (OS_RELEASE_ID: $ID, OS_RELEASE_ID_LIKE: $ID_LIKE)"

# --- Set Distro-Specific Variables ---
case "$DISTRO_ID" in
    ubuntu|debian)
        UPDATE_CMD="apt-get update"
        INSTALL_CMD="apt-get install -y"
        VLC_PKG="vlc" # vlc-nox could be an alternative for headless servers
        PULSE_PKG="pulseaudio-utils"
        PYTHON_TK_PKG="python3-tk"
        # yt-dlp will be installed manually via curl for latest version
        ;;
    fedora)
        UPDATE_CMD="dnf check-update || true" # Refresh metadata, don't fail if no updates
        INSTALL_CMD="dnf install -y"
        VLC_PKG="vlc" # Requires RPM Fusion often, or ensure it's in default repos
        YTDLP_METHOD="package"
        YTDLP_PKG="yt-dlp"
        PULSE_PKG="pulseaudio-utils"
        PYTHON_TK_PKG="python3-tkinter"
        ;;
    arch)
        UPDATE_CMD="pacman -Syu --noconfirm" # Updates entire system, typical for Arch
        INSTALL_CMD="pacman -S --noconfirm --needed" # --needed prevents reinstalling up-to-date packages
        VLC_PKG="vlc"
        YTDLP_METHOD="package"
        YTDLP_PKG="yt-dlp"
        PULSE_PKG="pulseaudio" # Provides pactl
        PYTHON_TK_PKG="tk"
        COMMON_PKGS="git curl python python-pip" # Arch uses 'python' for python3
        ;;
    *)
        echo "Unsupported distribution: '$DISTRO_ID' (or detection failed)."
        echo "Please install the following dependencies manually for your system:"
        echo "  - VLC (cvlc command, headless if possible e.g., vlc-nox)"
        echo "  - yt-dlp (latest version recommended)"
        echo "  - PulseAudio utilities (pactl command)"
        echo "  - Python 3 & Pip (python3, python3-pip)"
        echo "  - Tkinter for Python 3 (python3-tk or equivalent)"
        echo "  - git"
        echo "  - curl"
        exit 1
        ;;
esac

PKG_MANAGER_CMD="$INSTALL_CMD" # For clarity later

# --- Installation ---
echo "Updating package list..."
eval "$UPDATE_CMD"

echo "Installing common dependencies: $COMMON_PKGS $CURL_PKG..."
if ! eval "$PKG_MANAGER_CMD $COMMON_PKGS $CURL_PKG"; then
    echo "ERROR: Failed to install common dependencies. Please check your package manager configuration."
    exit 1
fi

echo "Installing distribution-specific core dependencies..."
CORE_DISTRO_PKGS="$VLC_PKG $PULSE_PKG $PYTHON_TK_PKG"
if [[ "$YTDLP_METHOD" == "package" && -n "$YTDLP_PKG" ]]; then
    CORE_DISTRO_PKGS="$CORE_DISTRO_PKGS $YTDLP_PKG"
fi

if ! eval "$PKG_MANAGER_CMD $CORE_DISTRO_PKGS"; then
    echo "ERROR: Failed to install core distribution-specific dependencies: $CORE_DISTRO_PKGS"
    # Consider listing which ones failed if possible, or guide to manual install
    exit 1
fi

# Install/Update yt-dlp manually if method is 'manual' (especially for Debian/Ubuntu)
if [ "$YTDLP_METHOD" == "manual" ]; then
    echo "Installing/Updating yt-dlp manually via curl..."
    if ! curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp; then
        echo "ERROR: Failed to download yt-dlp."
        exit 1
    fi
    if ! chmod a+rx /usr/local/bin/yt-dlp; then
        echo "ERROR: Failed to set execute permissions on yt-dlp."
        exit 1
    fi
fi

# --- Verification ---
echo "Verifying installations..."
COMMANDS_TO_VERIFY=("cvlc" "pactl" "yt-dlp" "python3" "pip3") # cvlc is part of vlc
MISSING_CMDS=()

for cmd in "${COMMANDS_TO_VERIFY[@]}"; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: Command '$cmd' not found after installation."
        MISSING_CMDS+=("$cmd")
    fi
done

if [ ${#MISSING_CMDS[@]} -ne 0 ]; then
    echo "Installation failed for the following commands: ${MISSING_CMDS[*]}"
    echo "Please try installing them manually or check your system configuration."
    exit 1
fi

echo "✓ All specified dependencies appear to be installed successfully!"
echo "Note: For Fedora, ensure RPM Fusion repository is enabled if 'vlc' package from default repos is insufficient."
echo "For Arch, 'pacman -Syu' updates the entire system; this is standard practice but be aware."
