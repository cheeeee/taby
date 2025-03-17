# taby - TeamSpeak Audio Bot YouTube

A bash script that creates a virtual audio pipeline to stream YouTube audio to TeamSpeak and optionally provides RTSP/HTTP streaming capabilities.

## Features

- Stream YouTube audio directly to TeamSpeak using a virtual microphone
- Optional RTSP streaming for media players
- Optional HTTP streaming for web browsers
- Automatic handling of YouTube URLs with yt-dlp
- Clean termination and resource cleanup

## Requirements

- Linux with PulseAudio
- VLC media player
- yt-dlp
- TeamSpeak client

## Installation

1. Make sure you have the required dependencies:
   ```
   sudo apt install vlc pulseaudio
   ```

2. Install yt-dlp:
   ```
   sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
   sudo chmod a+rx /usr/local/bin/yt-dlp
   ```

3. Clone this repository or download the script file

4. Make the script executable:
   ```
   chmod +x ts_youtube_bot.sh
   ```

## Usage

### Basic Usage

```
./ts_youtube_bot.sh  [options]
```

### Options

- `--rtsp-port PORT` - Enable RTSP streaming on specified port (default: 8554)
- `--http-port PORT` - Enable HTTP streaming on specified port (default: 8080)
- `--no-streaming` - Disable all streaming (TeamSpeak only mode)

### Examples

1. TeamSpeak only (no streaming):
   ```
   ./ts_youtube_bot.sh https://www.youtube.com/watch?v=example --no-streaming
   ```

2. With RTSP streaming:
   ```
   ./ts_youtube_bot.sh https://www.youtube.com/watch?v=example --rtsp-port 8554
   ```

3. With HTTP streaming for browsers:
   ```
   ./ts_youtube_bot.sh https://www.youtube.com/watch?v=example --http-port 8080
   ```

4. With both streaming options:
   ```
   ./ts_youtube_bot.sh https://www.youtube.com/watch?v=example --rtsp-port 8554 --http-port 8080
   ```

## TeamSpeak Setup

1. Start the script with your desired YouTube URL
2. In TeamSpeak, go to Settings → Options → Capture
3. Select "TS_Music_Bot" as your microphone input
4. Adjust the volume as needed

## Streaming

### RTSP Streaming

If RTSP streaming is enabled, you can connect to the stream using VLC or other media players:
```
rtsp://your-ip-address:8554/audio
```

### HTTP Streaming

If HTTP streaming is enabled:
1. Open a web browser
2. Navigate to `http://your-ip-address:8080/stream.ogg`
3. Alternatively, open the HTML player created at `/tmp/audio_player.html`

## Troubleshooting

### RTSP Streaming Issues

If you encounter errors with RTSP streaming related to "unsupported codec: mp3", the script automatically uses MPGA codec instead which is compatible with VLC's RTP implementation.

### YouTube Download Problems

If yt-dlp fails to download from YouTube:
1. Update yt-dlp: `yt-dlp -U`
2. Try a different format: `yt-dlp --list-formats `
3. Check if the video is region-restricted or private

### Audio Quality Issues

If audio quality is poor:
1. Increase network caching: Edit the script and increase the `--network-caching` value
2. Increase bitrate: Edit the script and increase the `ab=128` value in the transcode options

## License

This project is licensed under the MIT License - see the LICENSE file for details.
