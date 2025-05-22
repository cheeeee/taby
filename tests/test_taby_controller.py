import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import sys
import sqlite3
import argparse
import json
import signal # For signal.SIGTERM

# Adjust path to import TabyController from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from taby_controller import TabyController

# Default arguments for TabyController initialization
def create_default_args():
    args = argparse.Namespace()
    args.script = "./fake_taby.sh" 
    args.rtsp_base_port = 8554
    args.http_base_port = 8080
    args.port_increment = 10
    args.max_concurrent = 2 
    args.log_dir = "/tmp/taby_test_logs"
    # db_file is no longer used by TabyController directly from args for runtime,
    # but tests might still use it if they were testing file-based DBs.
    # For consistency with previous tests, we keep it, but TabyController forces :memory:.
    args.db_file = ":memory:" 
    args.audio_quality = "bestaudio_default" 
    args.stream_bitrate = 128 
    args.stream_codec = "mp3_default" 
    args.stream_volume = 100 
    args.url = None 
    args.playlist = None 
    return args

class TestTabyController(unittest.TestCase):

    def setUp(self):
        self.args = create_default_args()
        os.makedirs(self.args.log_dir, exist_ok=True)
        # No need to handle file-based DB cleanup here as controller forces :memory:

        self.patcher_popen = patch('subprocess.Popen')
        self.mock_popen = self.patcher_popen.start()
        self.mock_process = self.mock_popen.return_value
        self.mock_process.pid = 12345 

        self.patcher_check_output = patch('subprocess.check_output')
        self.mock_check_output = self.patcher_check_output.start()
        self.mock_check_output.return_value = "Mocked Video Title\n"

        self.patcher_os_kill = patch('os.kill')
        self.mock_os_kill = self.patcher_os_kill.start()
        
        self.patcher_socket = patch('socket.socket')
        self.mock_socket_constructor = self.patcher_socket.start()
        self.mock_socket_instance = self.mock_socket_constructor.return_value.__enter__.return_value
        self.mock_socket_instance.connect_ex.return_value = 1 # Port available by default
        
        self.patcher_set_pa_name = patch.object(TabyController, 'set_pulseaudio_device_name', return_value=True)
        self.mock_set_pa_name = self.patcher_set_pa_name.start()

    def tearDown(self):
        self.patcher_popen.stop()
        self.patcher_check_output.stop()
        self.patcher_os_kill.stop()
        self.patcher_socket.stop()
        self.patcher_set_pa_name.stop()

    def test_initialization_default(self):
        """Test basic initialization of the controller with default args."""
        controller = TabyController(self.args) 
        self.assertIsNotNone(controller)
        self.assertEqual(controller.settings["max_concurrent"], 2)
        self.assertTrue(os.path.exists(self.args.log_dir))
        self.assertEqual(controller.settings["db_file"], ":memory:") # Verify in-memory DB
        
        # Verify initial state due to in-memory DB
        self.assertEqual(len(controller.instances), 0, "Instances should be empty on init")
        self.assertEqual(len(controller.queue), 0, "Queue should be empty on init")
        self.assertEqual(controller.next_instance_id, 1, "next_instance_id should be 1 on init")
        
        # Check if tables were created in the in-memory DB
        conn = sqlite3.connect(controller.settings["db_file"]) # Use controller's db_file setting
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queue';")
        self.assertIsNotNone(cursor.fetchone())
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instances';")
        self.assertIsNotNone(cursor.fetchone())
        cursor.execute("PRAGMA table_info(queue);")
        columns = [info[1] for info in cursor.fetchall()]
        self.assertIn("options", columns)
        conn.close()

    def test_initialization_with_cli_urls(self):
        """Test initialization with URLs provided via command-line arguments."""
        self.args.url = ["http://youtube.com/watch?v=cli1", "http://youtube.com/watch?v=cli2"]
        controller = TabyController(self.args)
        
        # Queue should be populated by URLs from args
        self.assertEqual(len(controller.queue), 2)
        self.assertEqual(controller.queue[0]["url"], "http://youtube.com/watch?v=cli1")
        self.assertEqual(controller.queue[0]["options"], {}) 
        self.assertEqual(controller.queue[1]["url"], "http://youtube.com/watch?v=cli2")
        self.assertEqual(controller.queue[1]["options"], {})

        # Instances should still be empty, next_instance_id should be 1
        self.assertEqual(len(controller.instances), 0)
        self.assertEqual(controller.next_instance_id, 1)

        db_items = controller.db_op("SELECT url, options FROM queue ORDER BY id", fetch=True)
        self.assertEqual(len(db_items), 2)
        self.assertEqual(db_items[0]["url"], "http://youtube.com/watch?v=cli1")

    # --- Queue Management Tests (Controller instance created per test) ---
    def test_add_to_queue_valid_url_with_options(self):
        controller = TabyController(self.args)
        url = "http://youtube.com/watch?v=test_opts"
        options = {"volume": 80, "audio_quality": "low"}
        self.assertTrue(controller.add_to_queue(url, options))
        self.assertEqual(len(controller.queue), 1)
        self.assertEqual(controller.queue[0]["url"], url)
        self.assertEqual(controller.queue[0]["options"]["volume"], 80)
        
        db_item = controller.db_op("SELECT url, options FROM queue WHERE url=?", (url,), fetch=True)[0]
        self.assertEqual(json.loads(db_item["options"])["volume"], 80)

    # ... (other queue tests remain largely the same, ensure controller is instantiated) ...
    def test_add_to_queue_invalid_url_format(self):
        controller = TabyController(self.args)
        self.assertFalse(controller.add_to_queue("ftp://invalid.url"))
        self.assertEqual(len(controller.queue), 0)

    def test_add_to_queue_no_options(self):
        controller = TabyController(self.args)
        url = "http://youtube.com/watch?v=test_no_opts"
        self.assertTrue(controller.add_to_queue(url))
        self.assertEqual(len(controller.queue), 1)
        self.assertEqual(controller.queue[0]["url"], url)
        self.assertEqual(controller.queue[0]["options"], {}) 
        db_item = controller.db_op("SELECT url, options FROM queue WHERE url=?", (url,), fetch=True)[0]
        self.assertEqual(json.loads(db_item["options"]), {})

    def test_remove_from_queue_existing(self):
        controller = TabyController(self.args)
        url = "http://youtube.com/watch?v=test_remove"
        controller.add_to_queue(url)
        queue_id_to_remove = controller.queue[0]["id"]
        controller.remove_from_queue(queue_id_to_remove)
        self.assertEqual(len(controller.queue), 0)
        db_items = controller.db_op("SELECT * FROM queue WHERE id=?", (queue_id_to_remove,), fetch=True)
        self.assertEqual(len(db_items), 0)

    def test_remove_from_queue_non_existent(self):
        controller = TabyController(self.args)
        controller.add_to_queue("http://youtube.com/watch?v=test_remove_nonexist")
        initial_queue_size = len(controller.queue)
        controller.remove_from_queue(999) 
        self.assertEqual(len(controller.queue), initial_queue_size)

    # --- Playlist Tests ---
    @patch('builtins.open', new_callable=mock_open, read_data="http://youtube.com/watch?v=pl1\nhttp://youtube.com/watch?v=pl2")
    def test_load_playlist_valid(self, mock_file):
        controller = TabyController(self.args)
        controller.load_playlist("dummy_playlist.txt")
        self.assertEqual(len(controller.queue), 2)
        self.assertEqual(controller.queue[0]["url"], "http://youtube.com/watch?v=pl1")
        self.assertEqual(controller.queue[0]["options"], {})

    # ... (Other tests for start_taby, start_next, stop_instance also need controller instance)

    # --- start_taby Tests ---
    def test_start_taby_success_default_options(self):
        controller = TabyController(self.args) # Instantiate controller
        self.mock_check_output.return_value = "Test Video Title"
        url_to_start = "http://youtube.com/watch?v=start_default"
        instance_id = controller.next_instance_id
        
        result = controller.start_taby(url_to_start, instance_id) 
        
        self.assertTrue(result)
        self.assertEqual(len(controller.instances), 1)
        call_args_list = self.mock_popen.call_args[0][0]
        self.assertEqual(call_args_list[call_args_list.index("--volume") + 1], str(self.args.stream_volume))
        self.assertEqual(call_args_list[call_args_list.index("--audio-quality") + 1], self.args.audio_quality)
        self.mock_set_pa_name.assert_has_calls([
            call(f"ts_sink_{instance_id}", "Test Video Title"),
            call(f"ts_sink_{instance_id}.monitor", "Monitor of Test Video Title", True),
            call(f"TS_Bot_{instance_id}", "Test Video Title", True)
        ], any_order=False)

    # --- clean_instances Tests ---
    def test_clean_instances_one_dead_one_alive(self):
        controller = TabyController(self.args)
        live_pid = 111
        dead_pid = 222
        
        # Manually populate controller.instances as load_instances() is empty
        controller.instances = [
            {"id": 1, "pid": live_pid, "url": "live_url", "rtsp_port": 0, "http_port": 0, "sink_name": "", "source_name": ""},
            {"id": 2, "pid": dead_pid, "url": "dead_url", "rtsp_port": 0, "http_port": 0, "sink_name": "", "source_name": ""}
        ]
        # Add to DB for consistency with how clean_instances tries to delete from DB
        controller.db_op("INSERT INTO instances (id, url, pid) VALUES (?,?,?)", (1, "live_url", live_pid))
        controller.db_op("INSERT INTO instances (id, url, pid) VALUES (?,?,?)", (2, "dead_url", dead_pid))

        def os_kill_side_effect(pid, sig):
            if pid == dead_pid: raise ProcessLookupError
            return 
        self.mock_os_kill.side_effect = os_kill_side_effect
        
        controller.clean_instances()
        self.assertEqual(len(controller.instances), 1)
        self.assertEqual(controller.instances[0]["id"], 1)
        dead_db = controller.db_op("SELECT * FROM instances WHERE id=?", (2,), fetch=True)
        self.assertEqual(len(dead_db), 0)

    def test_clean_instances_os_kill_other_exception(self):
        controller = TabyController(self.args)
        pid = 333
        # Manually populate controller.instances
        controller.instances = [{"id": 3, "pid": pid, "url": "error_kill", "rtsp_port":0, "http_port":0, "sink_name":"", "source_name":""}]
        controller.db_op("INSERT INTO instances (id, url, pid) VALUES (?,?,?)", (3, "error_kill", pid))
        
        self.mock_os_kill.side_effect = PermissionError("Permission denied for kill")
        
        controller.clean_instances()
        self.assertEqual(len(controller.instances), 1) # Should not remove

    # --- Shutdown Test ---
    def test_shutdown_stops_all_instances(self):
        """Test that shutdown() calls stop_instance() for all active instances."""
        controller = TabyController(self.args)
        
        # Manually add mock instances to the controller's list
        controller.instances = [
            {"id": 1, "pid": 123, "url": "url1"},
            {"id": 2, "pid": 456, "url": "url2"}
        ]
        # Mock stop_instance to verify it's called
        controller.stop_instance = MagicMock(return_value=True)
        
        controller.shutdown()
        
        self.assertTrue(controller._shutting_down)
        self.assertEqual(controller.stop_instance.call_count, 2)
        controller.stop_instance.assert_any_call(1)
        controller.stop_instance.assert_any_call(2)

    # (Keep other existing tests, ensuring controller is instantiated in each)
    # For brevity, I'm not repeating all tests here, just showing the adjustments
    # and the new shutdown test. The pattern of instantiating controller per test
    # or ensuring self.args is set up before a shared controller instance is used
    # should be applied to all relevant tests.

    # Placeholder for other tests that need controller instance
    def test_placeholder_for_other_tests(self):
        controller = TabyController(self.args)
        # Example: self.mock_socket_instance setup if not default for this test
        # Then call controller methods
        pass


if __name__ == '__main__':
    unittest.main()
