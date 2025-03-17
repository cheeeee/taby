#!/usr/bin/env python3
import os, sys, signal, argparse, subprocess, time, re, shutil, sqlite3
from datetime import datetime
from contextlib import contextmanager

DEFAULT_SETTINGS = {
    "taby_script": "./taby.sh", "rtsp_base_port": 8554, "http_base_port": 8080,
    "port_increment": 10, "max_concurrent": 5, "log_dir": "/tmp/taby-controller-logs",
    "db_file": "/tmp/taby-controller.db"
}

@contextmanager
def db_connection(db_file):
    conn = sqlite3.connect(db_file)
    try: yield conn
    finally: conn.close()

class TabyController:
    def __init__(self):
        self.settings, self.urls_queue, self.running = DEFAULT_SETTINGS.copy(), [], True
        self.parse_arguments()
        self.check_dependencies()
        self.setup_db()
        signal.signal(signal.SIGINT, lambda s, f: self.cleanup())
        signal.signal(signal.SIGTERM, lambda s, f: self.cleanup())
        
    def parse_arguments(self):
        parser = argparse.ArgumentParser(description="Manage multiple taby instances")
        parser.add_argument("-p", "--playlist", help="Playlist file with YouTube URLs")
        parser.add_argument("-u", "--url", action="append", help="Add YouTube URL to queue")
        parser.add_argument("-s", "--script", help=f"Path to taby.sh (default: {self.settings['taby_script']})")
        parser.add_argument("-l", "--list", action="store_true", help="List active instances")
        parser.add_argument("--rtsp-base-port", type=int, help=f"RTSP base port (default: {self.settings['rtsp_base_port']})")
        parser.add_argument("--http-base-port", type=int, help=f"HTTP base port (default: {self.settings['http_base_port']})")
        parser.add_argument("--port-increment", type=int, help=f"Port increment (default: {self.settings['port_increment']})")
        parser.add_argument("--max-concurrent", type=int, help=f"Max concurrent instances (default: {self.settings['max_concurrent']})")
        parser.add_argument("--log-dir", help=f"Log directory (default: {self.settings['log_dir']})")
        parser.add_argument("--db-file", help=f"Database file (default: {self.settings['db_file']})")
        args = parser.parse_args()
        
        for k, v in vars(args).items():
            if v and k in self.settings: self.settings[k] = v
        
        if args.url: self.urls_queue.extend(args.url)
        if args.playlist: 
            with open(args.playlist, 'r') as f:
                self.urls_queue.extend([l.strip() for l in f if l.strip() and not l.startswith('#')])
        self.list_only = args.list
    
    def check_dependencies(self):
        for cmd in ["yt-dlp", "curl"]:
            if not shutil.which(cmd): sys.exit(f"Error: {cmd} not installed")
        if not os.path.isfile(self.settings["taby_script"]) or not os.access(self.settings["taby_script"], os.X_OK):
            sys.exit(f"Error: taby script not found or not executable: {self.settings['taby_script']}")
    
    def setup_db(self):
        os.makedirs(self.settings["log_dir"], exist_ok=True)
        with db_connection(self.settings["db_file"]) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS taby_instances (
                id INTEGER PRIMARY KEY, pid INTEGER NOT NULL, url TEXT NOT NULL, name TEXT NOT NULL,
                sink_name TEXT NOT NULL, source_name TEXT NOT NULL, rtsp_port INTEGER NOT NULL,
                http_port INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Running')''')
            conn.execute('''CREATE TABLE IF NOT EXISTS url_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()
    
    def cleanup(self):
        print("\nTerminating... Cleaning up...")
        self.stop_all_tabies()
        sys.exit(0)
    
    def get_name(self, url):
        video_id = "unknown"
        for regex in [r'youtube\.com/watch\?v=([^&]*)', r'youtu\.be/([^?]*)']: 
            if match := re.search(regex, url): 
                video_id = match.group(1)
                break
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        try:
            result = subprocess.run(["yt-dlp", "--skip-download", "--print", "title", url],
                                  capture_output=True, text=True, check=False)
            if title := result.stdout.strip():
                sanitized = re.sub(r'[^a-zA-Z0-9 ]', '', title).replace(' ', '_').lower()[:10]
                return f"taby-{sanitized}-{timestamp}-{video_id[:3]}"
        except: pass
        return f"taby-{timestamp}-{video_id}"
    
    def db_query(self, query, params=(), fetch=None):
        with db_connection(self.settings["db_file"]) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            if fetch == 'one': return cursor.fetchone()
            elif fetch == 'all': return cursor.fetchall()
            elif fetch == 'count': return cursor.fetchone()[0]
            conn.commit()
    
    def start_taby(self, url, instance_id):
        rtsp_port = self.settings["rtsp_base_port"] + (instance_id * self.settings["port_increment"])
        http_port = self.settings["http_base_port"] + (instance_id * self.settings["port_increment"])
        name = self.get_name(url)
        sink_name, source_name = f"{name}_sink"[:15], f"{name}_source"[:15]
        
        log_file = os.path.join(self.settings["log_dir"], f"taby_{instance_id}.log")
        with open(log_file, 'w') as f:
            process = subprocess.Popen([
                self.settings["taby_script"], url, "--rtsp-port", str(rtsp_port), 
                "--http-port", str(http_port), "--sink-name", sink_name, "--source-name", source_name
            ], stdout=f, stderr=f)
        
        self.db_query('''INSERT INTO taby_instances 
                      (id, pid, url, name, sink_name, source_name, rtsp_port, http_port, status)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Running')''', 
                   (instance_id, process.pid, url, name, sink_name, source_name, rtsp_port, http_port))
        print(f"Taby #{instance_id} started (PID: {process.pid})")
        return process.pid
    
    def stop_taby(self, instance_id):
        if instance := self.db_query('SELECT pid FROM taby_instances WHERE id = ?', (instance_id,), 'one'):
            try: os.kill(instance[0], signal.SIGTERM)
            except ProcessLookupError: pass
            self.db_query('DELETE FROM taby_instances WHERE id = ?', (instance_id,))
            return True
        return False
    
    def stop_all_tabies(self):
        for instance_id, pid in self.db_query('SELECT id, pid FROM taby_instances', fetch='all') or []:
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
        self.db_query('DELETE FROM taby_instances')
    
    def update_statuses(self):
        for instance_id, pid in self.db_query('SELECT id, pid FROM taby_instances WHERE status = "Running"', fetch='all') or []:
            try: os.kill(pid, 0)
            except ProcessLookupError: self.db_query('UPDATE taby_instances SET status = ? WHERE id = ?', ('Dead', instance_id))
    
    def list_tabies(self):
        self.update_statuses()
        rows = self.db_query('SELECT id, pid, status, rtsp_port, http_port, name, url FROM taby_instances ORDER BY id', fetch='all')
        if not rows:
            print("No active taby instances")
            return
        
        print("Active taby instances:")
        print("-" * 80)
        print(f"{'ID':<4} {'PID':<8} {'Status':<8} {'RTSP':<6} {'HTTP':<6} {'Name':<20} {'URL':<30}")
        print("-" * 80)
        for instance_id, pid, status, rtsp, http, name, url in rows:
            url_display = f"{url[:27]}..." if len(url) > 30 else url
            print(f"{instance_id:<4} {pid:<8} {status:<8} {rtsp:<6} {http:<6} {name:<20} {url_display:<30}")
        print("-" * 80)
    
    def start_next(self):
        if not self.urls_queue:
            print("No URLs in queue")
            return
            
        active_count = self.db_query('SELECT COUNT(*) FROM taby_instances WHERE status = "Running"', fetch='count') or 0
        if active_count >= self.settings["max_concurrent"]:
            oldest_id = self.db_query('SELECT id FROM taby_instances ORDER BY created_at LIMIT 1', fetch='one')[0]
            self.stop_taby(oldest_id)
        
        url = self.urls_queue.pop(0)
        next_id = self.db_query('SELECT COALESCE(MAX(id)+1, 0) FROM taby_instances', fetch='one')[0]
        self.start_taby(url, next_id)
    
    def run(self):
        if self.list_only:
            self.list_tabies()
            return
        
        active_count = self.db_query('SELECT COUNT(*) FROM taby_instances', fetch='count') or 0
        while active_count < self.settings["max_concurrent"] and self.urls_queue:
            self.start_next()
            active_count = self.db_query('SELECT COUNT(*) FROM taby_instances', fetch='count') or 0
        
        print("Interactive mode. Type 'help' for commands.")
        self.update_statuses()
        
        while self.running:
            try:
                cmd, *args = input("taby-controller> ").split(maxsplit=1)
                arg = args[0] if args else ""
                
                if cmd == "list": self.list_tabies()
                elif cmd == "stop" and arg: self.stop_taby(int(arg))
                elif cmd == "stop-all": self.stop_all_tabies()
                elif cmd == "start-next": self.start_next()
                elif cmd == "add" and arg:
                    self.urls_queue.append(arg)
                    self.db_query('INSERT INTO url_queue (url) VALUES (?)', (arg,))
                    if (self.db_query('SELECT COUNT(*) FROM taby_instances WHERE status = "Running"', fetch='count') or 0) < self.settings["max_concurrent"]:
                        self.start_next()
                elif cmd == "clean": self.db_query('DELETE FROM taby_instances WHERE status = "Dead"')
                elif cmd == "queue": print("\n".join(f"{i+1}: {url}" for i, url in enumerate(self.urls_queue)))
                elif cmd == "help": print("Commands: list, stop ID, stop-all, start-next, add URL, clean, queue, help, exit/quit")
                elif cmd in ["exit", "quit"]: self.cleanup()
                elif cmd: print(f"Unknown command: {cmd}")
            except KeyboardInterrupt: print("\nUse 'exit' or 'quit' to exit")
            except Exception as e: print(f"Error: {e}")

if __name__ == "__main__":
    TabyController().run()
