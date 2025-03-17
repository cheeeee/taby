# Taby

Taby is a script that creates a virtual audio pipeline for streaming YouTube audio to TeamSpeak and optionally to RTSP/HTTP streams.

## Features

- Creates virtual audio devices for TeamSpeak integration
- Streams YouTube audio to TeamSpeak channels
- Optional RTSP streaming (default port 8554)
- Optional HTTP streaming with browser player (default port 8080)
- Uses yt-dlp to extract direct audio streams from YouTube URLs

## Requirements

- Linux with PulseAudio
- VLC media player
- yt-dlp (will be automatically installed if missing)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/cheeeee/taby.git
   cd taby
   ```

2. Make the script executable:
   ```
   chmod +x taby.py
   ```

## Usage

The script requires at least a YouTube URL as input and accepts several options:

```
./taby.py [YouTube URL] [options]
```

### Options

- `--rtsp-port PORT` - Enable RTSP streaming on specified port
- `--http-port PORT` - Enable HTTP streaming on specified port
- `--no-streaming` - Disable all streaming (TeamSpeak only mode)

### Examples

```
# TeamSpeak only (no streaming)
./taby.py https://www.youtube.com/watch?v=example --no-streaming

# TeamSpeak + RTSP streaming
./taby.py https://www.youtube.com/watch?v=example --rtsp-port 8554

# TeamSpeak + HTTP streaming
./taby.py https://www.youtube.com/watch?v=example --http-port 8080

# TeamSpeak + RTSP + HTTP streaming
./taby.py https://www.youtube.com/watch?v=example --rtsp-port 8554 --http-port 8080
```

## How It Works

1. The script creates virtual PulseAudio devices (sink and source)
2. It extracts the direct audio stream URL from YouTube using yt-dlp
3. VLC is used to play the audio through the virtual sink
4. If enabled, additional VLC instances are started for RTSP/HTTP streaming
5. For HTTP streaming, it generates an HTML player page at `/tmp/audio_player.html`

## TeamSpeak Setup

1. In TeamSpeak, go to Settings → Options → Capture
2. Select "taby_source" as your capture device
3. Configure other settings as needed

## Accessing Streams

- RTSP stream: `rtsp://your-ip-address:8554/audio`
- HTTP stream: `http://your-ip-address:8080/` (opens player in browser)

## Troubleshooting

If you encounter issues:

1. Make sure VLC is installed and accessible in your PATH
2. Check that PulseAudio is running and functioning correctly
3. Verify that the YouTube URL is valid and accessible

## License

This project is licensed under the MIT License - see the LICENSE file for details.
