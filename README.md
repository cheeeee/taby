# Taby - TeamSpeak YouTube Audio Streamer

Taby is a versatile tool that allows you to stream YouTube audio to TeamSpeak and other applications through virtual audio devices. It creates a seamless audio pipeline that can be used for sharing music with friends in TeamSpeak or streaming audio content to other applications.

## Features

- Stream YouTube audio directly to TeamSpeak
- Create virtual audio devices for routing audio
- Support for RTSP and HTTP streaming
- Multiple concurrent streams with the controller
- Queue management for sequential playback
- Interactive command-line interface

## Prerequisites

Taby requires the following dependencies:
- VLC media player
- PulseAudio
- yt-dlp
- Python 3 (for the controller)
- curl

## Installation

You can quickly install all dependencies using the provided installation script:

```bash
sudo ./install.sh
```

This will install all required packages on Debian-based Linux distributions.

## Usage

### Basic Usage

To stream a YouTube video's audio:

```bash
./taby.sh 
```

This will create virtual audio devices and start streaming. Select the created virtual source (default: `TS_Music_Bot`) as your microphone in TeamSpeak.

### Advanced Options

```bash
./taby.sh  [--rtsp-port PORT] [--http-port PORT] [--no-streaming] [--sink-name NAME] [--source-name NAME]
```

- `--rtsp-port PORT`: Set custom RTSP streaming port (default: 8554)
- `--http-port PORT`: Set custom HTTP streaming port (default: 8080)
- `--no-streaming`: Disable RTSP and HTTP streaming
- `--sink-name NAME`: Custom name for the PulseAudio sink (max 15 chars)
- `--source-name NAME`: Custom name for the virtual microphone (max 15 chars)

## Taby Controller

The controller allows you to manage multiple Taby instances simultaneously, providing a queue system and interactive interface.

### Controller Usage

```bash
./taby-controller.py [options]
```

Options:
- `-p, --playlist FILE`: Load YouTube URLs from a playlist file
- `-u, --url URL`: Add YouTube URL to queue (can be used multiple times)
- `-s, --script PATH`: Path to taby.sh (default: ./taby.sh)
- `-l, --list`: List active instances
- `--rtsp-base-port PORT`: Base port for RTSP streaming (default: 8554)
- `--http-base-port PORT`: Base port for HTTP streaming (default: 8080)
- `--port-increment N`: Port increment for each instance (default: 10)
- `--max-concurrent N`: Maximum concurrent instances (default: 5)
- `--log-dir DIR`: Log directory (default: /tmp/taby-controller-logs)
- `--db-file FILE`: Database file (default: /tmp/taby-controller.db)

### Interactive Commands

Once the controller is running, you can use these commands:
- `list`: Show active Taby instances
- `stop ID`: Stop a specific instance
- `stop-all`: Stop all instances
- `start-next`: Start the next URL in queue
- `add URL`: Add a YouTube URL to the queue
- `clean`: Remove dead instances
- `queue`: Show the current URL queue
- `help`: Display available commands
- `exit` or `quit`: Exit the controller

## Examples

### Basic streaming
```bash
./taby.sh https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### Custom device names
```bash
./taby.sh https://www.youtube.com/watch?v=dQw4w9WgXcQ --sink-name music_sink --source-name Music_Bot
```

### Using the controller with a playlist
```bash
./taby-controller.py --playlist my_playlist.txt --max-concurrent 3
```

## How It Works

1. Taby creates a virtual audio sink and source using PulseAudio
2. It uses yt-dlp to extract the audio stream URL from YouTube
3. VLC plays the audio and routes it to the virtual sink
4. The virtual source captures this audio for use in TeamSpeak
5. Optional RTSP/HTTP streaming allows remote access to the audio

## Troubleshooting

- If audio is not playing, check that all dependencies are installed correctly
- Verify that PulseAudio is running with `pulseaudio --check`
- Make sure you've selected the correct virtual source in TeamSpeak
- Check logs in the controller's log directory for detailed error information

## License

This project is open-source software.
