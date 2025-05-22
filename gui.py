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
        self.root.geometry("900x500")
        
        # Instantiate the controller
        # The controller's __init__ now sets up the global instance for signal handling
        # and also handles its own signal registration if run as main.
        self.controller = TabyController(self.get_default_args())
        
        # Initialize default stream options for the dialog
        self.current_stream_options = {
            "volume": self.controller.settings.get("stream_volume", 100),
            "audio_quality": self.controller.settings.get("audio_quality", "bestaudio"),
            "stream_codec": self.controller.settings.get("stream_codec", "mp3"),
            "stream_bitrate": self.controller.settings.get("stream_bitrate", 128)
        }
        
        self.setup_ui()
        self.update_displays()
        
        # Register the on_close method for the window's close button
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Start periodic updates
        self.root.after(5000, self.schedule_updates)
    
    def get_default_args(self):
        # Helper to create a Namespace object similar to what argparse produces
        class Args:
            pass
        args = Args()
        args.script = "./taby.sh"
        args.rtsp_base_port = 8554
        args.http_base_port = 8080
        args.port_increment = 10
        args.max_concurrent = 5
        args.log_dir = "/tmp/taby-controller-logs"
        # db_file is not needed here as controller forces :memory:
        args.audio_quality = "bestaudio" 
        args.stream_bitrate = 128
        args.stream_codec = "mp3"
        args.stream_volume = 100 
        args.url = None # No initial URLs from CLI for GUI mode
        args.playlist = None # No initial playlist from CLI for GUI mode
        args.list = False # Not listing and exiting
        return args
    
    def on_close(self):
        """Handles the GUI window close event."""
        print("GUI: Close button clicked. Shutting down controller...")
        if self.controller:
            self.controller.shutdown() # Call the controller's shutdown method
        print("GUI: Controller shutdown initiated. Destroying window.")
        self.root.destroy()

    def setup_ui(self):
        frame = ttk.Frame(self.root, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        url_frame = ttk.Frame(frame)
        url_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(url_frame, text="YouTube URL:").pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(url_frame, width=40)
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(url_frame, text="Add URL", command=self.add_url).pack(side=tk.LEFT, padx=2)
        ttk.Button(url_frame, text="Load Playlist", command=self.load_playlist).pack(side=tk.LEFT, padx=2)
        ttk.Button(url_frame, text="Refresh All", command=self.update_displays).pack(side=tk.LEFT, padx=2)
        
        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        instances_frame = ttk.Frame(notebook)
        notebook.add(instances_frame, text="Active Streams")
        
        columns = ("id", "url", "friendly_name")
        self.instances_tree = ttk.Treeview(instances_frame, columns=columns, show="headings")
        self.instances_tree.heading("id", text="ID"); self.instances_tree.column("id", width=40, stretch=tk.NO)
        self.instances_tree.heading("url", text="YouTube URL"); self.instances_tree.column("url", width=350)
        self.instances_tree.heading("friendly_name", text="Stream Title"); self.instances_tree.column("friendly_name", width=300)
        
        scrollbar = ttk.Scrollbar(instances_frame, orient=tk.VERTICAL, command=self.instances_tree.yview)
        self.instances_tree.configure(yscroll=scrollbar.set)
        self.instances_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        btn_frame = ttk.Frame(instances_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Stop Selected", command=self.stop_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop All", command=self.stop_all).pack(side=tk.LEFT, padx=5)
        
        queue_frame = ttk.Frame(notebook)
        notebook.add(queue_frame, text="Queue")
        
        self.queue_tree = ttk.Treeview(queue_frame, columns=("url", "options"), show="headings")
        self.queue_tree.heading("url", text="URL"); self.queue_tree.column("url", width=400)
        self.queue_tree.heading("options", text="Options"); self.queue_tree.column("options", width=300)
        
        queue_scrollbar_tree = ttk.Scrollbar(queue_frame, orient=tk.VERTICAL, command=self.queue_tree.yview)
        self.queue_tree.configure(yscroll=queue_scrollbar_tree.set)
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        queue_scrollbar_tree.pack(side=tk.RIGHT, fill=tk.Y)

        queue_btn_frame = ttk.Frame(queue_frame)
        queue_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(queue_btn_frame, text="Start Next", command=self.start_next_from_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_btn_frame, text="Remove Selected", command=self.remove_from_queue).pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, pady=(5, 0))
    
    def add_url(self):
        url = self.url_entry.get().strip()
        if not url: messagebox.showwarning("Input Error", "URL cannot be empty."); return
        if not (url.startswith(('http://', 'https://')) and ("youtube.com/" in url or "youtu.be/" in url)):
            messagebox.showerror("Invalid URL", "Please enter a valid YouTube URL."); return
            
        dialog_options = self.show_options_dialog()
        if dialog_options:
            if self.controller.add_to_queue(url, options=dialog_options):
                self.url_entry.delete(0, tk.END); self.update_displays()
            else: messagebox.showerror("Error", "Failed to add URL to queue (controller error).")
    
    def show_options_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Stream Options"); dialog.geometry("350x250"); dialog.transient(self.root); dialog.grab_set()
        
        quality_var = tk.StringVar(value=self.current_stream_options.get("audio_quality", "bestaudio"))
        codec_var = tk.StringVar(value=self.current_stream_options.get("stream_codec", "mp3"))
        bitrate_var = tk.IntVar(value=self.current_stream_options.get("stream_bitrate", 128))
        volume_var = tk.IntVar(value=self.current_stream_options.get("volume", 100))

        ttk.Label(dialog, text="Audio Quality:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Combobox(dialog, textvariable=quality_var, values=["bestaudio", "bestaudio[ext=m4a]", "worstaudio"]).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Stream Codec:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Combobox(dialog, textvariable=codec_var, values=["mp3", "opus", "vorb", "flac"]).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Bitrate (kbps):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Spinbox(dialog, from_=64, to=320, increment=32, textvariable=bitrate_var, width=17).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(dialog, text="Volume (%):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Spinbox(dialog, from_=0, to=150, increment=10, textvariable=volume_var, width=17).grid(row=3, column=1, padx=5, pady=5)
        
        dialog_result = {"options": None} 
        def on_ok():
            try:
                br_val, vol_val = bitrate_var.get(), volume_var.get()
                if not (64 <= br_val <= 320): messagebox.showerror("Invalid Bitrate", "Bitrate: 64-320 kbps.", parent=dialog); return
                if not (0 <= vol_val <= 150): messagebox.showerror("Invalid Volume", "Volume: 0-150%.", parent=dialog); return
                
                self.current_stream_options.update({ "audio_quality": quality_var.get(), "stream_codec": codec_var.get(),
                                                    "stream_bitrate": br_val, "volume": vol_val })
                dialog_result["options"] = self.current_stream_options.copy()
                dialog.destroy()
            except tk.TclError: messagebox.showerror("Input Error", "Bitrate/Volume must be numbers.", parent=dialog)
            except Exception as e: messagebox.showerror("Error", f"Unexpected error: {e}", parent=dialog)

        button_frame = ttk.Frame(dialog)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        self.root.wait_window(dialog)
        return dialog_result["options"]
    
    def load_playlist(self):
        playlist_file = filedialog.askopenfilename(title="Select Playlist", filetypes=[("Text files", "*.txt"), ("All", "*.*")])
        if playlist_file:
            try: self.controller.load_playlist(playlist_file); self.update_displays(); messagebox.showinfo("Playlist Loaded", "Playlist loaded.")
            except Exception as e: messagebox.showerror("Error", f"Failed to load playlist: {e}")
    
    def stop_selected(self):
        sel = self.instances_tree.selection()
        if not sel: messagebox.showwarning("Selection Error", "No stream selected."); return
        try:
            instance_id = int(self.instances_tree.item(sel[0])['values'][0])
            if self.controller.stop_instance(instance_id): self.update_displays()
            else: messagebox.showerror("Error", f"Controller failed to stop instance {instance_id}.")
        except (ValueError, IndexError): messagebox.showerror("Internal Error", "Invalid instance data.")

    def stop_all(self):
        if not self.controller.instances: messagebox.showinfo("No Streams", "No active streams."); return
        if messagebox.askyesno("Confirm", "Stop all streams?"):
            for instance in list(self.controller.instances): self.controller.stop_instance(instance["id"])
            self.update_displays()
    
    def start_next_from_queue(self):
        if not self.controller.queue: messagebox.showinfo("Queue Empty", "Queue is empty."); return
        if len(self.controller.instances) >= self.controller.settings["max_concurrent"]:
            messagebox.showinfo("Limit Reached", f"Max streams ({self.controller.settings['max_concurrent']}) active."); return
        if self.controller.start_next(): self.update_displays()
        else: messagebox.showerror("Error", "Failed to start next stream (see controller logs).")
    
    def remove_from_queue(self):
        sel = self.queue_tree.selection()
        if not sel: messagebox.showwarning("Selection Error", "No item selected from queue."); return
        selected_index = self.queue_tree.index(sel[0])
        if 0 <= selected_index < len(self.controller.queue):
            self.controller.remove_from_queue(self.controller.queue[selected_index]["id"])
            self.update_displays()
        else: messagebox.showerror("Internal Error", "Selected index out of range.")

    def update_displays(self):
        self.controller.clean_instances()
        for item in self.instances_tree.get_children(): self.instances_tree.delete(item)
        for instance in self.controller.instances:
            # Simplified display for now; actual title fetching can be complex
            friendly_name = f"Stream {instance['id']} ({instance['url'][:30]}...)" 
            self.instances_tree.insert("", tk.END, values=(instance["id"], instance["url"], friendly_name))
        
        for item in self.queue_tree.get_children(): self.queue_tree.delete(item)
        for item in self.controller.queue:
            options = item.get("options", {})
            options_str = ", ".join([f"{k}: {v}" for k, v in options.items() if v is not None])
            self.queue_tree.insert("", tk.END, values=(item["url"], options_str if options_str else "Defaults"))
            
        self.status_var.set(f"Active: {len(self.controller.instances)}/{self.controller.settings['max_concurrent']} | Queue: {len(self.controller.queue)}")
    
    def schedule_updates(self):
        try: self.update_displays()
        except Exception as e: print(f"Error in GUI scheduled update: {e}")
        finally: self.root.after(5000, self.schedule_updates) # Reschedule

def main():
    root = tk.Tk()
    app = TabyGUI(root)
    # Signal handling for SIGINT/SIGTERM should be managed by taby_controller.py if it's run as main.
    # If gui.py is the main entry point, and controller is just a library,
    # then gui.py might also need to think about signals if controller doesn't set them up globally.
    # However, the controller's __init__ now sets the global controller_instance,
    # and its main() sets up signal handlers. If gui.py is the entry, it should ensure
    # controller's main() logic for signals is effectively active or replicated if necessary.
    # For now, relying on WM_DELETE_WINDOW for GUI-initiated shutdown.
    root.mainloop()

if __name__ == "__main__":
    main()
