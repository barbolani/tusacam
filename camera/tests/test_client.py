
import socket
import struct

from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase

from camera.client import CameraClient, FeedCommand
from camera.management.commands.camera_server import Command
from camera.models import CameraSettings


class TestCameraClient(SimpleTestCase):

    def check_base_client(self, conn, send, cmd):
        self.assertEqual(conn.call_count, 1)
        self.assertEqual(conn.call_args[0], (('localhost', settings.CAMERA_SERVER_PORT),))
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args[0], (cmd,))

    def test_base_client(self):
        with patch.object(socket.socket, 'connect') as conn:
            with patch.object(socket.socket, 'sendall') as send:
                command = CameraClient(Command.SERVER_PING)
                self.check_base_client(conn, send, Command.SERVER_PING)

    def test_feed_command_empty_response(self):
        with patch.object(socket.socket, 'connect') as conn:
            with patch.object(socket.socket, 'sendall') as send:
                with patch.object(socket.socket, 'recv', return_value=[]):
                    command = FeedCommand()
                    self.check_base_client(conn, send, Command.SERVER_LIVE_FEED)
                    self.assertIsNone(command.response)

    def test_feed_command_completed_response(self):
        with patch.object(socket.socket, 'connect') as conn:
            with patch.object(socket.socket, 'sendall') as send:
                buffer_lenght_resp = struct.pack('I', 2)
                with patch.object(socket.socket, 'recv', return_value=buffer_lenght_resp):
                    with patch.object(socket.socket, 'recv_into', side_effect=(1, 1)):
                        command = FeedCommand()
                        self.check_base_client(conn, send, Command.SERVER_LIVE_FEED)
                        self.assertIsNotNone(command.response)
