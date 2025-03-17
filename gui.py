#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import os
import sys
import subprocess
import socket

# Import the TabyController from taby_controller.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from taby_controller import TabyController

class TabyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Taby - TeamSpeak YouTube Streamer")
        self.root.geometry("900x500")  # Increased width to accommodate more columns
        
        # Initialize controller with minimal default settings
        self.controller = TabyController(self.get_default_args())
        
        self.setup_ui()
        self.update_displays()
        self.root.after(5000, self.schedule_updates)
    
    def get_default_args(self):
        # Create a simple object with default attributes
        class Args:
            def __init__(self):
                self.script = "./taby.sh"
                self.rtsp_base_port = 8554
                self.http_base_port = 8080
                self.port_increment = 10
                self.max_concurrent = 5
                self.log_dir = "/tmp/taby-controller-logs"
                self.db_file = "/tmp/taby-controller.db"
                self.audio_quality = "bestaudio"
                self.stream_bitrate = 128
                self.stream_codec = "mp3"
                self.url = None
                self.playlist = None
        return Args()
    
    def setup_ui(self):
        # Main frame with padding
        frame = ttk.Frame(self.root, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # URL entry and buttons
        url_frame = ttk.Frame(frame)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(url_frame, text="YouTube URL:").pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(url_frame, width=40)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(url_frame, text="Add", command=self.add_url).pack(side=tk.LEFT, padx=2)
        ttk.Button(url_frame, text="Playlist", command=self.load_playlist).pack(side=tk.LEFT, padx=2)
        ttk.Button(url_frame, text="Refresh", command=self.update_displays).pack(side=tk.LEFT, padx=2)
        
        # Notebook with tabs
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Instances tab
        instances_frame = ttk.Frame(notebook)
        notebook.add(instances_frame, text="Active Streams")
        
        # Instances list with additional columns for sink and monitor
        columns = ("id", "url", "source", "sink", "monitor", "friendly_name")
        self.instances_tree = ttk.Treeview(instances_frame, columns=columns, show="headings")
        
        self.instances_tree.heading("id", text="ID")
        self.instances_tree.heading("url", text="YouTube URL")
        self.instances_tree.heading("source", text="Source Name")
        self.instances_tree.heading("sink", text="Sink Name")
        self.instances_tree.heading("monitor", text="Monitor Name")
        self.instances_tree.heading("friendly_name", text="Stream Title")
        
        self.instances_tree.column("id", width=40)
        self.instances_tree.column("url", width=250)
        self.instances_tree.column("source", width=120)
        self.instances_tree.column("sink", width=120)
        self.instances_tree.column("monitor", width=120)
        self.instances_tree.column("friendly_name", width=200)
        
        scrollbar = ttk.Scrollbar(instances_frame, orient=tk.VERTICAL, command=self.instances_tree.yview)
        self.instances_tree.configure(yscroll=scrollbar.set)
        
        self.instances_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Instance control buttons
        btn_frame = ttk.Frame(instances_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Stop Selected", command=self.stop_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop All", command=self.stop_all).pack(side=tk.LEFT, padx=5)
        
        # Queue tab
        queue_frame = ttk.Frame(notebook)
        notebook.add(queue_frame, text="Queue")
        
        self.queue_listbox = tk.Listbox(queue_frame)
        queue_scrollbar = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_listbox.yview)
        self.queue_listbox.configure(yscroll=queue_scrollbar.set)
        
        self.queue_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        queue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        queue_btn_frame = ttk.Frame(queue_frame)
        queue_btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(queue_btn_frame, text="Start Next", command=self.start_next).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_btn_frame, text="Remove", command=self.remove_from_queue).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))
    
    def check_port_availability(self, port):
        """Check if a port is available for use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0
    
    def add_url(self):
        url = self.url_entry.get().strip()
        if not url:
            return
            
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            messagebox.showerror("Invalid URL", "Please enter a valid YouTube URL starting with http:// or https://")
            return
            
        # Simple dialog for stream options
        options = self.show_options_dialog()
        if options:
            if self.controller.add_to_queue(url):
                self.url_entry.delete(0, tk.END)
                self.update_displays()
            else:
                messagebox.showerror("Error", "Failed to add URL to queue")
    
    def show_options_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Stream Options")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Audio Quality:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        quality = ttk.Combobox(dialog, values=["bestaudio", "bestaudio[ext=m4a]", "worstaudio"])
        quality.current(0)
        quality.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="Stream Codec:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        codec = ttk.Combobox(dialog, values=["mp3", "opus", "vorb", "flac"])
        codec.current(0)
        codec.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(dialog, text="Bitrate (kbps):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        bitrate = ttk.Spinbox(dialog, from_=64, to=320, increment=32)
        bitrate.insert(0, "128")
        bitrate.grid(row=2, column=1, padx=5, pady=5)
        
        result = {"confirmed": False}
        
        def on_ok():
            try:
                # Validate bitrate is a number
                bitrate_val = int(bitrate.get())
                if bitrate_val < 64 or bitrate_val > 320:
                    messagebox.showerror("Invalid Bitrate", "Bitrate must be between 64 and 320 kbps")
                    return
                
                self.controller.settings["audio_quality"] = quality.get()
                self.controller.settings["stream_codec"] = codec.get()
                self.controller.settings["stream_bitrate"] = bitrate_val
                result["confirmed"] = True
                dialog.destroy()
            except ValueError:
                messagebox.showerror("Invalid Bitrate", "Bitrate must be a number")
        
        def on_cancel():
            dialog.destroy()
        
        ttk.Button(dialog, text="OK", command=on_ok).grid(row=3, column=0, padx=5, pady=10)
        ttk.Button(dialog, text="Cancel", command=on_cancel).grid(row=3, column=1, padx=5, pady=10)
        
        self.root.wait_window(dialog)
        return result["confirmed"]
    
    def load_playlist(self):
        playlist_file = filedialog.askopenfilename(
            title="Select Playlist File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if playlist_file:
            try:
                # Use a safe approach for Linux
                self.root.config(cursor="")
                self.update_displays()
                self.controller.load_playlist(playlist_file)
                self.update_displays()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load playlist: {str(e)}")
            finally:
                self.root.config(cursor="")
    
    def stop_selected(self):
        selected = self.instances_tree.selection()
        if selected:
            instance_id = int(self.instances_tree.item(selected[0])['values'][0])
            if self.controller.stop_instance(instance_id):
                self.update_displays()
            else:
                messagebox.showerror("Error", f"Failed to stop instance {instance_id}")
    
    def stop_all(self):
        if messagebox.askyesno("Confirm", "Are you sure you want to stop all streams?"):
            for instance in list(self.controller.instances):
                self.controller.stop_instance(instance["id"])
            self.update_displays()
    
    def start_next(self):
        if not self.controller.queue:
            messagebox.showinfo("Queue Empty", "There are no items in the queue")
            return
            
        if len(self.controller.instances) >= self.controller.settings["max_concurrent"]:
            messagebox.showinfo("Maximum Instances", 
                               f"Maximum number of concurrent instances ({self.controller.settings['max_concurrent']}) reached")
            return
            
        try:
            # Fix for the controller bug - temporary workaround
            if len(self.controller.queue) > 0:
                next_item = self.controller.queue[0]
                if self.controller.start_taby(next_item["url"], self.controller.next_instance_id):
                    self.controller.next_instance_id += 1
                    self.controller.remove_from_queue(next_item["id"])
                    self.update_displays()
                else:
                    messagebox.showerror("Error", "Failed to start stream")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start next item: {str(e)}")
    
    def remove_from_queue(self):
        selected = self.queue_listbox.curselection()
        if selected:
            queue_id = self.controller.queue[selected[0]]["id"]
            self.controller.remove_from_queue(queue_id)
            self.update_displays()
    
    def update_displays(self):
        self.controller.clean_instances()
        
        # Update instances
        for item in self.instances_tree.get_children():
            self.instances_tree.delete(item)
        
        for instance in self.controller.instances:
            # Get the monitor name by appending .monitor to sink_name
            monitor_name = f"{instance['sink_name']}.monitor"
            
            # Get the friendly name from logs or use a default
            friendly_name = "Unknown"
            try:
                # Try to get the friendly name by running pacmd list-sources and parsing output
                output = subprocess.check_output(["pacmd", "list-sources"], text=True)
                for line in output.splitlines():
                    if line.strip().startswith("name:") and f"<{instance['source_name']}>" in line:
                        # Found the source, now look for device.description
                        source_section = output[output.find(line):]
                        for prop_line in source_section.splitlines():
                            if "device.description" in prop_line:
                                friendly_name = prop_line.split("=")[1].strip().strip('"')
                                break
                        break
            except Exception as e:
                # If we can't get the friendly name, use a fallback
                friendly_name = f"Stream {instance['id']}"
            
            self.instances_tree.insert("", tk.END, values=(
                instance["id"],
                instance["url"],
                friendly_name,  # Use friendly name instead of source_name
                friendly_name,  # Use friendly name instead of sink_name
                friendly_name,  # Use friendly name instead of monitor_name
                friendly_name   # Add friendly name as a separate column
            ))
        
        # Update queue
        self.queue_listbox.delete(0, tk.END)
        for item in self.controller.queue:
            self.queue_listbox.insert(tk.END, item["url"])
        
        # Update status
        self.status_var.set(
            f"Active: {len(self.controller.instances)}/{self.controller.settings['max_concurrent']} | "
            f"Queue: {len(self.controller.queue)}"
        )
    
    def schedule_updates(self):
        self.update_displays()
        self.root.after(5000, self.schedule_updates)

def main():
    root = tk.Tk()
    app = TabyGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
