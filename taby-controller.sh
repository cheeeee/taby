#!/bin/bash

# taby-controller: Manage multiple taby instances for streaming a list of YouTube URLs
# Each taby instance will have a unique sink/source name based on the YouTube stream name

# Check if dependencies are installed
for cmd in yt-dlp jq curl; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is not installed. Please install it first."
        exit 1
    fi
done

# Default settings
TABY_SCRIPT="./taby.sh"
PLAYLIST_FILE=""
ACTIVE_TABIES=()
RTSP_BASE_PORT=8554
HTTP_BASE_PORT=8080
PORT_INCREMENT=10
MAX_CONCURRENT=5
LOG_DIR="/tmp/taby-controller-logs"

# Display usage information
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help                   Show this help message"
    echo "  -p, --playlist FILE          Specify a playlist file with YouTube URLs (one per line)"
    echo "  -u, --url URL                Add a single YouTube URL to the queue"
    echo "  -s, --script PATH            Path to the taby.sh script (default: ./taby.sh)"
    echo "  --rtsp-base-port PORT        Base port for RTSP streaming (default: 8554)"
    echo "  --http-base-port PORT        Base port for HTTP streaming (default: 8080)"
    echo "  --port-increment NUM         Port increment for each taby instance (default: 10)"
    echo "  --max-concurrent NUM         Maximum number of concurrent taby instances (default: 5)"
    echo "  --log-dir DIR                Directory for log files (default: /tmp/taby-controller-logs)"
    echo ""
    echo "Commands (when running interactively):"
    echo "  list                         List all active taby instances"
    echo "  stop ID                      Stop a specific taby instance by ID"
    echo "  stop-all                     Stop all taby instances"
    echo "  add URL                      Add a YouTube URL to the queue"
    echo "  next                         Stop the oldest taby and start the next in queue"
    echo "  queue                        Show URLs in the queue"
    echo "  help                         Show this help message"
    echo "  exit                         Exit the controller (stops all taby instances)"
    echo ""
    echo "Example: $0 --playlist my_playlist.txt --max-concurrent 3"
    exit 1
}

# Parse command line arguments
URLS_QUEUE=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_usage
            ;;
        -p|--playlist)
            PLAYLIST_FILE="$2"
            shift 2
            ;;
        -u|--url)
            URLS_QUEUE+=("$2")
            shift 2
            ;;
        -s|--script)
            TABY_SCRIPT="$2"
            shift 2
            ;;
        --rtsp-base-port)
            RTSP_BASE_PORT="$2"
            shift 2
            ;;
        --http-base-port)
            HTTP_BASE_PORT="$2"
            shift 2
            ;;
        --port-increment)
            PORT_INCREMENT="$2"
            shift 2
            ;;
        --max-concurrent)
            MAX_CONCURRENT="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Check if taby script exists and is executable
if [ ! -x "$TABY_SCRIPT" ]; then
    echo "Error: taby script not found or not executable at $TABY_SCRIPT"
    echo "Please provide the correct path with --script option"
    exit 1
fi

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Load URLs from playlist file if specified
if [ -n "$PLAYLIST_FILE" ]; then
    if [ ! -f "$PLAYLIST_FILE" ]; then
        echo "Error: Playlist file not found: $PLAYLIST_FILE"
        exit 1
    fi
    
    while IFS= read -r url || [ -n "$url" ]; do
        # Skip empty lines and comments
        if [ -n "$url" ] && [[ ! "$url" =~ ^[[:space:]]*# ]]; then
            URLS_QUEUE+=("$url")
        fi
    done < "$PLAYLIST_FILE"
    
    echo "Loaded ${#URLS_QUEUE[@]} URLs from playlist file"
fi

# Function to get a sanitized name from YouTube video title
get_sanitized_name() {
    local url="$1"
    local video_id="unknown"
    
    # Extract video ID from URL
    if [[ "$url" =~ youtube\.com/watch\?v=([^&]*) ]]; then
        video_id="${BASH_REMATCH[1]}"
    elif [[ "$url" =~ youtu\.be/([^?]*) ]]; then
        video_id="${BASH_REMATCH[1]}"
    else
        # If we can't extract ID, use timestamp
        video_id="video_$(date +%s)"
    fi
    
    # Try to get the video title
    local title
    title=$(yt-dlp --skip-download --print title "$url" 2>/dev/null)
    
    if [ -z "$title" ]; then
        # If title retrieval fails, use video ID
        echo "taby_${video_id}"
    else
        # Sanitize the title: remove special chars, convert spaces to underscores, lowercase
        local sanitized
        sanitized=$(echo "$title" | tr -cd '[:alnum:] ' | tr ' ' '_' | tr '[:upper:]' '[:lower:]' | head -c 20)
        echo "taby_${sanitized}_${video_id:0:6}"
    fi
}

# Function to start a new taby instance
start_taby() {
    local url="$1"
    local instance_id="$2"
    local rtsp_port=$((RTSP_BASE_PORT + (instance_id * PORT_INCREMENT)))
    local http_port=$((HTTP_BASE_PORT + (instance_id * PORT_INCREMENT)))
    
    # Get a name based on the YouTube video title
    local name=$(get_sanitized_name "$url")
    local sink_name="${name}_sink"
    local source_name="${name}_source"
    
    echo "Starting taby instance #$instance_id for URL: $url"
    echo "Using name: $name"
    echo "Sink name: $sink_name"
    echo "Source name: $source_name"
    echo "RTSP port: $rtsp_port, HTTP port: $http_port"
    
    # Start taby with the URL and custom settings
    "$TABY_SCRIPT" "$url" \
        --rtsp-port "$rtsp_port" \
        --http-port "$http_port" \
        --sink-name "$sink_name" \
        --source-name "$source_name" \
        > "$LOG_DIR/taby_${instance_id}.log" 2>&1 &
    
    local pid=$!
    ACTIVE_TABIES+=("$instance_id|$pid|$url|$name|$sink_name|$source_name|$rtsp_port|$http_port")
    
    echo "Taby instance #$instance_id started with PID $pid"
    echo "Log file: $LOG_DIR/taby_${instance_id}.log"
}

# Function to stop a taby instance
stop_taby() {
    local instance_id="$1"
    local found=false
    
    for i in "${!ACTIVE_TABIES[@]}"; do
        IFS='|' read -r id pid url name sink_name source_name rtsp_port http_port <<< "${ACTIVE_TABIES[$i]}"
        
        if [ "$id" = "$instance_id" ]; then
            echo "Stopping taby instance #$id (PID: $pid, Name: $name)"
            echo "Sink: $sink_name, Source: $source_name"
            
            # Kill the process
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "Sent SIGTERM to process $pid"
            else
                echo "Process $pid is not running"
            fi
            
            # Remove from active tabies array
            unset 'ACTIVE_TABIES[$i]'
            ACTIVE_TABIES=("${ACTIVE_TABIES[@]}")  # Reindex array
            found=true
            break
        fi
    done
    
    if [ "$found" = false ]; then
        echo "No taby instance found with ID $instance_id"
    fi
}

# Function to stop all taby instances
stop_all_tabies() {
    echo "Stopping all taby instances..."
    
    for entry in "${ACTIVE_TABIES[@]}"; do
        IFS='|' read -r id pid url name sink_name source_name rtsp_port http_port <<< "$entry"
        
        echo "Stopping taby instance #$id (PID: $pid, Name: $name)"
        echo "Sink: $sink_name, Source: $source_name"
        
        # Kill the process
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
        fi
    done
    
    ACTIVE_TABIES=()
    echo "All taby instances stopped"
}

# Function to list all active taby instances
list_tabies() {
    if [ ${#ACTIVE_TABIES[@]} -eq 0 ]; then
        echo "No active taby instances"
        return
    fi
    
    echo "Active taby instances:"
    echo "--------------------------------------------------------------------------------------------"
    printf "%-5s %-8s %-20s %-20s %-20s %-10s %-10s %s\n" "ID" "PID" "NAME" "SINK" "SOURCE" "RTSP" "HTTP" "STATUS"
    echo "--------------------------------------------------------------------------------------------"
    
    for entry in "${ACTIVE_TABIES[@]}"; do
        IFS='|' read -r id pid url name sink_name source_name rtsp_port http_port <<< "$entry"
        
        # Check if process is still running
        if kill -0 "$pid" 2>/dev/null; then
            status="Running"
        else
            status="Dead"
        fi
        
        # Truncate long fields for better display
        name_short="${name:0:18}"
        sink_short="${sink_name:0:18}"
        source_short="${source_name:0:18}"
        
        printf "%-5s %-8s %-20s %-20s %-20s %-10s %-10s %s\n" \
            "$id" "$pid" "$name_short" "$sink_short" "$source_short" "$rtsp_port" "$http_port" "$status"
    done
    
    echo ""
    echo "URL details:"
    echo "--------------------------------------------------------------------------------------------"
    for entry in "${ACTIVE_TABIES[@]}"; do
        IFS='|' read -r id pid url name sink_name source_name rtsp_port http_port <<< "$entry"
        echo "ID $id: $url"
    done
}

# Function to start the next URL in the queue
start_next() {
    if [ ${#URLS_QUEUE[@]} -eq 0 ]; then
        echo "No URLs in the queue"
        return
    fi
    
    # Check if we've reached the maximum number of concurrent instances
    if [ ${#ACTIVE_TABIES[@]} -ge "$MAX_CONCURRENT" ]; then
        # Find the oldest instance
        local oldest_id
        oldest_id=$(echo "${ACTIVE_TABIES[0]}" | cut -d'|' -f1)
        stop_taby "$oldest_id"
    fi
    
    # Get next URL from queue
    local next_url="${URLS_QUEUE[0]}"
    URLS_QUEUE=("${URLS_QUEUE[@]:1}")  # Remove first element
    
    # Find the next available instance ID
    local next_id=0
    for entry in "${ACTIVE_TABIES[@]}"; do
        local id=$(echo "$entry" | cut -d'|' -f1)
        if [ "$id" -ge "$next_id" ]; then
            next_id=$((id + 1))
        fi
    done
    
    # Start new taby instance
    start_taby "$next_url" "$next_id"
}

# Function to add a URL to the queue
add_url() {
    local url="$1"
    URLS_QUEUE+=("$url")
    echo "Added URL to queue: $url"
    echo "Queue now has ${#URLS_QUEUE[@]} URLs"
}

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    stop_all_tabies
    echo "Exiting taby-controller"
    exit 0
}

# Set up cleanup on script termination
trap cleanup EXIT INT TERM

# Start initial taby instances from the queue
while [ ${#ACTIVE_TABIES[@]} -lt "$MAX_CONCURRENT" ] && [ ${#URLS_QUEUE[@]} -gt 0 ]; do
    start_next
done

# If no URLs were provided, enter interactive mode immediately
if [ ${#ACTIVE_TABIES[@]} -eq 0 ] && [ ${#URLS_QUEUE[@]} -eq 0 ]; then
    echo "No URLs provided. Entering interactive mode."
    echo "Type 'help' for a list of commands."
fi

# Interactive mode
echo "Entering interactive mode. Type 'help' for a list of commands."
while true; do
    echo -n "taby-controller> "
    read -r cmd args
    
    case "$cmd" in
        list)
            list_tabies
            ;;
        stop)
            if [ -z "$args" ]; then
                echo "Error: Missing instance ID. Usage: stop ID"
            else
                stop_taby "$args"
            fi
            ;;
        stop-all)
            stop_all_tabies
            ;;
        add)
            if [ -z "$args" ]; then
                echo "Error: Missing URL. Usage: add URL"
            else
                add_url "$args"
                # Start immediately if we have room
                if [ ${#ACTIVE_TABIES[@]} -lt "$MAX_CONCURRENT" ]; then
                    start_next
                fi
            fi
            ;;
        next)
            # Stop oldest and start next
            if [ ${#ACTIVE_TABIES[@]} -gt 0 ]; then
                local oldest_id
                oldest_id=$(echo "${ACTIVE_TABIES[0]}" | cut -d'|' -f1)
                stop_taby "$oldest_id"
            fi
            start_next
            ;;
        queue)
            echo "URLs in queue (${#URLS_QUEUE[@]}):"
            for i in "${!URLS_QUEUE[@]}"; do
                echo "$((i+1)): ${URLS_QUEUE[$i]}"
            done
            ;;
        help)
            echo "Available commands:"
            echo "  list                         List all active taby instances"
            echo "  stop ID                      Stop a specific taby instance by ID"
            echo "  stop-all                     Stop all taby instances"
            echo "  add URL                      Add a YouTube URL to the queue"
            echo "  next                         Stop the oldest taby and start the next in queue"
            echo "  queue                        Show URLs in the queue"
            echo "  help                         Show this help message"
            echo "  exit                         Exit the controller (stops all taby instances)"
            ;;
        exit)
            echo "Exiting taby-controller..."
            break
            ;;
        "")
            # Empty command, do nothing
            ;;
        *)
            echo "Unknown command: $cmd. Type 'help' for a list of commands."
            ;;
    esac
done

cleanup
