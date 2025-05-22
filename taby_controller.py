#!/usr/bin/env python3

import argparse, os, subprocess, signal, sqlite3, sys, time, re, socket, json
from datetime import datetime

controller_instance = None

class TabyController:
    def __init__(self, args):
        global controller_instance 
        controller_instance = self 

        settings_keys = [
            "script", "rtsp_base_port", "http_base_port", "port_increment", 
            "max_concurrent", "log_dir", "audio_quality",
            "stream_bitrate", "stream_codec", "stream_volume"
        ]
        self.settings = {k: getattr(args, k, None) for k in settings_keys}
        self.settings["db_file"] = ":memory:"
        
        os.makedirs(self.settings["log_dir"], exist_ok=True)
        self.init_db() 
        self.queue = self.load_queue()
        
        if hasattr(args, 'url') and args.url:
            for url_arg in args.url:
                self.add_to_queue(url_arg) 
        
        if hasattr(args, 'playlist') and args.playlist:
            self.load_playlist(args.playlist)
            
        self.instances = self.load_instances() # Will be empty
        self.next_instance_id = 1 # Fresh start
        self.clean_instances()
        self.print_status()
        self._shutting_down = False

    def db_op(self, query, params=(), fetch=False):
        with sqlite3.connect(self.settings["db_file"]) as conn:
            conn.row_factory = sqlite3.Row 
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall() if fetch else (c.lastrowid if query.lstrip().upper().startswith("INSERT") else None)
    
    def init_db(self):
        self.db_op('CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, url TEXT NOT NULL, options TEXT, added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        self.db_op('CREATE TABLE IF NOT EXISTS instances (id INTEGER PRIMARY KEY, url TEXT NOT NULL, rtsp_port INTEGER, http_port INTEGER, sink_name TEXT, source_name TEXT, pid INTEGER, started_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, options TEXT)') # Added options to instances

    def load_queue(self):
        queue_data = []
        for r in self.db_op("SELECT id, url, options FROM queue ORDER BY id", fetch=True):
            item_options = json.loads(r["options"]) if r["options"] else {}
            queue_data.append({"id": r["id"], "url": r["url"], "options": item_options})
        return queue_data
    
    def load_instances(self):
        # For in-memory, this will be empty on start. If we stored options for instances, we'd load them here.
        # For now, change_instance_url will rely on new_options or controller defaults.
        # If we were to persist instance options, this method would load them.
        # For the current task, keeping it simple: instances list is primarily live data.
        # The `instances` table in DB *does* have an options column now, so `start_taby` will save them.
        # This `load_instances` could be enhanced if controller restarts needed to restore running instances' options.
        # But since DB is :memory:, it's a moot point for persistence across controller restarts.
        # It *is* useful for `change_instance_url` to potentially retrieve original options if needed.
        loaded_instances = []
        for r in self.db_op("SELECT id, url, rtsp_port, http_port, sink_name, source_name, pid, options FROM instances", fetch=True):
            instance_options = json.loads(r["options"]) if r["options"] else {}
            loaded_instances.append({
                "id": r["id"], "url": r["url"], "rtsp_port": r["rtsp_port"], 
                "http_port": r["http_port"], "sink_name": r["sink_name"], 
                "source_name": r["source_name"], "pid": r["pid"], "options": instance_options
            })
        return loaded_instances


    def add_to_queue(self, url, options=None):
        if not url.startswith(('http://', 'https://')):
            print(f"Invalid URL format: {url}"); return False
        current_options = options if options else {}
        options_json = json.dumps(current_options)
        queue_id = self.db_op("INSERT INTO queue (url, options) VALUES (?, ?)", (url, options_json))
        if queue_id is not None:
            self.queue.append({"id": queue_id, "url": url, "options": current_options})
            print(f"Added to queue: {url} with options: {current_options}"); return True
        else: print(f"Failed to add to queue: {url}"); return False

    def remove_from_queue(self, queue_id):
        self.db_op("DELETE FROM queue WHERE id = ?", (queue_id,))
        self.queue = [item for item in self.queue if item["id"] != queue_id]
    
    def load_playlist(self, playlist_file):
        try:
            with open(playlist_file, 'r') as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith('#'): self.add_to_queue(url) 
            print(f"Loaded {playlist_file}")
        except FileNotFoundError: print(f"Error: Playlist file not found: {playlist_file}")
        except Exception as e: print(f"Error loading playlist {playlist_file}: {e}")
    
    def check_port_availability(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0
    
    def set_pulseaudio_device_name(self, device_name, description, is_source=False):
        try:
            safe_description = re.sub(r'[^\w\s\-_\.,]', '', description).replace(" ", "_")
            device_type = "source" if is_source else "sink"
            cmd = f"pacmd update-{device_type}-proplist {device_name} device.description={safe_description}"
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e: print(f"PA command failed: {e.stderr or e}"); return False
        except Exception as e: print(f"Error setting device name: {e}"); return False
    
    def start_taby(self, url, instance_id, 
                   volume=None, audio_quality=None, stream_bitrate=None, stream_codec=None,
                   rtsp_port_override=None, http_port_override=None, 
                   sink_name_override=None, source_name_override=None):
        try:
            # Determine ports and names: use overrides if provided, else generate
            rtsp_port = rtsp_port_override if rtsp_port_override is not None else \
                        self.settings["rtsp_base_port"] + (instance_id * self.settings["port_increment"])
            http_port = http_port_override if http_port_override is not None else \
                        self.settings["http_base_port"] + (instance_id * self.settings["port_increment"])
            
            # Check port availability for the determined ports
            if not self.check_port_availability(rtsp_port): # Check specific rtsp_port
                print(f"RTSP port {rtsp_port} is already in use for instance {instance_id}")
                return False
            if not self.check_port_availability(http_port): # Check specific http_port
                print(f"HTTP port {http_port} is already in use for instance {instance_id}")
                return False
                
            sink_name = sink_name_override if sink_name_override else f"ts_sink_{instance_id}"
            source_name = source_name_override if source_name_override else f"TS_Bot_{instance_id}"
            log_file = os.path.join(self.settings["log_dir"], f"taby_{instance_id}_{int(time.time())}.log")
            
            effective_volume = volume if volume is not None else self.settings.get("stream_volume", 100)
            effective_audio_quality = audio_quality if audio_quality else self.settings["audio_quality"]
            effective_bitrate = stream_bitrate if stream_bitrate is not None else self.settings["stream_bitrate"]
            effective_codec = stream_codec if stream_codec else self.settings["stream_codec"]
            
            current_options = { # Store the actual options used for this instance
                "volume": effective_volume, "audio_quality": effective_audio_quality,
                "stream_bitrate": effective_bitrate, "stream_codec": effective_codec
            }
            options_json = json.dumps(current_options)

            print(f"Starting Taby instance {instance_id} for {url} (Ports: RTSP/{rtsp_port}, HTTP/{http_port}, Sink: {sink_name}) with options: {options_json}")
            
            try:
                title = subprocess.check_output(["yt-dlp", "--get-title", url], text=True).strip()
                title = title[:27] + "..." if len(title) > 30 else title
            except Exception as e: print(f"Error getting video title for {url}: {e}"); title = f"Stream {instance_id}"
            
            script_command = [ self.settings["script"], url, "--rtsp-port", str(rtsp_port), "--http-port", str(http_port),
                "--sink-name", sink_name, "--source-name", source_name, "--audio-quality", effective_audio_quality,
                "--stream-bitrate", str(effective_bitrate), "--stream-codec", effective_codec, "--volume", str(effective_volume) ]

            with open(log_file, 'w') as f: process = subprocess.Popen(script_command, stdout=f, stderr=f)
            
            self.db_op("INSERT INTO instances (id, url, rtsp_port, http_port, sink_name, source_name, pid, options) VALUES (?,?,?,?,?,?,?,?)",
                (instance_id, url, rtsp_port, http_port, sink_name, source_name, process.pid, options_json))
            self.instances.append({ "id": instance_id, "url": url, "rtsp_port": rtsp_port, "http_port": http_port,
                "sink_name": sink_name, "source_name": source_name, "pid": process.pid, "options": current_options })
            
            time.sleep(2) # Allow taby.sh to create PulseAudio devices
            self.set_pulseaudio_device_name(sink_name, title)
            self.set_pulseaudio_device_name(f"{sink_name}.monitor", f"Monitor of {title}", True)
            self.set_pulseaudio_device_name(source_name, title, True)
            print(f"Updated PA device names for instance {instance_id} to '{title}'")
            return True
        except FileNotFoundError: print(f"Error: Script '{self.settings['script']}' not found."); return False
        except Exception as e:
            print(f"Error starting instance {instance_id} ({url}): {e}")
            self.db_op("DELETE FROM instances WHERE id = ?", (instance_id,)) # Cleanup DB
            self.instances = [i for i in self.instances if i["id"] != instance_id] # Cleanup list
            return False
    
    def stop_instance(self, instance_id, from_change_url=False): # Added from_change_url
        instance_to_remove = next((i for i in self.instances if i["id"] == instance_id), None)
        if not instance_to_remove: print(f"Instance {instance_id} not found for stopping."); return False
        
        pid = instance_to_remove.get('pid')
        log_msg_prefix = f"Instance {instance_id} (PID: {pid or 'N/A'})"
        
        if pid:
            try:
                print(f"Attempting to stop {log_msg_prefix}...")
                os.kill(pid, signal.SIGTERM)
                print(f"Successfully sent SIGTERM to {log_msg_prefix}.")
            except ProcessLookupError: print(f"{log_msg_prefix} process not found (already stopped/cleaned up).")
            except Exception as e: print(f"Error sending SIGTERM to {log_msg_prefix}: {e}")
        else:
            print(f"{log_msg_prefix} has no PID, cannot send signal.")
            
        # Always remove from DB and self.instances list
        self.db_op("DELETE FROM instances WHERE id = ?", (instance_id,))
        self.instances = [i for i in self.instances if i["id"] != instance_id]
        if not from_change_url: # Avoid double message if called from change_instance_url
             print(f"Instance {instance_id} removed from controller records.")
        return True

    def change_instance_url(self, instance_id, new_url, new_options=None):
        print(f"Attempting to change URL for instance {instance_id} to '{new_url}' with options: {new_options}")
        if not new_url.startswith(('http://', 'https://')):
            print(f"Error: Invalid new URL format: {new_url}"); return False

        original_instance = next((i for i in self.instances if i["id"] == instance_id), None)
        if not original_instance:
            print(f"Error: Instance {instance_id} not found to change URL."); return False

        # Store original identifiers and options
        original_rtsp_port = original_instance["rtsp_port"]
        original_http_port = original_instance["http_port"]
        original_sink_name = original_instance["sink_name"]
        original_source_name = original_instance["source_name"]
        # Use original instance's options as a base, override with new_options
        # This ensures settings like volume, quality etc., are preserved if not specified in new_options
        # The `start_taby` method itself has fallbacks to controller defaults if an option is still None.
        
        # Options priority: new_options > original_instance options > controller defaults (handled by start_taby)
        combined_options = original_instance.get("options", {}).copy() # Start with original
        if new_options:
            combined_options.update(new_options) # Override with any new ones

        print(f"Stopping original instance {instance_id} (URL: {original_instance['url']}) before changing URL...")
        if not self.stop_instance(instance_id, from_change_url=True): # Pass flag to suppress one log message
            print(f"Warning: Failed to cleanly stop original instance {instance_id}, but attempting to start new one.")
        
        print(f"Starting new stream for instance {instance_id} with URL '{new_url}' using original ports/names.")
        
        success = self.start_taby(
            new_url, instance_id, # Same instance_id
            volume=combined_options.get("volume"),
            audio_quality=combined_options.get("audio_quality"),
            stream_bitrate=combined_options.get("stream_bitrate"),
            stream_codec=combined_options.get("stream_codec"),
            rtsp_port_override=original_rtsp_port,
            http_port_override=original_http_port,
            sink_name_override=original_sink_name,
            source_name_override=original_source_name
        )
        if success:
            print(f"Successfully changed URL for instance {instance_id} to '{new_url}'.")
            return True
        else:
            print(f"Error: Failed to start new stream for instance {instance_id} with URL '{new_url}'. The instance might be stopped.")
            # At this point, stop_instance already removed it. If start_taby failed, it's also removed.
            return False

    def change_instance_volume(self, instance_id, new_volume):
        instance = next((i for i in self.instances if i["id"] == instance_id), None)
        if not instance: print(f"Error: Instance ID {instance_id} not found."); return False
        sink_name = instance.get("sink_name")
        if not sink_name: print(f"Error: Sink name for instance ID {instance_id} not found."); return False
        try:
            new_volume = int(new_volume)
            if not (0 <= new_volume <= 150): raise ValueError("Volume: 0-150.")
        except ValueError as e: print(f"Error: Invalid volume '{new_volume}'. {e}"); return False
        cmd = ["pactl", "set-sink-volume", sink_name, f"{new_volume}%"]
        try:
            print(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Volume for {instance_id} (sink: {sink_name}) changed to {new_volume}%. Output: {result.stdout.strip()}")
            # Update the stored options for this live instance
            if "options" not in instance: instance["options"] = {}
            instance["options"]["volume"] = new_volume 
            # Update the instance in the database (instances table)
            self.db_op("UPDATE instances SET options = ? WHERE id = ?", (json.dumps(instance["options"]), instance_id))
            return True
        except FileNotFoundError: print(f"Error: 'pactl' not found."); return False
        except subprocess.CalledProcessError as e: print(f"Error changing volume for {sink_name}: {e.stderr}"); return False
        except Exception as e: print(f"Unexpected error changing volume: {e}"); return False

    def clean_instances(self):
        for instance in list(self.instances):
            pid = instance.get('pid', 'N/A')
            try: os.kill(instance["pid"], 0) 
            except ProcessLookupError:
                print(f"Cleaning dead instance {instance['id']} (PID: {pid}).")
                self.db_op("DELETE FROM instances WHERE id = ?", (instance["id"],))
                self.instances = [i for i in self.instances if i["id"] != instance["id"]]
            except Exception as e: print(f"Error checking instance {instance['id']} (PID: {pid}): {e}.")
    
    def start_next(self):
        if not self.queue: print("Queue empty"); return False
        if len(self.instances) >= self.settings["max_concurrent"]:
            print(f"Max instances ({self.settings['max_concurrent']}) reached"); return False
        next_item = self.queue[0]
        opts = next_item.get("options", {})
        if self.start_taby(next_item["url"], self.next_instance_id, volume=opts.get("volume"), 
                           audio_quality=opts.get("audio_quality"), stream_bitrate=opts.get("stream_bitrate"), 
                           stream_codec=opts.get("stream_codec")): 
            self.next_instance_id += 1; self.remove_from_queue(next_item["id"]); return True
        return False

    def shutdown(self):
        if self._shutting_down: print("Shutdown in progress."); return
        self._shutting_down = True; print("\nShutting down, stopping all instances...")
        for instance in list(self.instances): self.stop_instance(instance["id"])
        print("All instances processed. Controller shut down.")

    def print_status(self): print(f"\n=== Status ===\nActive: {len(self.instances)}/{self.settings['max_concurrent']} | Queue: {len(self.queue)}\n")
    def list_instances(self):
        if not self.instances: print("No active instances"); return
        print("\n=== Active Instances ===")
        for i in self.instances: 
            opts_str = json.dumps(i.get("options", {}))
            print(f"ID: {i['id']} URL: {i['url']} RTSP: {i['rtsp_port']} HTTP: {i['http_port']} PID: {i['pid']} Sink: {i['sink_name']} Opts: {opts_str}")
    def show_queue(self):
        if not self.queue: print("\n=== Queue ===\nEmpty\n"); return
        print("\n=== Queue ===")
        for i, item in enumerate(self.queue):
            opts_str = json.dumps(item.get('options',{}))
            print(f"{i+1}. {item['url']}" + (f" (Options: {opts_str})" if opts_str !="{}" else ""))
        print("")

    def interactive_mode(self):
        print("Taby Controller Interactive Mode. Type 'help'.")
        help_text = ("\nCommands:\n"
                     "  list                      - Show active instances\n"
                     "  queue                     - Show the current media queue\n"
                     "  add <URL> [options_json]  - Add URL (e.g. {\"volume\":80})\n"
                     "  setvol <ID> <VOL>         - Change volume of instance (0-150)\n"
                     "  changeurl <ID> <URL> [opts_json] - Change URL of instance\n"
                     "  clean                     - Remove dead instances\n"
                     "  stop <ID>                 - Stop a specific instance\n"
                     "  stop-all                  - Stop all active instances\n"
                     "  start-next                - Start next from queue\n"
                     "  exit/quit                 - Exit\n"
                     "  help                      - Show this help\n")
        cmds = { "list": self.list_instances, "queue": self.show_queue, "clean": self.clean_instances, 
                   "start-next": self.start_next, "help": lambda: print(help_text) }
        try:
            while True:
                try:
                    cmd_input = input("> ").strip()
                    if not cmd_input: continue
                    parts = cmd_input.split(" ", 3); cmd = parts[0] # Max 3 splits for changeurl
                    if cmd in ["exit", "quit"]: print("Exiting..."); break
                    if cmd in cmds:
                        if cmd == "add" and len(parts) > 1:
                            opts = None; url_to_add = parts[1]
                            if len(parts) > 2:
                                try: opts = json.loads(parts[2])
                                except json.JSONDecodeError: print(f"Invalid JSON: {parts[2]}"); continue
                            self.add_to_queue(url_to_add, opts)
                        elif cmd == "add": print("Usage: add <URL> [options_json]")
                        else: cmds[cmd]()
                    elif cmd == "stop":
                        if len(parts) > 1:
                            try: self.stop_instance(int(parts[1]))
                            except ValueError: print(f"Invalid ID: {parts[1]}")
                        else: print("Usage: stop <ID>")
                    elif cmd == "stop-all":
                        print("Stopping all instances..."); 
                        for i in list(self.instances): self.stop_instance(i["id"])
                        print("All instances commanded to stop.")
                    elif cmd == "setvol":
                        if len(parts) == 3:
                            try: self.change_instance_volume(int(parts[1]), int(parts[2]))
                            except ValueError: print("ID and Volume must be integers.")
                        else: print("Usage: setvol <ID> <VOLUME>")
                    elif cmd == "changeurl":
                        if len(parts) >= 3:
                            opts = None; new_url = parts[2]
                            if len(parts) > 3: # options_json provided
                                try: opts = json.loads(parts[3])
                                except json.JSONDecodeError: print(f"Invalid JSON options: {parts[3]}"); continue
                            try: self.change_instance_url(int(parts[1]), new_url, opts)
                            except ValueError: print("Instance ID must be an integer.")
                        else: print("Usage: changeurl <ID> <NEW_URL> [options_json]")
                    else: print(f"Unknown command: '{cmd}'. Type 'help'.")
                except KeyboardInterrupt: print("\nCtrl+C. Type 'exit' or use Ctrl+C again."); continue
                except Exception as e: print(f"Error in loop: {e}")
        finally:
            self.shutdown() 

def signal_handler(sig, frame):
    print(f"\nSignal {signal.Signals(sig).name} received.")
    if controller_instance: controller_instance.shutdown()
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    parser = argparse.ArgumentParser(description="Taby Controller")
    parser.add_argument("-p", "--playlist", help="Load playlist file")
    parser.add_argument("-u", "--url", action="append", help="Add URL to queue")
    parser.add_argument("-s", "--script", default="./taby.sh", help="Path to taby.sh")
    parser.add_argument("-l", "--list", action="store_true", help="List and exit")
    parser.add_argument("--rtsp-base-port", type=int, default=8554)
    parser.add_argument("--http-base-port", type=int, default=8080)
    parser.add_argument("--port-increment", type=int, default=10)
    parser.add_argument("--max-concurrent", type=int, default=5)
    parser.add_argument("--log-dir", default="/tmp/taby-controller-logs")
    parser.add_argument("--audio-quality", default="bestaudio")
    parser.add_argument("--stream-bitrate", type=int, default=128)
    parser.add_argument("--stream-codec", default="mp3", choices=['mp3','opus','vorb','flac'])
    parser.add_argument("--stream-volume", type=int, default=100)
    
    args = parser.parse_args()
    controller = TabyController(args)
    
    if args.list: controller.list_instances(); controller.show_queue(); return
    
    active_count = len(controller.instances)
    while active_count < controller.settings["max_concurrent"] and controller.queue:
        if not controller.start_next(): print("Could not start initial item."); break 
        active_count = len(controller.instances)
    
    controller.interactive_mode()

if __name__ == "__main__":
    main()
