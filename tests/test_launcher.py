"""Launcher regression: an occupied port must never be shared."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'portal'))
_data = tempfile.TemporaryDirectory()
os.environ['SNS_STUDY_DB'] = str(Path(_data.name) / 'test.sqlite3')
import launch_portal


class LauncherTests(unittest.TestCase):
    def test_busy_port_is_skipped_and_socket_stays_reserved(self):
        first = launch_portal.LocalPortalServer(('127.0.0.1', 0), launch_portal.PortalRequestHandler)
        second = None
        try:
            second = launch_portal.bind_server(first.server_port)
            self.assertNotEqual(first.server_port, second.server_port)
            self.assertEqual(second.server_address[0], '127.0.0.1')
            with self.assertRaises(OSError):
                launch_portal.LocalPortalServer(second.server_address, launch_portal.PortalRequestHandler)
        finally:
            if second:
                second.server_close()
            first.server_close()


if __name__ == '__main__':
    unittest.main()
