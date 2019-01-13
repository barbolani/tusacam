import os
import pathlib
import socket
import struct

from unittest.mock import Mock, patch

from django.conf import settings
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import TestCase

from camera.capture import Capture, FileManager
from camera.client import CameraClient, FeedCommand
from camera.management.commands.camera_server import Command
from camera.models import CameraSettings


class TestCameraServer(TestCase):

    def setUp(self):
        self.folder = os.path.join(os.path.dirname(__file__), 'capture')
        pathlib.Path(self.folder).mkdir(parents=True, exist_ok=True)
        Capture.CAMERA_CONTENT_MANAGER = FileManager(self.folder)

    def tearDown(self):
        Capture.CAMERA_CONTENT_MANAGER = None

    def create_cmd_seq(self, a_cmd):
        cmd = Mock(recv=Mock(return_value=a_cmd))
        srv_quit = Mock(recv=Mock(return_value=Command.SERVER_QUIT))
        return Mock(side_effect=[(c, 1) for c in (cmd, srv_quit)]), cmd

    def test_ping(self):
        with patch('camera.management.commands.camera_server.socket.socket') as fake_sock:
            fake_sock = fake_sock.return_value
            fake_sock.accept, conn = self.create_cmd_seq(Command.SERVER_PING)
            call_command('camera_server')
            self.assertEqual(conn.close.call_count, 1)
            self.assertEqual(fake_sock.shutdown.call_count, 1)
            self.assertEqual(fake_sock.close.call_count, 1)

    def test_settings(self):
        while not Capture.CAMERA_SETTINGS_QUEUE.empty():
            Capture.CAMERA_SETTINGS_QUEUE.get()
        with patch('camera.management.commands.camera_server.socket.socket') as fake_sock:
            fake_sock = fake_sock.return_value
            fake_sock.accept, _ = self.create_cmd_seq(Command.SERVER_SETTINGS)
            call_command('camera_server')
            self.assertFalse(Capture.CAMERA_SETTINGS_QUEUE.empty())

    def test_live_feed_no_buffers(self):
        Capture.init_buffers()
        with patch('camera.management.commands.camera_server.socket.socket') as fake_sock:
            fake_sock = fake_sock.return_value
            fake_sock.accept, _ = self.create_cmd_seq(Command.SERVER_LIVE_FEED)
            call_command('camera_server')

    def test_live_feed_buffers(self):
        Capture.init_buffers()
        Capture.CAMERA_CURRENT_FEED_BUFFER.value = 1
        Capture.CAMERA_FEED_BUFFERS[0][0:6] = struct.pack('I', 2) + bytearray((1, 2))
        Capture.CAMERA_FEED_BUFFERS[1][0:6] = struct.pack('I', 2) + bytearray((3, 4))
        with patch('camera.management.commands.camera_server.socket.socket') as fake_sock:
            fake_sock = fake_sock.return_value
            fake_sock.accept, conn = self.create_cmd_seq(Command.SERVER_LIVE_FEED)
            call_command('camera_server')
            self.assertEqual(Capture.CAMERA_CURRENT_FEED_USAGE.value, 0)
            send_all_call = conn.sendall.call_args[0]
            self.assertEqual(send_all_call[0], bytearray(Capture.CAMERA_FEED_BUFFERS[1][0:6]))
