#!/usr/bin/env python3

import sys
import os
import subprocess
import json 
import shutil # For shutil.which()

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QTreeWidget, QTreeWidgetItem, QLabel, QPushButton, QHBoxLayout,
    QLineEdit, QTabWidget, QHeaderView, QGroupBox, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QComboBox, QSpinBox,
    QFileDialog
)
from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QIcon 

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from taby_controller import TabyController
except ImportError:
    # This will be caught by check_gui_dependencies if taby_controller itself is missing
    # or if taby_controller fails to import its own dependencies.
    # For now, if TabyController itself is missing, the later check for its CLI tools will also likely fail.
    pass 

def check_gui_dependencies(app_instance):
    """Checks for essential CLI tools and Python libraries."""
    missing_cli_tools = []
    cli_tools_to_check = ['pactl', 'cvlc', 'yt-dlp']
    for tool in cli_tools_to_check:
        if shutil.which(tool) is None:
            missing_cli_tools.append(tool)

    missing_python_libs = []
    try:
        import PySide6.QtCore # Try importing a core module
    except ImportError:
        missing_python_libs.append("PySide6 (Core Components)") 
    
    try:
        # Check if TabyController could be imported (proxy for its own internal dependencies)
        # This is a bit indirect; TabyController itself should do more specific checks if run headlessly.
        from taby_controller import TabyController
    except ImportError as e:
        missing_python_libs.append(f"TabyController or its dependencies ({e.name})")


    error_messages = []
    if missing_cli_tools:
        error_messages.append(f"Missing command-line tools: {', '.join(missing_cli_tools)}.")
    if missing_python_libs:
        error_messages.append(f"Missing Python libraries: {', '.join(missing_python_libs)}.")

    if error_messages:
        full_error_message = ("The following dependencies are missing or not found in PATH:\n\n"
                              + "\n".join(error_messages)
                              + "\n\nPlease run 'sudo ./install.sh' or install them manually.")
        
        # Ensure QApplication instance exists before QMessageBox
        if QApplication.instance() is None:
            # This case should ideally not happen if check_gui_dependencies is called after app creation.
            # If it must be called before, a temporary app instance is needed here.
            # For this implementation, we assume 'app_instance' is valid.
            pass

        QMessageBox.critical(None, "Dependency Error", full_error_message)
        return False
    return True

class StreamOptionsDialog(QDialog):
    def __init__(self, parent=None, current_options=None):
        super().__init__(parent)
        self.setWindowTitle("Stream Options")
        self.setMinimumWidth(350)
        
        self.current_options = current_options if current_options else {}
        
        self.layout = QFormLayout(self)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["bestaudio", "bestaudio[ext=m4a]", "worstaudio"])
        self.quality_combo.setCurrentText(self.current_options.get("audio_quality", "bestaudio"))
        self.layout.addRow("Audio Quality:", self.quality_combo)
        
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["mp3", "opus", "vorb", "flac"])
        self.codec_combo.setCurrentText(self.current_options.get("stream_codec", "mp3"))
        self.layout.addRow("Stream Codec:", self.codec_combo)
        
        self.bitrate_spinbox = QSpinBox()
        self.bitrate_spinbox.setRange(64, 320); self.bitrate_spinbox.setSingleStep(32)
        self.bitrate_spinbox.setValue(self.current_options.get("stream_bitrate", 128))
        self.layout.addRow("Bitrate (kbps):", self.bitrate_spinbox)
        
        self.volume_spinbox = QSpinBox()
        self.volume_spinbox.setRange(0, 150); self.volume_spinbox.setSingleStep(10)
        self.volume_spinbox.setValue(self.current_options.get("volume", 100))
        self.layout.addRow("Volume (%):", self.volume_spinbox)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept); self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_options(self):
        return { "audio_quality": self.quality_combo.currentText(), "stream_codec": self.codec_combo.currentText(),
                 "stream_bitrate": self.bitrate_spinbox.value(), "volume": self.volume_spinbox.value() }

class TabyQtGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taby - TeamSpeak YouTube Streamer (Qt)")
        self.setGeometry(100, 100, 1000, 700) 

        # Controller might fail if its own dependencies (like taby.sh path) are wrong,
        # but the core CLI tools for taby.sh are checked by check_gui_dependencies.
        try:
            self.controller = TabyController(self.get_default_args())
        except Exception as e: # Catch any error during controller init
             QMessageBox.critical(self, "Controller Error", f"Failed to initialize TabyController: {e}\nEnsure taby.sh is accessible and configured correctly.")
             sys.exit(1) # Exit if controller cannot be initialized

        self.current_stream_options = {
            "volume": self.controller.settings.get("stream_volume", 100),
            "audio_quality": self.controller.settings.get("audio_quality", "bestaudio"),
            "stream_codec": self.controller.settings.get("stream_codec", "mp3"),
            "stream_bitrate": self.controller.settings.get("stream_bitrate", 128)
        }
        
        self.setup_ui()
        self.update_displays()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_displays)
        self.timer.start(5000)

    def get_default_args(self):
        class Args: pass
        args = Args(); args.script = "./taby.sh"; args.rtsp_base_port = 8554; args.http_base_port = 8080
        args.port_increment = 10; args.max_concurrent = 5; args.log_dir = "/tmp/taby-controller-logs"
        args.audio_quality = "bestaudio"; args.stream_bitrate = 128; args.stream_codec = "mp3"
        args.stream_volume = 100; args.url = None; args.playlist = None; args.list = False
        return args

    def setup_ui(self):
        self.central_widget = QWidget(); self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        url_group_box = QGroupBox("Add Stream"); url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("YouTube URL:"))
        self.url_entry = QLineEdit(); self.url_entry.setPlaceholderText("Enter YouTube URL"); url_layout.addWidget(self.url_entry)
        self.add_url_button = QPushButton("Add URL"); self.add_url_button.clicked.connect(self.add_url_handler); url_layout.addWidget(self.add_url_button)
        self.load_playlist_button = QPushButton("Load Playlist"); self.load_playlist_button.clicked.connect(self.load_playlist_handler); url_layout.addWidget(self.load_playlist_button)
        self.refresh_button = QPushButton("Refresh All"); self.refresh_button.clicked.connect(self.update_displays); url_layout.addWidget(self.refresh_button)
        url_group_box.setLayout(url_layout); self.main_layout.addWidget(url_group_box)
        self.tabs = QTabWidget(); self.main_layout.addWidget(self.tabs)
        self.streams_tab = QWidget(); self.tabs.addTab(self.streams_tab, "Active Streams")
        streams_layout = QVBoxLayout(self.streams_tab)
        self.instances_tree = QTreeWidget(); self.instances_tree.setColumnCount(3) 
        self.instances_tree.setHeaderLabels(["ID", "URL", "Stream Title"])
        self.instances_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.instances_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.instances_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        streams_layout.addWidget(self.instances_tree)
        streams_controls_layout = QHBoxLayout()
        self.stop_selected_button = QPushButton("Stop Selected"); self.stop_selected_button.clicked.connect(self.stop_selected_instance_handler); streams_controls_layout.addWidget(self.stop_selected_button)
        self.stop_all_button = QPushButton("Stop All"); self.stop_all_button.clicked.connect(self.stop_all_instances_handler); streams_controls_layout.addWidget(self.stop_all_button)
        streams_layout.addLayout(streams_controls_layout)
        self.queue_tab = QWidget(); self.tabs.addTab(self.queue_tab, "Queue")
        queue_layout = QVBoxLayout(self.queue_tab)
        self.queue_tree = QTreeWidget(); self.queue_tree.setColumnCount(2); 
        self.queue_tree.setHeaderLabels(["URL", "Options"])
        self.queue_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.queue_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        queue_layout.addWidget(self.queue_tree)
        queue_controls_layout = QHBoxLayout()
        self.start_next_button = QPushButton("Start Next"); self.start_next_button.clicked.connect(self.start_next_from_queue_handler); queue_controls_layout.addWidget(self.start_next_button)
        self.remove_queue_button = QPushButton("Remove Selected"); self.remove_queue_button.clicked.connect(self.remove_selected_from_queue_handler); queue_controls_layout.addWidget(self.remove_queue_button)
        queue_layout.addLayout(queue_controls_layout)
        self.setStatusBar(QLabel("Initializing..."))

    @Slot()
    def add_url_handler(self):
        url = self.url_entry.text().strip()
        if not url: QMessageBox.warning(self, "Input Error", "URL empty."); return
        if not (url.startswith(('http://','https://')) and ("youtube.com/" in url or "youtu.be/" in url)):
            QMessageBox.critical(self, "Invalid URL", "Enter valid YouTube URL."); return
        dialog = StreamOptionsDialog(self, self.current_stream_options)
        if dialog.exec() == QDialog.Accepted:
            opts = dialog.get_options(); self.current_stream_options.update(opts)
            if self.controller.add_to_queue(url, options=opts):
                self.url_entry.clear(); self.update_displays()
            else: QMessageBox.critical(self, "Error", "Controller failed to add URL.")
        else: print("Stream options dialog cancelled.")

    @Slot()
    def load_playlist_handler(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Playlist", "", "Text (*.txt);;All (*.*)")
        if path:
            try: self.controller.load_playlist(path); self.update_displays(); QMessageBox.information(self, "Playlist Loaded", f"Loaded: {os.path.basename(path)}")
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load: {e}")

    @Slot()
    def stop_selected_instance_handler(self):
        sel = self.instances_tree.selectedItems()
        if not sel: QMessageBox.warning(self, "Selection Error", "No stream selected."); return
        try:
            inst_id = int(sel[0].text(0))
            if self.controller.stop_instance(inst_id): self.update_displays()
            else: QMessageBox.information(self, "Stop Instance", f"Stop instance {inst_id} attempted.")
        except ValueError: QMessageBox.critical(self, "Error", f"Invalid instance ID in tree: {sel[0].text(0)}")
            
    @Slot()
    def stop_all_instances_handler(self):
        if not self.controller.instances: QMessageBox.information(self, "No Streams", "No streams to stop."); return
        reply = QMessageBox.question(self, "Confirm Stop All", "Stop all active streams?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: self.controller.shutdown(); self.update_displays()

    @Slot()
    def start_next_from_queue_handler(self):
        if not self.controller.queue: QMessageBox.information(self, "Queue Empty", "Queue is empty."); return
        if len(self.controller.instances) >= self.controller.settings['max_concurrent']:
            QMessageBox.information(self, "Limit Reached", f"Max streams ({self.controller.settings['max_concurrent']}) active."); return
        if self.controller.start_next(): self.update_displays()
        else: QMessageBox.critical(self, "Error", "Failed to start next stream.")

    @Slot()
    def remove_selected_from_queue_handler(self):
        sel = self.queue_tree.selectedItems()
        if not sel: QMessageBox.warning(self, "Selection Error", "No queue item selected."); return
        item_id = sel[0].data(0, Qt.UserRole) # Retrieve stored ID
        if item_id is not None:
            self.controller.remove_from_queue(item_id); self.update_displays()
        else: QMessageBox.critical(self, "Error", "Could not get ID for selected queue item.")

    def fetch_pulse_friendly_name(self, device_name_part, device_type="source"):
        cmd = ["pacmd", f"list-{device_type}s"]
        try:
            output = subprocess.check_output(cmd, text=True, timeout=0.25) # Shorter timeout
            in_block = False
            for line in output.splitlines():
                s_line = line.strip()
                if f"name: <{device_name_part}" in s_line: in_block = True
                elif in_block and "device.description" in s_line: return s_line.split("=")[1].strip().strip('"')
                elif in_block and s_line.startswith("name: <"): break
            return f"{device_name_part}" # Fallback to device name part
        except Exception: return f"{device_name_part}" # Fallback

    @Slot()
    def update_displays(self):
        print("GUI: Updating displays...")
        self.controller.clean_instances()
        self.instances_tree.clear()
        for instance in self.controller.instances:
            title = self.fetch_pulse_friendly_name(instance.get("source_name", ""), "source")
            if "Error" in title or "N/A" in title or title == instance.get("source_name", ""): # If source name fetch failed or was basic
                title = self.fetch_pulse_friendly_name(instance.get("sink_name", ""), "sink")
            if "Error" in title or "N/A" in title or title == instance.get("sink_name", ""): # If sink name also failed
                 title = instance.get("options", {}).get("title_override", f"Stream {instance['id']}") # Future: store title from yt-dlp in options

            item = QTreeWidgetItem([str(instance["id"]), instance.get("url", "N/A"), title])
            self.instances_tree.addTopLevelItem(item)

        self.queue_tree.clear()
        for item_data in self.controller.queue:
            opts_str = ", ".join([f"{k}:{v}" for k,v in item_data.get("options",{}).items() if v is not None])
            tree_item = QTreeWidgetItem([item_data.get("url","N/A"), opts_str if opts_str else "Defaults"])
            tree_item.setData(0, Qt.UserRole, item_data.get("id")) 
            self.queue_tree.addTopLevelItem(tree_item)
            
        self.statusBar().showMessage(f"Active: {len(self.controller.instances)}/{self.controller.settings['max_concurrent']} | Queue: {len(self.controller.queue)}")

    def closeEvent(self, event):
        print("GUI: Window close. Shutting down.")
        if self.timer: self.timer.stop()
        if self.controller: self.controller.shutdown()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv) # QApplication must be created first

    # Perform dependency checks after QApplication is initialized
    if not check_gui_dependencies(app):
        # QMessageBox is shown by check_gui_dependencies if it returns False
        sys.exit(1) 
    
    # Ensure TabyController can be imported and initialized
    try:
        from taby_controller import TabyController # Re-check if it's available
    except ImportError as e:
        QMessageBox.critical(None, "Import Error", f"Failed to import TabyController: {e}.\nMake sure taby_controller.py is in the correct path.")
        sys.exit(1)
        
    window = TabyQtGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
