#!/bin/bash

# TeamSpeak YouTube Audio Streamer
# Usage: ./taby.sh <youtube_url> [options]

# Check dependencies
command -v yt-dlp &>/dev/null || { echo "yt-dlp not installed. Run install script first"; exit 1; }
command -v pactl &>/dev/null || { echo "PulseAudio not installed. Run install script first"; exit 1; }
command -v cvlc &>/dev/null || { echo "VLC not installed. Run install script first"; exit 1; }

# Default settings
SINK_NAME="${3:-ts_music_sink}"
SOURCE_NAME="${4:-TS_Music_Bot}"
RTSP_PORT="${5:-8554}"
HTTP_PORT="${6:-8080}"
LOCAL_IP=$(hostname -I | awk '{print $1}')
RTSP_PATH="/audio"

# Parse arguments
[[ "$1" == "-h" || "$1" == "--help" || -z "$1" ]] && {
    echo "Usage: $0 <youtube_url> [--rtsp-port PORT] [--http-port PORT] [--no-streaming] [--sink-name NAME] [--source-name NAME]"
    exit 1
}

YOUTUBE_URL="$1"
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rtsp-port) RTSP_PORT="$2"; shift 2 ;;
        --http-port) HTTP_PORT="$2"; shift 2 ;;
        --no-streaming) RTSP_PORT=""; HTTP_PORT=""; shift ;;
        --sink-name) SINK_NAME="${2:0:15}"; shift 2 ;;
        --source-name) SOURCE_NAME="${2:0:15}"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "Setting up audio pipeline for: $YOUTUBE_URL"

# Create virtual audio devices
echo "Creating virtual audio devices..."
SINK_ID=$(pactl load-module module-null-sink sink_name=$SINK_NAME sink_properties=device.description=$SINK_NAME)
VIRTUAL_MIC_ID=$(pactl load-module module-virtual-source source_name=$SOURCE_NAME master=$SINK_NAME.monitor source_properties=device.description=$SOURCE_NAME)
[[ -z "$SINK_ID" || -z "$VIRTUAL_MIC_ID" ]] && { echo "Failed to create virtual devices"; exit 1; }

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    for pid in "$VLC_PID" "$RTSP_VLC_PID" "$HTTP_VLC_PID"; do
        [[ -n "$pid" ]] && kill $pid 2>/dev/null
    done
    pactl unload-module "$VIRTUAL_MIC_ID" 2>/dev/null
    pactl unload-module "$SINK_ID" 2>/dev/null
    exit 0
}
trap cleanup EXIT INT TERM

# Get stream URL and start VLC
STREAM_URL=$(yt-dlp -f 'bestaudio' -g "$YOUTUBE_URL")
[[ -z "$STREAM_URL" ]] && { echo "Failed to get stream URL"; cleanup; }

PULSE_SINK=$SINK_NAME cvlc --no-video --volume=256 "$STREAM_URL" &>/dev/null &
VLC_PID=$!
sleep 2
ps -p "$VLC_PID" &>/dev/null || { echo "VLC failed to start"; cleanup; }

# Set volume levels
pactl set-sink-volume $SINK_NAME 100%
pactl set-source-volume $SOURCE_NAME 100%

# Start RTSP streaming if enabled
if [[ -n "$RTSP_PORT" ]]; then
    cvlc -vvv pulse://$SINK_NAME.monitor --sout "#transcode{acodec=mpga,ab=128}:rtp{sdp=rtsp://:$RTSP_PORT$RTSP_PATH}" --sout-keep &>/dev/null &
    RTSP_VLC_PID=$!
    echo "RTSP: rtsp://$LOCAL_IP:$RTSP_PORT$RTSP_PATH"
fi

# Start HTTP streaming if enabled
if [[ -n "$HTTP_PORT" ]]; then
    cvlc -vvv pulse://$SINK_NAME.monitor --sout "#transcode{vcodec=theo,vb=800,acodec=vorb,ab=128}:http{mux=ogg,dst=:$HTTP_PORT/stream.ogg}" --sout-keep &>/dev/null &
    HTTP_VLC_PID=$!
    echo "HTTP: http://$LOCAL_IP:$HTTP_PORT/stream.ogg"
fi

echo "✓ Audio pipeline ready! Select '$SOURCE_NAME' as your TeamSpeak mic"
echo "Press Ctrl+C to stop"

# Keep script running and monitor processes
while ps -p "$VLC_PID" &>/dev/null; do sleep 1; done
echo "Main VLC process terminated"
cleanup
