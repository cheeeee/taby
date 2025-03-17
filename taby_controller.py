#!/usr/bin/env python3

import argparse, os, subprocess, signal, sqlite3, sys, time, re, socket
from datetime import datetime

class TabyController:
    def __init__(self, args):
        self.settings = {k: getattr(args, k, None) for k in ["script", "rtsp_base_port", "http_base_port", 
            "port_increment", "max_concurrent", "log_dir", "db_file", "audio_quality", 
            "stream_bitrate", "stream_codec"]}
        
        os.makedirs(self.settings["log_dir"], exist_ok=True)
        self.init_db()
        self.queue = self.load_queue()
        
        if hasattr(args, 'url') and args.url:
            for url in args.url:
                self.add_to_queue(url)
        
        if hasattr(args, 'playlist') and args.playlist:
            self.load_playlist(args.playlist)
            
        self.instances = self.load_instances()
        self.next_instance_id = max([i["id"] for i in self.instances], default=0) + 1
        self.clean_instances()
        self.print_status()
    
    def db_op(self, query, params=(), fetch=False):
        with sqlite3.connect(self.settings["db_file"]) as conn:
            c = conn.cursor()
            c.execute(query, params)
            return c.fetchall() if fetch else (c.lastrowid if query.lstrip().upper().startswith("INSERT") else None)
    
    def init_db(self):
        self.db_op('CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, url TEXT NOT NULL, added_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        self.db_op('CREATE TABLE IF NOT EXISTS instances (id INTEGER PRIMARY KEY, url TEXT NOT NULL, rtsp_port INTEGER, http_port INTEGER, sink_name TEXT, source_name TEXT, pid INTEGER, started_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    
    def load_queue(self):
        return [{"id": r[0], "url": r[1]} for r in self.db_op("SELECT id, url FROM queue ORDER BY id", fetch=True)]
    
    def load_instances(self):
        return [{"id": r[0], "url": r[1], "rtsp_port": r[2], "http_port": r[3], "sink_name": r[4], "source_name": r[5], "pid": r[6]} 
                for r in self.db_op("SELECT id, url, rtsp_port, http_port, sink_name, source_name, pid FROM instances", fetch=True)]
    
    def add_to_queue(self, url):
        if not url.startswith(('http://', 'https://')):
            print(f"Invalid URL format: {url}")
            return False
            
        queue_id = self.db_op("INSERT INTO queue (url) VALUES (?)", (url,))
        self.queue.append({"id": queue_id, "url": url})
        print(f"Added to queue: {url}")
        return True
    
    def remove_from_queue(self, queue_id):
        self.db_op("DELETE FROM queue WHERE id = ?", (queue_id,))
        self.queue = [item for item in self.queue if item["id"] != queue_id]
    
    def load_playlist(self, playlist_file):
        try:
            with open(playlist_file, 'r') as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith('#'):
                        self.add_to_queue(url)
            print(f"Loaded {playlist_file}")
        except Exception as e:
            print(f"Error loading playlist: {e}")
    
    def check_port_availability(self, port):
        """Check if a port is available for use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0
    
    def set_pulseaudio_device_name(self, device_name, description, is_source=False):
        try:
            # Create a safe description for PulseAudio
            safe_description = re.sub(r'[^\w\s\-_\.,]', '', description).replace(" ", "_")
            
            # Create the command with proper quoting
            device_type = "source" if is_source else "sink"
            cmd = f"pacmd update-{device_type}-proplist {device_name} device.description={safe_description}"
            
            # Execute the command
            subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"PulseAudio command failed: {e.stderr if hasattr(e, 'stderr') else str(e)}")
            return False
        except Exception as e:
            print(f"Error setting device name: {e}")
            return False
    
    def start_taby(self, url, instance_id):
        try:
            rtsp_port = self.settings["rtsp_base_port"] + (instance_id * self.settings["port_increment"])
            http_port = self.settings["http_base_port"] + (instance_id * self.settings["port_increment"])
            
            # Check port availability
            if not self.check_port_availability(rtsp_port):
                print(f"RTSP port {rtsp_port} is already in use")
                return False
            if not self.check_port_availability(http_port):
                print(f"HTTP port {http_port} is already in use")
                return False
                
            sink_name = f"ts_sink_{instance_id}"
            source_name = f"TS_Bot_{instance_id}"
            log_file = os.path.join(self.settings["log_dir"], f"taby_{instance_id}_{int(time.time())}.log")
            
            print(f"Starting Taby instance {instance_id} for {url}")
            
            # Get video title first
            try:
                title = subprocess.check_output(["yt-dlp", "--get-title", url], text=True).strip()
                if len(title) > 30:
                    title = title[:27] + "..."
            except Exception as e:
                print(f"Error getting video title: {e}")
                title = f"YouTube Stream {instance_id}"
            
            with open(log_file, 'w') as f:
                process = subprocess.Popen([
                    self.settings["script"], url,
                    "--rtsp-port", str(rtsp_port),
                    "--http-port", str(http_port),
                    "--sink-name", sink_name,
                    "--source-name", source_name,
                    "--audio-quality", self.settings["audio_quality"],
                    "--stream-bitrate", str(self.settings["stream_bitrate"]),
                    "--stream-codec", self.settings["stream_codec"]
                ], stdout=f, stderr=f)
            
            self.db_op("INSERT INTO instances VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (instance_id, url, rtsp_port, http_port, sink_name, source_name, process.pid))
            
            self.instances.append({
                "id": instance_id, "url": url, "rtsp_port": rtsp_port, "http_port": http_port,
                "sink_name": sink_name, "source_name": source_name, "pid": process.pid
            })
            
            # Update PulseAudio device descriptions with video title
            time.sleep(2)  # Wait for PulseAudio to create the devices
            try:
                self.set_pulseaudio_device_name(sink_name, title)
                self.set_pulseaudio_device_name(f"{sink_name}.monitor", f"Monitor of {title}", True)
                self.set_pulseaudio_device_name(source_name, title, True)
                print(f"Updated device names to: {title}")
            except Exception as e:
                print(f"Error updating device names: {e}")
            
            return True
        except Exception as e:
            print(f"Error starting instance: {e}")
            return False
    
    def stop_instance(self, instance_id):
        instance = next((i for i in self.instances if i["id"] == instance_id), None)
        if not instance:
            print(f"Instance {instance_id} not found")
            return False
        
        try:
            os.kill(instance["pid"], signal.SIGTERM)
            print(f"Stopped instance {instance_id}")
        except ProcessLookupError:
            print(f"Process for instance {instance_id} not found, cleaning up")
        except Exception as e:
            print(f"Error stopping instance {instance_id}: {e}")
            return False
            
        self.db_op("DELETE FROM instances WHERE id = ?", (instance_id,))
        self.instances = [i for i in self.instances if i["id"] != instance_id]
        return True
    
    def clean_instances(self):
        for instance in list(self.instances):
            try:
                os.kill(instance["pid"], 0)
            except ProcessLookupError:
                print(f"Cleaning up dead instance {instance['id']}")
                self.db_op("DELETE FROM instances WHERE id = ?", (instance["id"],))
                self.instances = [i for i in self.instances if i["id"] != instance["id"]]
            except Exception as e:
                print(f"Error checking instance {instance['id']}: {e}")
    
    def start_next(self):
        if not self.queue:
            print("Queue is empty")
            return False
        
        if len(self.instances) >= self.settings["max_concurrent"]:
            print(f"Maximum number of concurrent instances ({self.settings['max_concurrent']}) reached")
            return False
        
        # Fixed critical bug: Get the first item from the queue instead of the entire queue
        next_item = self.queue[0]  # Fixed line - was incorrectly "next_item = self.queue"
        if self.start_taby(next_item["url"], self.next_instance_id):
            self.next_instance_id += 1
            self.remove_from_queue(next_item["id"])
            return True
        return False
    
    def print_status(self):
        print(f"\n=== Taby Controller Status ===\nActive: {len(self.instances)}/{self.settings['max_concurrent']} | Queue: {len(self.queue)}\n")
    
    def list_instances(self):
        if not self.instances:
            print("No active instances")
            return
        
        print("\n=== Active Instances ===")
        for i in self.instances:
            print(f"ID: {i['id']}\n  URL: {i['url']}\n  RTSP: rtsp://localhost:{i['rtsp_port']}/audio\n  HTTP: http://localhost:{i['http_port']}/stream.ogg")
    
    def show_queue(self):
        print("\n=== Queue ===\n" + "\n".join([f"{i+1}. {item['url']}" for i, item in enumerate(self.queue)] or ["Empty"]) + "\n")
    
    def interactive_mode(self):
        print("Taby Controller Interactive Mode\nType 'help' for commands")
        
        cmds = {
            "list": self.list_instances,
            "queue": self.show_queue,
            "clean": self.clean_instances,
            "start-next": self.start_next,
            "help": lambda: print("\nCommands:\n  list - Show instances\n  queue - Show queue\n  add URL - Add URL\n  clean - Remove dead instances\n  stop ID - Stop instance\n  stop-all - Stop all\n  start-next - Start next\n  exit/quit - Exit\n")
        }
        
        while True:
            try:
                cmd = input("> ").strip()
                if not cmd: continue
                if cmd in ["exit", "quit"]: break
                
                if cmd in cmds:
                    cmds[cmd]()
                elif cmd.startswith("stop "):
                    try: self.stop_instance(int(cmd.split(" ")[1]))
                    except: print("Invalid instance ID")
                elif cmd == "stop-all":
                    for instance in list(self.instances): self.stop_instance(instance["id"])
                elif cmd.startswith("add "):
                    self.add_to_queue(cmd[4:].strip())
                else:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Taby Controller - Manage multiple YouTube audio streams")
    parser.add_argument("-p", "--playlist", help="Load YouTube URLs from a playlist file")
    parser.add_argument("-u", "--url", action="append", help="Add YouTube URL to queue")
    parser.add_argument("-s", "--script", default="./taby.sh", help="Path to taby.sh (default: ./taby.sh)")
    parser.add_argument("-l", "--list", action="store_true", help="List active instances")
    parser.add_argument("--rtsp-base-port", type=int, default=8554, help="Base RTSP port (default: 8554)")
    parser.add_argument("--http-base-port", type=int, default=8080, help="Base HTTP port (default: 8080)")
    parser.add_argument("--port-increment", type=int, default=10, help="Port increment (default: 10)")
    parser.add_argument("--max-concurrent", type=int, default=5, help="Max instances (default: 5)")
    parser.add_argument("--log-dir", default="/tmp/taby-controller-logs", help="Log directory")
    parser.add_argument("--db-file", default="/tmp/taby-controller.db", help="Database file")
    parser.add_argument("--audio-quality", default="bestaudio", help="Audio quality (default: bestaudio)")
    parser.add_argument("--stream-bitrate", type=int, default=128, help="Stream bitrate (default: 128)")
    parser.add_argument("--stream-codec", default="mp3", help="Stream codec (default: mp3)")
    
    args = parser.parse_args()
    controller = TabyController(args)
    
    if args.list:
        controller.list_instances()
        return
    
    while len(controller.instances) < controller.settings["max_concurrent"] and controller.queue:
        controller.start_next()
    
    controller.interactive_mode()

if __name__ == "__main__":
    main()
