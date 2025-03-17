#!/bin/bash

# Quick installer for TeamSpeak YouTube audio streaming dependencies
# For Debian-based Linux distributions

# Check for root privileges
[[ "$(id -u)" -ne 0 ]] && { echo "Run as root or with sudo"; exit 1; }

# Install packages
echo "Installing dependencies..."
apt-get update
apt-get install -y vlc pulseaudio pulseaudio-utils python3 python3-pip curl

# Install yt-dlp
echo "Installing yt-dlp..."
curl -L -o /usr/local/bin/yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp
chmod a+rx /usr/local/bin/yt-dlp

# Verify installations
for cmd in vlc pactl yt-dlp; do
    command -v $cmd &>/dev/null || { echo "ERROR: $cmd installation failed"; exit 1; }
done

echo "✓ All dependencies installed successfully!"
