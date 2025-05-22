#!/usr/bin/env python3

import sys
import os
import subprocess
import json # For formatting options in queue display
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
    print("Error: taby_controller.py not found.")
    sys.exit(1)

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
        self.bitrate_spinbox.setRange(64, 320)
        self.bitrate_spinbox.setSingleStep(32)
        self.bitrate_spinbox.setValue(self.current_options.get("stream_bitrate", 128))
        self.layout.addRow("Bitrate (kbps):", self.bitrate_spinbox)
        
        self.volume_spinbox = QSpinBox()
        self.volume_spinbox.setRange(0, 150) # As per taby.sh validation
        self.volume_spinbox.setSingleStep(10)
        self.volume_spinbox.setValue(self.current_options.get("volume", 100))
        self.layout.addRow("Volume (%):", self.volume_spinbox)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_options(self):
        # Called when dialog is accepted
        return {
            "audio_quality": self.quality_combo.currentText(),
            "stream_codec": self.codec_combo.currentText(),
            "stream_bitrate": self.bitrate_spinbox.value(),
            "volume": self.volume_spinbox.value()
        }

class TabyQtGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Taby - TeamSpeak YouTube Streamer (Qt)")
        self.setGeometry(100, 100, 1000, 700) 

        self.controller = TabyController(self.get_default_args())
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
        args = Args()
        args.script = "./taby.sh"; args.rtsp_base_port = 8554; args.http_base_port = 8080
        args.port_increment = 10; args.max_concurrent = 5; args.log_dir = "/tmp/taby-controller-logs"
        args.audio_quality = "bestaudio"; args.stream_bitrate = 128; args.stream_codec = "mp3"
        args.stream_volume = 100; args.url = None; args.playlist = None; args.list = False
        return args

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # URL Entry Group
        url_group_box = QGroupBox("Add Stream")
        url_layout = QHBoxLayout()
        self.url_label = QLabel("YouTube URL:"); url_layout.addWidget(self.url_label)
        self.url_entry = QLineEdit(); self.url_entry.setPlaceholderText("Enter YouTube URL"); url_layout.addWidget(self.url_entry)
        self.add_url_button = QPushButton("Add URL"); self.add_url_button.clicked.connect(self.add_url_handler); url_layout.addWidget(self.add_url_button)
        self.load_playlist_button = QPushButton("Load Playlist"); self.load_playlist_button.clicked.connect(self.load_playlist_handler); url_layout.addWidget(self.load_playlist_button)
        self.refresh_button = QPushButton("Refresh All"); self.refresh_button.clicked.connect(self.update_displays); url_layout.addWidget(self.refresh_button)
        url_group_box.setLayout(url_layout)
        self.main_layout.addWidget(url_group_box)

        self.tabs = QTabWidget(); self.main_layout.addWidget(self.tabs)

        # Active Streams Tab
        self.streams_tab = QWidget(); self.tabs.addTab(self.streams_tab, "Active Streams")
        streams_layout = QVBoxLayout(self.streams_tab)
        self.instances_tree = QTreeWidget(); self.instances_tree.setColumnCount(3) # ID, URL, Title
        self.instances_tree.setHeaderLabels(["ID", "URL", "Stream Title"])
        self.instances_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.instances_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.instances_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        streams_layout.addWidget(self.instances_tree)
        streams_controls_layout = QHBoxLayout()
        self.stop_selected_button = QPushButton("Stop Selected"); self.stop_selected_button.clicked.connect(self.stop_selected_instance_handler); streams_controls_layout.addWidget(self.stop_selected_button)
        self.stop_all_button = QPushButton("Stop All"); self.stop_all_button.clicked.connect(self.stop_all_instances_handler); streams_controls_layout.addWidget(self.stop_all_button)
        streams_layout.addLayout(streams_controls_layout)

        # Queue Tab
        self.queue_tab = QWidget(); self.tabs.addTab(self.queue_tab, "Queue")
        queue_layout = QVBoxLayout(self.queue_tab)
        self.queue_tree = QTreeWidget(); self.queue_tree.setColumnCount(2); 
        self.queue_tree.setHeaderLabels(["URL", "Options"])
        self.queue_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.queue_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents) # Options might be long or short
        queue_layout.addWidget(self.queue_tree)
        queue_controls_layout = QHBoxLayout()
        self.start_next_button = QPushButton("Start Next from Queue"); self.start_next_button.clicked.connect(self.start_next_from_queue_handler); queue_controls_layout.addWidget(self.start_next_button)
        self.remove_queue_button = QPushButton("Remove Selected from Queue"); self.remove_queue_button.clicked.connect(self.remove_selected_from_queue_handler); queue_controls_layout.addWidget(self.remove_queue_button)
        queue_layout.addLayout(queue_controls_layout)
        
        # Status Bar
        self.setStatusBar(QLabel("Initializing...")) # QMainWindow has its own status bar

    @Slot()
    def add_url_handler(self):
        url = self.url_entry.text().strip()
        if not url:
            QMessageBox.warning(self, "Input Error", "URL cannot be empty.")
            return
        if not (url.startswith(('http://', 'https://')) and ("youtube.com/" in url or "youtu.be/" in url)):
            QMessageBox.critical(self, "Invalid URL", "Please enter a valid YouTube URL.")
            return

        dialog = StreamOptionsDialog(self, self.current_stream_options)
        if dialog.exec() == QDialog.Accepted:
            selected_options = dialog.get_options()
            self.current_stream_options.update(selected_options) # Update defaults for next time
            if self.controller.add_to_queue(url, options=selected_options):
                self.url_entry.clear()
                self.update_displays()
            else:
                QMessageBox.critical(self, "Error", "Controller failed to add URL to queue.")
        else: # Dialog cancelled
            print("Stream options dialog cancelled.")


    @Slot()
    def load_playlist_handler(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Playlist File", "", "Text files (*.txt);;All files (*.*)")
        if file_path:
            try:
                self.controller.load_playlist(file_path)
                self.update_displays()
                QMessageBox.information(self, "Playlist Loaded", f"Playlist '{os.path.basename(file_path)}' loaded.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load playlist: {e}")

    @Slot()
    def stop_selected_instance_handler(self):
        selected_items = self.instances_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "No active stream selected to stop.")
            return
        instance_id_str = selected_items[0].text(0) # ID is in the first column
        try:
            instance_id = int(instance_id_str)
            if self.controller.stop_instance(instance_id):
                self.update_displays()
            else: # Should be handled by controller's logging, but GUI can show generic
                QMessageBox.information(self, "Stop Instance", f"Attempted to stop instance {instance_id}.")
        except ValueError:
            QMessageBox.critical(self, "Error", f"Invalid instance ID: {instance_id_str}")
            
    @Slot()
    def stop_all_instances_handler(self):
        if not self.controller.instances:
            QMessageBox.information(self, "No Streams", "No active streams to stop.")
            return
        reply = QMessageBox.question(self, "Confirm Stop All", 
                                     "Are you sure you want to stop all active streams?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            print("GUI: User confirmed stop all. Calling controller shutdown.")
            self.controller.shutdown() # This will stop all instances
            self.update_displays()

    @Slot()
    def start_next_from_queue_handler(self):
        if not self.controller.queue:
            QMessageBox.information(self, "Queue Empty", "The queue is empty.")
            return
        if len(self.controller.instances) >= self.controller.settings['max_concurrent']:
            QMessageBox.information(self, "Limit Reached", 
                                    f"Maximum concurrent streams ({self.controller.settings['max_concurrent']}) reached.")
            return
        if self.controller.start_next():
            self.update_displays()
        else:
            QMessageBox.critical(self, "Error", "Failed to start the next stream from queue.")

    @Slot()
    def remove_selected_from_queue_handler(self):
        selected_items = self.queue_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "No item selected from queue to remove.")
            return
        
        # Get the index of the selected item in the tree
        # This assumes single selection mode
        selected_tree_item = selected_items[0]
        # To get the actual queue item, we need its ID. We can store ID in Qt.UserRole
        # For now, we'll find by index in the controller's queue if display matches order.
        # This is fragile if the queue display order can differ from controller.queue.
        # A more robust way: iterate self.controller.queue and match URL, or store ID in QTreeWidgetItem
        
        # Simple approach: iterate and find (less efficient for large queues but okay for now)
        url_to_remove = selected_tree_item.text(0) # Assuming URL is unique enough for this demo
        found_item = None
        for item in self.controller.queue:
            if item["url"] == url_to_remove: # This might not be unique enough for real use
                # A better way: store item['id'] in QTreeWidgetItem data
                # For now, if multiple identical URLs, this removes the first match
                found_item = item 
                break
        
        if found_item:
            self.controller.remove_from_queue(found_item["id"])
            self.update_displays()
        else:
            QMessageBox.critical(self, "Error", f"Could not find item {url_to_remove} in controller's queue for removal.")


    def fetch_pulse_friendly_name(self, device_name_part, device_type="source"):
        cmd = ["pacmd", f"list-{device_type}s"]
        try:
            output = subprocess.check_output(cmd, text=True, timeout=0.5) # Reduced timeout
            in_correct_device_block = False
            for line in output.splitlines():
                line_stripped = line.strip()
                if f"name: <{device_name_part}" in line_stripped:
                    in_correct_device_block = True
                elif in_correct_device_block and "device.description" in line_stripped:
                    return line_stripped.split("=")[1].strip().strip('"')
                elif in_correct_device_block and line_stripped.startswith("name: <"): break
            return f"{device_type.capitalize()} N/A"
        except Exception: # Catchall for timeout, not found, etc.
            return f"{device_type.capitalize()} Error"

    @Slot()
    def update_displays(self):
        print("GUI: Updating displays...")
        self.controller.clean_instances()

        self.instances_tree.clear()
        for instance in self.controller.instances:
            instance_id_str = str(instance["id"])
            url = instance.get("url", "N/A")
            # Simplified: using instance ID as placeholder for complex title fetching for now
            title = f"Stream {instance_id_str} - {url[:30]}..." 
            # The full fetch_pulse_friendly_name logic can be re-added if performance is acceptable
            # or if title is stored better in controller.instances
            
            item = QTreeWidgetItem([instance_id_str, url, title])
            self.instances_tree.addTopLevelItem(item)

        self.queue_tree.clear()
        for i, item_data in enumerate(self.controller.queue):
            url = item_data.get("url", "N/A")
            options = item_data.get("options", {})
            # Format options for display, excluding None values for brevity
            options_str = ", ".join([f"{k}: {v}" for k, v in options.items() if v is not None])
            if not options_str: options_str = "Defaults"
            
            tree_item = QTreeWidgetItem([url, options_str])
            # Store the queue item's ID for easier removal
            tree_item.setData(0, Qt.UserRole, item_data.get("id")) 
            self.queue_tree.addTopLevelItem(tree_item)
            
        status_text = f"Active: {len(self.controller.instances)}/{self.controller.settings['max_concurrent']} | Queue: {len(self.controller.queue)}"
        self.statusBar().showMessage(status_text)

    def closeEvent(self, event):
        print("GUI: Window close event received. Initiating shutdown.")
        if self.timer: self.timer.stop() # Stop timer to prevent updates during/after shutdown
        if self.controller:
            self.controller.shutdown()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = TabyQtGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
