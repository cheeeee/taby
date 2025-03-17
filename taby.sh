#!/bin/bash

# TeamSpeak YouTube Audio Streamer
# Usage: ./taby.sh <youtube_url> [options]
# Author: [Your Name]
# Version: 1.1.0

set -o pipefail  # Properly propagate errors in pipelines

# Check dependencies
command -v yt-dlp &>/dev/null || { echo "ERROR: yt-dlp not installed. Run install script first"; exit 1; }
command -v pactl &>/dev/null || { echo "ERROR: PulseAudio not installed. Run install script first"; exit 1; }
command -v cvlc &>/dev/null || { echo "ERROR: VLC not installed. Run install script first"; exit 1; }

# Default settings
SINK_NAME="ts_music_sink"
SOURCE_NAME="TS_Music_Bot"
RTSP_PORT="8554"
HTTP_PORT="8080"
LOCAL_IP=$(hostname -I | awk '{print $1}')
RTSP_PATH="/audio"
AUDIO_QUALITY="bestaudio"
STREAM_BITRATE="128"
STREAM_CODEC="mp3"
YT_DLP_TIMEOUT=60  # Timeout in seconds for yt-dlp

# Parse arguments
[[ "$1" == "-h" || "$1" == "--help" || -z "$1" ]] && {
    echo "Usage: $0 <youtube_url> [--rtsp-port PORT] [--http-port PORT] [--no-streaming] [--sink-name NAME] [--source-name NAME] [--audio-quality QUALITY] [--stream-bitrate BITRATE] [--stream-codec CODEC]"
    echo "Options:"
    echo "  --audio-quality QUALITY    Audio quality for yt-dlp (e.g., 'bestaudio', 'bestaudio[ext=m4a]', 'bestaudio[height<=480]')"
    echo "  --stream-bitrate BITRATE   Bitrate for HTTP/RTSP streaming in kb/s (default: 128)"
    echo "  --stream-codec CODEC       Audio codec for streaming (default: mp3, options: mp3, opus, vorb, flac)"
    echo "  --sink-name NAME           PulseAudio sink name (max 15 chars, default: ts_music_sink)"
    echo "  --source-name NAME         PulseAudio source name (max 15 chars, default: TS_Music_Bot)"
    exit 1
}

YOUTUBE_URL="$1"
shift

# Validate YouTube URL format
if ! [[ "$YOUTUBE_URL" =~ ^https?://(www\.)?(youtube\.com|youtu\.be) ]]; then
    echo "ERROR: Invalid YouTube URL format. Must start with http:// or https:// and be from youtube.com or youtu.be"
    exit 1
fi

# Parse remaining arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rtsp-port) 
            if [[ "$2" =~ ^[0-9]+$ ]] && [ "$2" -ge 1024 ] && [ "$2" -le 65535 ]; then
                RTSP_PORT="$2"
            else
                echo "ERROR: Invalid RTSP port. Must be a number between 1024-65535"
                exit 1
            fi
            shift 2 
            ;;
        --http-port) 
            if [[ "$2" =~ ^[0-9]+$ ]] && [ "$2" -ge 1024 ] && [ "$2" -le 65535 ]; then
                HTTP_PORT="$2"
            else
                echo "ERROR: Invalid HTTP port. Must be a number between 1024-65535"
                exit 1
            fi
            shift 2 
            ;;
        --no-streaming) RTSP_PORT=""; HTTP_PORT=""; shift ;;
        --sink-name) 
            if [ ${#2} -le 15 ]; then
                SINK_NAME="$2"
            else
                echo "WARNING: Sink name too long, truncating to 15 characters"
                SINK_NAME="${2:0:15}"
            fi
            shift 2 
            ;;
        --source-name) 
            if [ ${#2} -le 15 ]; then
                SOURCE_NAME="$2"
            else
                echo "WARNING: Source name too long, truncating to 15 characters"
                SOURCE_NAME="${2:0:15}"
            fi
            shift 2 
            ;;
        --audio-quality) AUDIO_QUALITY="$2"; shift 2 ;;
        --stream-bitrate) 
            if [[ "$2" =~ ^[0-9]+$ ]]; then
                STREAM_BITRATE="$2"
            else
                echo "ERROR: Bitrate must be a number"
                exit 1
            fi
            shift 2 
            ;;
        --stream-codec) 
            case "$2" in
                mp3|opus|vorb|flac) STREAM_CODEC="$2"; shift 2 ;;
                *) echo "ERROR: Unsupported codec. Use mp3, opus, vorb, or flac"; exit 1 ;;
            esac
            ;;
        *) echo "ERROR: Unknown option: $1"; exit 1 ;;
    esac
done

echo "Setting up audio pipeline for: $YOUTUBE_URL"
echo "Audio quality: $AUDIO_QUALITY"
echo "Stream settings: codec=$STREAM_CODEC, bitrate=$STREAM_BITRATE kb/s"

# Create virtual audio devices
echo "Creating virtual audio devices..."
SINK_ID=$(pactl load-module module-null-sink sink_name=$SINK_NAME sink_properties=device.description=$SINK_NAME)
VIRTUAL_MIC_ID=$(pactl load-module module-virtual-source source_name=$SOURCE_NAME master=$SINK_NAME.monitor source_properties=device.description=$SOURCE_NAME)

if [[ -z "$SINK_ID" || -z "$VIRTUAL_MIC_ID" ]]; then
    echo "ERROR: Failed to create virtual devices"
    # Clean up any devices that might have been created
    [[ -n "$SINK_ID" ]] && pactl unload-module "$SINK_ID" 2>/dev/null
    exit 1
fi

# Initialize process IDs
VLC_PID=""
RTSP_VLC_PID=""
HTTP_VLC_PID=""

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    # Kill all VLC processes with proper error checking
    for pid_var in VLC_PID RTSP_VLC_PID HTTP_VLC_PID; do
        pid=${!pid_var}
        if [[ -n "$pid" ]]; then
            if ps -p "$pid" &>/dev/null; then
                echo "Terminating process $pid_var ($pid)"
                kill $pid 2>/dev/null
                # Wait for process to terminate
                for i in {1..5}; do
                    if ! ps -p "$pid" &>/dev/null; then
                        break
                    fi
                    sleep 0.5
                done
                # Force kill if still running
                if ps -p "$pid" &>/dev/null; then
                    echo "Force killing $pid_var ($pid)"
                    kill -9 $pid 2>/dev/null
                fi
            fi
        fi
    done
    
    # Unload PulseAudio modules
    echo "Unloading PulseAudio modules"
    [[ -n "$VIRTUAL_MIC_ID" ]] && pactl unload-module "$VIRTUAL_MIC_ID" 2>/dev/null
    [[ -n "$SINK_ID" ]] && pactl unload-module "$SINK_ID" 2>/dev/null
    
    echo "Cleanup complete"
    exit 0
}

trap cleanup EXIT INT TERM

# Get stream URL with timeout
echo "Retrieving stream URL (timeout: ${YT_DLP_TIMEOUT}s)..."
STREAM_URL=""
timeout $YT_DLP_TIMEOUT yt-dlp -f "$AUDIO_QUALITY" -g "$YOUTUBE_URL" > /tmp/yt_url.$$ 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to get stream URL (timeout or yt-dlp error)"
    cleanup
fi

STREAM_URL=$(cat /tmp/yt_url.$$ | head -1)
rm -f /tmp/yt_url.$$

if [[ -z "$STREAM_URL" ]]; then
    echo "ERROR: Failed to get stream URL"
    cleanup
fi

echo "Starting main audio player..."
PULSE_SINK=$SINK_NAME cvlc --no-video --volume=256 "$STREAM_URL" &>/dev/null &
VLC_PID=$!

# Wait for VLC to initialize
echo "Waiting for VLC to initialize..."
for i in {1..10}; do
    if ! ps -p "$VLC_PID" &>/dev/null; then
        echo "ERROR: VLC failed to start"
        cleanup
    fi
    sleep 0.5
done

# Set volume levels
echo "Setting volume levels..."
pactl set-sink-volume $SINK_NAME 100%
pactl set-source-volume $SOURCE_NAME 100%

# Start RTSP streaming if enabled
if [[ -n "$RTSP_PORT" ]]; then
    echo "Starting RTSP server on port $RTSP_PORT..."
    cvlc -vvv pulse://$SINK_NAME.monitor \
        --sout "#transcode{acodec=$STREAM_CODEC,ab=$STREAM_BITRATE}:rtp{sdp=rtsp://:$RTSP_PORT$RTSP_PATH}" \
        --sout-keep &>/dev/null &
    RTSP_VLC_PID=$!
    
    # Verify RTSP server started
    sleep 2
    if ! ps -p "$RTSP_VLC_PID" &>/dev/null; then
        echo "WARNING: RTSP server failed to start"
        RTSP_VLC_PID=""
    else
        echo "RTSP: rtsp://$LOCAL_IP:$RTSP_PORT$RTSP_PATH"
    fi
fi

# Start HTTP streaming if enabled
if [[ -n "$HTTP_PORT" ]]; then
    echo "Starting HTTP server on port $HTTP_PORT..."
    cvlc -vvv pulse://$SINK_NAME.monitor \
        --sout "#transcode{vcodec=none,acodec=$STREAM_CODEC,ab=$STREAM_BITRATE}:http{mux=ogg,dst=:$HTTP_PORT/stream.ogg}" \
        --sout-keep &>/dev/null &
    HTTP_VLC_PID=$!
    
    # Verify HTTP server started
    sleep 2
    if ! ps -p "$HTTP_VLC_PID" &>/dev/null; then
        echo "WARNING: HTTP server failed to start"
        HTTP_VLC_PID=""
    else
        echo "HTTP: http://$LOCAL_IP:$HTTP_PORT/stream.ogg"
    fi
fi

echo "✓ Audio pipeline ready! Select '$SOURCE_NAME' as your TeamSpeak mic"
echo "Press Ctrl+C to stop"

# Monitor all processes
while true; do
    # Check if main VLC process is still running
    if ! ps -p "$VLC_PID" &>/dev/null; then
        echo "Main VLC process terminated"
        break
    fi
    
    # Check streaming processes if they were started
    if [[ -n "$RTSP_VLC_PID" ]] && ! ps -p "$RTSP_VLC_PID" &>/dev/null; then
        echo "WARNING: RTSP streaming process terminated, restarting..."
        cvlc -vvv pulse://$SINK_NAME.monitor \
            --sout "#transcode{acodec=$STREAM_CODEC,ab=$STREAM_BITRATE}:rtp{sdp=rtsp://:$RTSP_PORT$RTSP_PATH}" \
            --sout-keep &>/dev/null &
        RTSP_VLC_PID=$!
    fi
    
    if [[ -n "$HTTP_VLC_PID" ]] && ! ps -p "$HTTP_VLC_PID" &>/dev/null; then
        echo "WARNING: HTTP streaming process terminated, restarting..."
        cvlc -vvv pulse://$SINK_NAME.monitor \
            --sout "#transcode{vcodec=none,acodec=$STREAM_CODEC,ab=$STREAM_BITRATE}:http{mux=ogg,dst=:$HTTP_PORT/stream.ogg}" \
            --sout-keep &>/dev/null &
        HTTP_VLC_PID=$!
    fi
    
    sleep 2
done

echo "Stream ended"
cleanup
