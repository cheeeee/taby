#!/bin/bash

# Check if yt-dlp is installed
if ! command -v yt-dlp &> /dev/null; then
    echo "yt-dlp is not installed. Please install it first."
    echo "Visit: https://github.com/yt-dlp/yt-dlp#installation"
    exit 1
fi

# Default device names
DEFAULT_SINK_NAME="ts_music_sink"
DEFAULT_SOURCE_NAME="TS_Music_Bot"

# Variables to hold actual device names
SINK_NAME="$DEFAULT_SINK_NAME"
SOURCE_NAME="$DEFAULT_SOURCE_NAME"

# Display usage information
show_usage() {
    echo "Usage: $0 <youtube_url> [options]"
    echo "Options:"
    echo "  -h, --help           Show this help message"
    echo "  --rtsp-port PORT     Enable RTSP streaming on specified port (default: 8554)"
    echo "  --http-port PORT     Enable HTTP streaming on specified port (default: 8080)"
    echo "  --no-streaming       Disable all streaming (TeamSpeak only mode)"
    echo "  --sink-name NAME     Custom name for the virtual sink (default: ts_music_sink)"
    echo "  --source-name NAME   Custom name for the virtual microphone (default: TS_Music_Bot)"
    echo "Example: $0 https://www.youtube.com/watch?v=example --rtsp-port 8554 --http-port 8080"
    exit 1
}

# Check for help flag first
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_usage
fi

# Check if a YouTube URL was provided
if [ $# -lt 1 ]; then
    show_usage
fi

YOUTUBE_URL="$1"
shift

# Default settings
RTSP_PORT=""
HTTP_PORT=""
ENABLE_STREAMING=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_usage
            ;;
        --rtsp-port)
            RTSP_PORT="$2"
            shift 2
            ;;
        --http-port)
            HTTP_PORT="$2"
            shift 2
            ;;
        --no-streaming)
            ENABLE_STREAMING=false
            shift
            ;;
        --sink-name)
            SINK_NAME="$2"
            shift 2
            ;;
        --source-name)
            SOURCE_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Set default ports if streaming is enabled and ports aren't specified
if [ "$ENABLE_STREAMING" = true ]; then
    [ -z "$RTSP_PORT" ] && RTSP_PORT="8554"
    [ -z "$HTTP_PORT" ] && HTTP_PORT="8080"
fi

RTSP_PATH="/audio"
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo "Setting up virtual audio pipeline for TeamSpeak with YouTube URL: $YOUTUBE_URL"
if [ "$ENABLE_STREAMING" = true ]; then
    [ -n "$RTSP_PORT" ] && echo "Will stream audio via RTSP on rtsp://$LOCAL_IP:$RTSP_PORT$RTSP_PATH"
    [ -n "$HTTP_PORT" ] && echo "Will stream audio via HTTP on http://$LOCAL_IP:$HTTP_PORT/stream.ogg"
else
    echo "Streaming is disabled (TeamSpeak only mode)"
fi

# Ensure sink name is not too long (max 15 chars)
if [ ${#SINK_NAME} -gt 15 ]; then
    SINK_NAME="${SINK_NAME:0:15}"
fi

# Ensure source name is not too long (max 15 chars)
if [ ${#SOURCE_NAME} -gt 15 ]; then
    SOURCE_NAME="${SOURCE_NAME:0:15}"
fi

# Create virtual audio devices
echo "Creating virtual audio devices..."
SINK_ID=$(pactl load-module module-null-sink sink_name=$SINK_NAME sink_properties=device.description=$SINK_NAME)
if [ -z "$SINK_ID" ]; then
    echo "Failed to create virtual sink. Exiting."
    exit 1
fi

# Create a virtual microphone source that uses the monitor of the sink
# Important: We set both source_name and device.description to $SOURCE_NAME so it appears correctly in TeamSpeak
VIRTUAL_MIC_ID=$(pactl load-module module-virtual-source source_name=$SOURCE_NAME master=$SINK_NAME.monitor source_properties=device.description=$SOURCE_NAME)
if [ -z "$VIRTUAL_MIC_ID" ]; then
    echo "Failed to create virtual microphone. Cleaning up."
    pactl unload-module "$SINK_ID" 2>/dev/null || true
    exit 1
fi

echo "Virtual microphone created: $SOURCE_NAME"

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    
    # Kill VLC processes if still running
    if [ -n "$VLC_PID" ] && ps -p "$VLC_PID" >/dev/null 2>&1; then
        kill "$VLC_PID" 2>/dev/null || pkill -f "vlc" 2>/dev/null || true
    fi
    
    if [ -n "$RTSP_VLC_PID" ] && ps -p "$RTSP_VLC_PID" >/dev/null 2>&1; then
        kill "$RTSP_VLC_PID" 2>/dev/null || pkill -f "vlc.*rtsp" 2>/dev/null || true
    fi
    
    if [ -n "$HTTP_VLC_PID" ] && ps -p "$HTTP_VLC_PID" >/dev/null 2>&1; then
        kill "$HTTP_VLC_PID" 2>/dev/null || pkill -f "vlc.*http" 2>/dev/null || true
    fi
    
    # Unload PulseAudio modules
    [ -n "$VIRTUAL_MIC_ID" ] && pactl unload-module "$VIRTUAL_MIC_ID" 2>/dev/null || true
    [ -n "$SINK_ID" ] && pactl unload-module "$SINK_ID" 2>/dev/null || true
    
    echo "Cleanup complete."
    exit 0
}

# Set up cleanup on script termination
trap cleanup EXIT INT TERM

echo "Getting direct stream URL from YouTube..."
# Get the direct stream URL using yt-dlp
STREAM_URL=$(yt-dlp -f 'bestaudio' -g "$YOUTUBE_URL")

if [ -z "$STREAM_URL" ]; then
    echo "Failed to get stream URL from YouTube. Exiting."
    cleanup
fi

echo "Starting VLC with direct stream URL..."

# Start VLC with the direct stream URL and route audio to the virtual sink
PULSE_SINK=$SINK_NAME cvlc --no-video --volume=256 --audio --audio-visual=visual --effect-list=spectrum --network-caching=10000 "$STREAM_URL" &
VLC_PID=$!

echo "VLC started with PID: $VLC_PID"
sleep 2 # Wait briefly for VLC initialization

# Verify VLC process started correctly
if ! ps -p "$VLC_PID" >/dev/null 2>&1; then
    echo "VLC failed to start. Exiting."
    cleanup
fi

# Ensure the sink is not muted and set to 100% volume
pactl set-sink-volume $SINK_NAME 100%
pactl set-sink-mute $SINK_NAME 0

# Ensure the virtual mic is not muted and set to 100% volume
pactl set-source-volume $SOURCE_NAME 100%
pactl set-source-mute $SOURCE_NAME 0

# Start RTSP streaming if enabled
if [ "$ENABLE_STREAMING" = true ] && [ -n "$RTSP_PORT" ]; then
    echo "Starting RTSP server on port $RTSP_PORT..."
    # Using mpga instead of mp3 for RTSP compatibility
    cvlc -vvv pulse://$SINK_NAME.monitor --sout "#transcode{acodec=mpga,ab=128,channels=2}:rtp{sdp=rtsp://:$RTSP_PORT$RTSP_PATH}" --sout-keep &
    RTSP_VLC_PID=$!

    # Verify RTSP VLC process started correctly
    if ! ps -p "$RTSP_VLC_PID" >/dev/null 2>&1; then
        echo "RTSP streaming failed to start. Continuing without RTSP..."
    else
        echo "✓ RTSP streaming started successfully"
        echo "✓ RTSP URL: rtsp://$LOCAL_IP:$RTSP_PORT$RTSP_PATH"
    fi
fi

# Start HTTP streaming if enabled
if [ "$ENABLE_STREAMING" = true ] && [ -n "$HTTP_PORT" ]; then
    echo "Starting HTTP streaming server on port $HTTP_PORT..."
    cvlc -vvv pulse://$SINK_NAME.monitor --sout "#transcode{vcodec=theo,vb=800,acodec=vorb,ab=128,channels=2}:http{mux=ogg,dst=:$HTTP_PORT/stream.ogg}" --sout-keep &
    HTTP_VLC_PID=$!

    # Verify HTTP VLC process started correctly
    if ! ps -p "$HTTP_VLC_PID" >/dev/null 2>&1; then
        echo "HTTP streaming failed to start. Continuing without browser streaming..."
    else
        echo "✓ HTTP streaming started successfully"
        echo "✓ Browser URL: http://$LOCAL_IP:$HTTP_PORT/stream.ogg"
        echo "✓ Open this URL in your web browser to listen to the stream"
        
        # Create a simple HTML player file for easy access
        cat > /tmp/audio_player.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Audio Stream Player</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            text-align: center;
        }
        audio {
            width: 100%;
            margin: 20px 0;
        }
        .info {
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>YouTube Audio Stream</h1>
    
    <audio controls autoplay>
        <source src="http://$LOCAL_IP:$HTTP_PORT/stream.ogg" type="audio/ogg">
        Your browser does not support the audio element.
    </audio>
    
    <div class="info">
        If you can't hear audio, try opening the direct URL in VLC or another media player:
        <br>http://$LOCAL_IP:$HTTP_PORT/stream.ogg
        <br>$([ -n "$RTSP_PORT" ] && echo "RTSP URL (for media players): rtsp://$LOCAL_IP:$RTSP_PORT$RTSP_PATH")
    </div>
</body>
</html>
EOF
        echo "✓ Created HTML player at /tmp/audio_player.html"
        echo "✓ Open this file in a browser to access the player"
    fi
fi

echo "✓ Audio pipeline setup complete!"
echo "✓ In TeamSpeak, select '$SOURCE_NAME' as your microphone input"
echo "✓ YouTube audio is now available for streaming to your TeamSpeak channel"
echo "✓ Press Ctrl+C to stop."

# Keep running until interrupted or VLC exits unexpectedly
while true; do
    if ! ps -p "$VLC_PID" >/dev/null 2>&1; then
        echo "VLC terminated unexpectedly. Exiting..."
        cleanup
    fi
    
    if [ "$ENABLE_STREAMING" = true ] && [ -n "$RTSP_PORT" ] && [ -n "$RTSP_VLC_PID" ] && ! ps -p "$RTSP_VLC_PID" >/dev/null 2>&1; then
        echo "RTSP streaming terminated unexpectedly. Restarting..."
        cvlc -vvv pulse://$SINK_NAME.monitor --sout "#transcode{acodec=mpga,ab=128,channels=2}:rtp{sdp=rtsp://:$RTSP_PORT$RTSP_PATH}" --sout-keep &
        RTSP_VLC_PID=$!
    fi
    
    if [ "$ENABLE_STREAMING" = true ] && [ -n "$HTTP_PORT" ] && [ -n "$HTTP_VLC_PID" ] && ! ps -p "$HTTP_VLC_PID" >/dev/null 2>&1; then
        echo "HTTP streaming terminated unexpectedly. Restarting..."
        cvlc -vvv pulse://$SINK_NAME.monitor --sout "#transcode{vcodec=theo,vb=800,acodec=vorb,ab=128,channels=2}:http{mux=ogg,dst=:$HTTP_PORT/stream.ogg}" --sout-keep &
        HTTP_VLC_PID=$!
    fi
    
    sleep 1
done
