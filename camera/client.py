# -*- coding: utf-8 -*-

import socket
import sys
import struct


from django.conf import settings

from camera.management.commands.camera_server import Command


class CameraClient:

    def __init__(self, command: str):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(('localhost', settings.CAMERA_SERVER_PORT))
        self._socket.sendall(command)


class FeedCommand(CameraClient):

    def __init__(self):
        super().__init__(Command.SERVER_LIVE_FEED)
        self.response = None
        buffer_length_buff = self._socket.recv(4)
        if not buffer_length_buff or len(buffer_length_buff) != 4:
            return
        buffer_length = struct.unpack('I', buffer_length_buff[:4])[0]
        if buffer_length:
            self.response = bytearray(buffer_length)
            total_read = 0
            remaining = buffer_length
            while remaining:
                b = memoryview(self.response)
                received = self._socket.recv_into(b[total_read:], remaining)
                total_read += received
                remaining -= received
