# Taby - TeamSpeak YouTube Audio Streamer

Taby is a versatile tool that allows you to stream audio from YouTube videos directly to TeamSpeak. It creates virtual audio devices that can be selected as microphone inputs in TeamSpeak, enabling you to share music or other audio content with your TeamSpeak friends.

## Features

- Stream audio from YouTube videos to TeamSpeak
- Queue multiple YouTube streams
- Manage multiple concurrent streams
- Customize audio quality, codec, and bitrate
- RTSP and HTTP streaming support
- User-friendly GUI interface
- Command-line interface for advanced users
- Load playlists from text files

## Requirements

- Linux operating system
- PulseAudio sound system
- VLC media player
- yt-dlp (YouTube downloader)
- Python 3.6+
- TeamSpeak client

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/taby.git
   cd taby
   ```

2. Run the installer script to set up dependencies:
   ```
   sudo ./install.sh
   ```

## Usage

### GUI Mode

Launch the graphical interface:

```
./taby_gui.py
```

The GUI allows you to:
- Add YouTube URLs to the queue
- Start and stop streams
- Manage the queue
- Configure stream settings

### Command Line Mode

```
./taby_controller.py [options]
```

Options:
- `-u URL, --url URL`: Add YouTube URL to queue
- `-p FILE, --playlist FILE`: Load YouTube URLs from a playlist file
- `-s PATH, --script PATH`: Path to taby.sh (default: ./taby.sh)
- `-l, --list`: List active instances
- `--rtsp-base-port PORT`: Base RTSP port (default: 8554)
- `--http-base-port PORT`: Base HTTP port (default: 8080)
- `--port-increment N`: Port increment (default: 10)
- `--max-concurrent N`: Max instances (default: 5)
- `--audio-quality QUALITY`: Audio quality (default: bestaudio)
- `--stream-bitrate BITRATE`: Stream bitrate (default: 128)
- `--stream-codec CODEC`: Stream codec (default: mp3)

### Direct Script Usage

For advanced users who want to run a single stream directly:

```
./taby.sh  [options]
```

Options:
- `--rtsp-port PORT`: RTSP port
- `--http-port PORT`: HTTP port
- `--no-streaming`: Disable RTSP/HTTP streaming
- `--sink-name NAME`: PulseAudio sink name
- `--source-name NAME`: PulseAudio source name
- `--audio-quality QUALITY`: Audio quality for yt-dlp
- `--stream-bitrate BITRATE`: Bitrate for streaming
- `--stream-codec CODEC`: Audio codec for streaming

## How It Works

Taby creates virtual PulseAudio devices for each stream:
1. A null sink to receive audio from YouTube
2. A virtual source that can be selected as a microphone in TeamSpeak
3. Optional RTSP and HTTP servers for remote streaming

When you start a stream, the YouTube audio is routed through these virtual devices, making it available as a microphone input in TeamSpeak.

## Troubleshooting

- **No audio in TeamSpeak**: Make sure you've selected the correct virtual source as your microphone in TeamSpeak settings.
- **Stream fails to start**: Check the log files in `/tmp/taby-controller-logs/` for error messages.
- **High CPU usage**: Try lowering the audio quality or bitrate in the stream options.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- VLC for audio processing
- yt-dlp for YouTube downloading
- PulseAudio for virtual audio routing
