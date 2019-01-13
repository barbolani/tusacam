# -*- coding: utf-8 -*-

import socket
import struct
import sys

from django.core.management.base import BaseCommand
from django.conf import settings

from camera.capture import Capture
from camera.models import CameraSettings


class Command(BaseCommand):
    """A thin layer of TCPIP server over the capture daemon that communicates
    with it using pipes, locks and shared memory buffers
    """
    SERVER_PING = b'PING'
    SERVER_QUIT = b'QUIT'
    SERVER_SETTINGS = b'SETT'
    SERVER_LIVE_FEED = b'FEED'

    def ping(self, _: socket):
        """Does nothing as a command but useful to know if the server is up
        and running
        """
        return

    def settings(self, _: socket.socket):
        """Pushes a new set of settings on the queue so the camera is
        reconfigured in the next available occassion (that is, when recording
        is not taking place)
        """
        Capture.CAMERA_SETTINGS_QUEUE.put(CameraSettings.objects.first())

    def live_feed(self, conn: socket.socket):
        """Feeds back the latest live preview over the socket, or nothing if
        there is none available
        """
        if Capture.CAMERA_CURRENT_FEED_BUFFER.value == -1:
            conn.sendall(bytearray((0, 0, 0, 0)))
            return
        try:
            with Capture.CAMERA_CURRENT_FEED_LOCK:
                Capture.CAMERA_CURRENT_FEED_USAGE.value += 1
            buffer = bytearray(Capture.CAMERA_FEED_BUFFERS[Capture.CAMERA_CURRENT_FEED_BUFFER.value])
            buffer_length = struct.unpack('I', buffer[:4])[0]
            conn.sendall(buffer[:4 + buffer_length])
        finally:
            with Capture.CAMERA_CURRENT_FEED_LOCK:
                Capture.CAMERA_CURRENT_FEED_USAGE.value -= 1
        return

    def quit(self, _: socket.socket):
        """Stops the server
        """
        self.quit = True

    def handle(self, *args, **kwargs):

        self.SERVER_COMMANDS = {
            self.SERVER_PING: self.ping,
            self.SERVER_SETTINGS: self.settings,
            self.SERVER_LIVE_FEED: self.live_feed,
            self.SERVER_QUIT: self.quit
        }

        Capture.start_daemon(settings.CAMERA_STORAGE_FOLDER)
        self.settings(None)
        # Fairly boilerplate server code
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Bind the socket to the port
        sock.bind(('localhost', settings.CAMERA_SERVER_PORT))
        # Listen for incoming connections
        sock.listen(2)
        self.quit = False
        try:
            while not self.quit:
                # Wait for a connection
                connection, client_address = sock.accept()
                data = connection.recv(4)
                # Read the command and act upon it
                self.SERVER_COMMANDS.get(data, lambda self_obj, conn: None)(connection)
                connection.close()
        finally:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            Capture.stop_daemon()
