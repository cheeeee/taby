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

## Dependencies and Versions

Taby relies on several external programs and libraries. The `install.sh` script attempts to install these on supported distributions (Debian/Ubuntu, Fedora, Arch Linux). For manual installations or unsupported systems, please ensure the following (or compatible newer versions) are present:

*   **Python**: 3.6 or newer. (Python 3.7+ recommended for optimal standard library features).
*   **PySide6**: 6.2 or newer (compatible with Python 3.6+). The latest stable version available for your Python version is generally recommended for the Qt-based GUI (`gui_qt.py`).
*   **VLC (VideoLAN Client)**: 3.0.x or newer. Specifically, the `cvlc` command-line utility (often included in the main `vlc` package) is required for audio playback and streaming.
*   **yt-dlp**: Latest version strongly recommended. This program is updated frequently to maintain compatibility with YouTube and other video platforms. The `install.sh` script attempts to install a recent version. You can also update it manually via `pip install --upgrade yt-dlp` or by following instructions on the [yt-dlp GitHub page](https://github.com/yt-dlp/yt-dlp).
*   **PulseAudio**: A standard, functional system installation is required, typically version 13.x or newer. The `pactl` and `pacmd` command-line utilities (usually part of `pulseaudio-utils` or the main `pulseaudio` package) are essential for Taby's audio routing.
*   **Git**: Required for cloning the repository and potentially for updates if managing a cloned version.
*   **Curl**: Required by `install.sh` for downloading `yt-dlp` on some distributions and by `install_teamspeak.sh` for downloading the TeamSpeak client.
*   **Standard GNU/Linux Utilities**: Basic commands like `bash`, `awk`, `grep`, `mv`, `rm`, `chmod`, `ln`, `mktemp`, `ps` are assumed to be present.
*   **TeamSpeak 3 Client**: Required for the primary use case of streaming audio into TeamSpeak. The optional `install_teamspeak.sh` script can assist with its installation.

**Note on `install.sh`**:
The provided `install.sh` script will attempt to:
1. Detect your Linux distribution (Debian/Ubuntu, Fedora, Arch Linux).
2. Install the necessary dependencies using your system's package manager.
3. For Debian/Ubuntu, it installs `yt-dlp` directly from GitHub to ensure a recent version.
4. For GUI functionality, it will try to install PySide6.

If you are using a different distribution, please use the list above as a guide for manual installation.

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

## Creating a Standalone Executable (Linux)

For easier distribution or to run Taby on systems without a full Python development environment (though core runtime dependencies like VLC, PulseAudio, and yt-dlp will still be needed on the target system), you can create a standalone executable using PyInstaller.

1.  **Ensure Dependencies are Met**:
    First, ensure you have all the runtime dependencies listed in the "Dependencies and Versions" section installed (VLC, yt-dlp, PulseAudio tools). PyInstaller bundles Python and PySide6, but not these system-level tools.

2.  **Run the Build Script**:
    The project includes a `build_executable.sh` script to automate the PyInstaller process.
    ```bash
    cd taby # Navigate to the project root directory if you haven't already
    bash ./build_executable.sh
    ```
    - The script will first check if PyInstaller is installed via `pip`. If not, it will prompt you to install it.
    - It bundles the main GUI application (`gui_qt.py`) and the `taby.sh` script (which is required by the controller).
    - It uses the `--onefile` option to create a single executable.
    - It uses `--windowed` so no console window appears when running the GUI executable.
    - An optional icon (`assets/icon.png`) will be included if found.

3.  **Locate the Executable**:
    After a successful build, the standalone executable will be located in the `dist/` directory within your project folder (e.g., `dist/TabyGUI`).

4.  **Running the Executable**:
    You can copy this single executable file to another compatible Linux system and run it. Remember that the target system still needs VLC, yt-dlp, and PulseAudio installed for Taby to function correctly. The executable contains the Python interpreter and all necessary Python libraries (like PySide6).

**Notes on Bundling**:
- The `taby_controller.py` script has been adapted with a `resource_path` function to correctly locate `taby.sh` when bundled into the executable.
- The `build_executable.sh` script adds `taby.sh` to the root of the bundle, making it accessible via `resource_path("taby.sh")`.

## Usage

### GUI Mode (`gui_qt.py` or Standalone Executable)

Launch the graphical interface:
- From source: `python3 ./gui_qt.py` (or `./gui_qt.py` if executable)
- If you created a standalone executable: `./dist/TabyGUI`

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
- `-s PATH, --script PATH`: Path to `taby.sh` script (default: `./taby.sh`; resolved for bundling).
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
1.  The **controller** (`taby_controller.py`) manages a queue (in an ephemeral in-memory database) and launches `taby.sh` instances. When running as part of a bundled executable, it locates `taby.sh` within the bundle.
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
- PyInstaller (for executable creation)
