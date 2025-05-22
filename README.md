# Taby - TeamSpeak YouTube Audio Streamer - Version 2.0.0

Taby is a versatile tool that allows you to stream audio from YouTube videos directly to TeamSpeak. It creates virtual audio devices that can be selected as microphone inputs in TeamSpeak, enabling you to share music or other audio content with your TeamSpeak friends.

## Features

- Stream audio from YouTube videos to TeamSpeak
- Queue multiple YouTube streams with per-stream options
- Manage multiple concurrent streams
- Customize audio quality, codec, bitrate, and **volume per stream** (at time of adding or live for volume)
- **Live control**: Change volume and URL of active streams via CLI.
- RTSP and HTTP streaming support for listening outside TeamSpeak
- User-friendly **Qt (PySide6) GUI** interface
- Command-line interface for advanced users and automation
- Load playlists from text files
- **Graceful shutdown**: Ensures all stream processes and virtual audio devices are cleaned up on exit.
- **Multi-distro installer** for dependencies (Debian/Ubuntu, Fedora, Arch Linux).
- Optional installer for the **TeamSpeak 3 Client** itself.

## Requirements

- Linux operating system (Debian/Ubuntu, Fedora, Arch Linux and derivatives supported by installer)
- PulseAudio sound system
- VLC media player (`cvlc` command)
- yt-dlp (YouTube downloader)
- Python 3.6+
- **PySide6** (for the GUI, e.g., `python3-pyside6` or `pip install PySide6`)
- TeamSpeak client (for the primary use case)
- `git` and `curl` (for installation scripts)

## Installation

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/yourusername/taby.git 
    cd taby
    ```
    (Replace `yourusername/taby.git` with the actual repository URL if applicable)

2.  **Run Dependency Installer (`install.sh`)**:
    This script installs core dependencies for Taby (VLC, yt-dlp, PulseAudio tools, Python essentials, and PySide6 for the GUI).
    ```bash
    sudo ./install.sh
    ```
    The script attempts to auto-detect your Linux distribution (Debian/Ubuntu, Fedora, Arch Linux) and uses the appropriate package manager. For Debian/Ubuntu, `yt-dlp` is installed manually via `curl` to get the latest version. For other distributions, it tries to use the system's package manager for `yt-dlp`.

3.  **Optional: Install TeamSpeak 3 Client (`install_teamspeak.sh`)**:
    If you don't have the TeamSpeak 3 Linux client, you can use this script to download and install it.
    ```bash
    sudo ./install_teamspeak.sh
    ```
    This script:
    - Downloads a recent version of the TeamSpeak 3 Client (`.run` file) from the official website.
    - Prompts you to accept the TeamSpeak license during its execution.
    - Installs the client to `/opt/TeamSpeak3-Client`.
    - Creates a system-wide command `teamspeak3-client` by adding a symlink to `/usr/local/bin`.
    - Attempts to create a `.desktop` file for application menus.
    *Note: The TeamSpeak version in the script might need updating over time if the download URL changes significantly.*

## Usage

### GUI Mode (`gui_qt.py`)

Launch the graphical interface (now powered by Qt/PySide6):

```bash
./gui_qt.py 
```
(Ensure `gui_qt.py` is executable or run with `python3 ./gui_qt.py`)

The GUI allows you to:
- Add YouTube URLs to the queue. When adding a URL, a dialog appears allowing you to set specific options for that stream:
    - Audio Quality (for `yt-dlp`)
    - Stream Codec (for RTSP/HTTP output)
    - Stream Bitrate (for RTSP/HTTP output)
    - **Volume** (for playback, 0-150%)
- Start, stop, and view active streams.
- Manage the queue (add, remove, start next).
- Load URLs from playlist files.
- When the GUI is closed (e.g., by clicking the 'X' button), it gracefully shuts down all active streams.

### Controller CLI Mode (`taby_controller.py`)

The controller manages multiple `taby.sh` instances, the queue, and scheduling. It uses an **in-memory database**, meaning the queue and list of active streams are **not persisted** if the controller is restarted.

```bash
./taby_controller.py [options]
```
(Ensure `taby_controller.py` is executable or run with `python3 ./taby_controller.py`)

**Common Options:**
- `-u URL, --url URL`: Add YouTube URL to queue.
- `-p FILE, --playlist FILE`: Load YouTube URLs from a playlist file.
- `-l, --list`: List active instances and queue, then exit.
- `-s PATH, --script PATH`: Path to `taby.sh` script (default: `./taby.sh`).
- `--max-concurrent N`: Max concurrent `taby.sh` instances (default: 5).
- `--log-dir DIR`: Log directory for instances (default: `/tmp/taby-controller-logs`).

**Default Stream Settings (used if not specified per-stream):**
- `--audio-quality QUALITY`: Default `yt-dlp` audio quality (default: `bestaudio`).
- `--stream-bitrate BITRATE`: Default RTSP/HTTP stream bitrate (kb/s) (default: 128).
- `--stream-codec CODEC`: Default RTSP/HTTP stream codec (default: `mp3`).
- `--stream-volume PERCENTAGE`: Default sink volume (0-150) for new streams (default: 100).

**Port Settings:**
- `--rtsp-base-port PORT`: Base RTSP port (default: 8554).
- `--http-base-port PORT`: Base HTTP port (default: 8080).
- `--port-increment N`: Port increment for subsequent instances (default: 10).

**Interactive Mode:**
Run without `-u`, `-p`, or `-l` for interactive mode. Key commands:
- `add <URL> [options_json]`: Adds a URL. `options_json` is optional, e.g., `{"volume": 80, "audio_quality": "worstaudio"}`.
- `setvol <ID> <VOLUME>`: **New!** Changes the volume (0-150) of an active stream instance ID.
- `changeurl <ID> <NEW_URL> [options_json]`: **New!** Changes the URL of an active stream ID. Optionally, new stream options can be provided. The stream reuses the original ID, ports, and PulseAudio sink/source names.
- `list`, `queue`, `start-next`, `stop <ID>`, `stop-all`, `clean`, `help`.
- Exiting ( `exit`, `quit`, Ctrl+C) triggers graceful shutdown.

### Direct Script Usage (`taby.sh`)

For advanced users or testing a single stream:
```bash
./taby.sh <youtube_url> [options]
```
**Common Options:**
- `--rtsp-port PORT`, `--http-port PORT`, `--no-streaming`
- `--sink-name NAME`, `--source-name NAME`
- `--volume PERCENTAGE` (0-150, default: 100)
- `--audio-quality QUALITY`, `--stream-bitrate BITRATE`, `--stream-codec CODEC`

## How It Works

Taby uses `yt-dlp` to get audio stream URLs.
1.  The **controller** (`taby_controller.py`) manages a queue (in an ephemeral in-memory database) and launches `taby.sh` instances.
2.  Each `taby.sh` instance creates a PulseAudio null sink and a virtual source (microphone).
3.  `cvlc` (VLC) plays YouTube audio into the sink. Volume and other parameters are applied.
4.  The virtual source is selected as mic in TeamSpeak.
5.  Optional RTSP/HTTP streaming is handled by separate VLC processes within `taby.sh`.
6.  **Graceful shutdown** (GUI close, CLI exit/Ctrl+C) tells the controller to stop all `taby.sh` instances, which then clean up their VLC processes and PulseAudio devices.

## Troubleshooting
- **No audio in TeamSpeak**: Check correct virtual source selected in TeamSpeak, stream volume (GUI/CLI options), and PulseAudio Volume Control (`pavucontrol`).
- **Stream fails**: Check logs in `/tmp/taby-controller-logs/`. Update `yt-dlp` (`sudo yt-dlp -U`). Check port conflicts.
- **High CPU**: Lower audio quality/bitrate in stream options. Disable RTSP/HTTP if unused.
- **"Invalid JSON"**: In controller CLI `add` or `changeurl` commands, ensure options are valid JSON (double quotes for keys/strings).
- **Orphaned Processes**: Taby aims for clean exits. If issues occur, use `ps aux | grep taby` or `ps aux | grep cvlc` to find and kill processes.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Acknowledgments
- VLC (`cvlc`)
- yt-dlp
- PulseAudio
- Qt (PySide6 for the GUI)
