# Taby - YouTube to TeamSpeak Audio Streaming

## Overview
Taby is a set of Bash scripts that create a virtual audio pipeline to stream YouTube audio to TeamSpeak and optionally to RTSP/HTTP streams. It allows you to play music or other audio content from YouTube directly through your TeamSpeak microphone input, making it easy to share audio with friends in your TeamSpeak server.

## Features
- Stream YouTube audio directly to TeamSpeak via virtual audio devices
- Optional RTSP streaming for media players
- Optional HTTP streaming with browser-based player
- Custom naming of audio devices for easy identification
- Multiple concurrent streams with the controller script

## Components
- **taby.sh**: The main script that handles a single YouTube stream
- **taby-controller.sh**: A management script that can handle multiple streams simultaneously

## Requirements
- Linux with PulseAudio
- VLC media player
- yt-dlp (YouTube downloader)
- curl
- jq

## Installation
1. Clone the repository or download the scripts
2. Make the scripts executable: `chmod +x taby.sh taby-controller.sh`
3. Ensure all dependencies are installed

## Usage

### Basic Usage
```bash
./taby.sh https://www.youtube.com/watch?v=example
```

### Advanced Options
```bash
./taby.sh https://www.youtube.com/watch?v=example --rtsp-port 8554 --http-port 8080 --sink-name custom_sink --source-name custom_source
```

### Using the Controller
```bash
# Start with a single URL
./taby-controller.sh -u https://www.youtube.com/watch?v=example

# Use a playlist file
./taby-controller.sh -p my_playlist.txt --max-concurrent 3

# Interactive commands
taby-controller> add https://www.youtube.com/watch?v=example
taby-controller> list
taby-controller> next
taby-controller> stop 0
taby-controller> stop-all
```

## Configuration Options

### taby.sh
- `--rtsp-port PORT`: Set RTSP streaming port (default: 8554)
- `--http-port PORT`: Set HTTP streaming port (default: 8080)
- `--no-streaming`: Disable all streaming (TeamSpeak only mode)
- `--sink-name NAME`: Custom name for the virtual sink
- `--source-name NAME`: Custom name for the virtual microphone

### taby-controller.sh
- `-u, --url URL`: Add a single YouTube URL to the queue
- `-p, --playlist FILE`: Specify a playlist file with YouTube URLs
- `-s, --script PATH`: Path to the taby.sh script
- `--rtsp-base-port PORT`: Base port for RTSP streaming
- `--http-base-port PORT`: Base port for HTTP streaming
- `--port-increment NUM`: Port increment for each instance
- `--max-concurrent NUM`: Maximum number of concurrent instances
- `--log-dir DIR`: Directory for log files

## TeamSpeak Setup
In TeamSpeak, select the custom virtual microphone source as your input device. If you don't see the custom name, you may need to use pavucontrol to redirect the audio input for TeamSpeak.

## Notes
- Device names are limited to 15 characters for compatibility
- HTTP streaming creates an HTML player at /tmp/audio_player.html
- The controller script provides a convenient way to manage multiple streams
