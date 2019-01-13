#!/usr/bin/python
import ctypes
import datetime
import io
import os
import pathlib
import pytz
import re
import shutil
import subprocess
import struct
from time import sleep
from typing import Tuple, List
from pathlib import Path

from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
from django.conf import settings
from django.utils.timezone import localtime, now, make_aware

from os.path import expanduser, basename, splitext
import RPi.GPIO as GPIO
from multiprocessing import Process, Queue, Lock, RawArray, RawValue

from pathlib import Path
import picamera


class GPIOBoard:

    def __init__(self, mode: int=GPIO.BOARD):
        GPIO.setmode(mode)     # Set GPIO to pin numbering

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        GPIO.cleanup()


class GPIOSensor(object):

    def __init__(self, pin: int):
        self._pin = pin


class GPIOInput(GPIOSensor):

    def __init__(self, pin: int):
        super(GPIOInput, self).__init__(pin)
        GPIO.setup(self._pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def input(self):
        return GPIO.input(self._pin)

    def wait(self, edge_type=GPIO.BOTH, ms_timeout=None):
        return GPIO.wait_for_edge(self._pin, edge_type, timeout=ms_timeout)


class Video(namedtuple('Video', ('timestamp', 'file', 'duration', 'thumbnail'))):

    # Regex for parsing video files. File name format is
    # <YYYY>-<MM>-<DD>_HHMMSS_<duration in seconds>.mp4
    # the regex splits this in two groups, one with date and time and another
    # with the duration
    NAME_RE = re.compile('(\\d{4}-\\d{2}-\\d{2}_\\d{6})_(\\d+)\.mp4')


class FileManager:

    def remove_even_thumbnail(self, file_path):
        for f in (file_path, '{}.jpg'.format(file_path)):
            try:
                os.unlink(f)
            except IOError as e:
                pass

    def __init__(self, folder: str=None):
        self._folder = folder or os.path.join(expanduser('~'), 'capture')
        pathlib.Path(self._folder).mkdir(parents=True, exist_ok=True)
        for temp_video in pathlib.Path(self._folder).glob('*.h264'):
            self.remove_even_thumbnail(str(temp_video.absolute()))

    def new_filename(self) -> str:
        timestamp = now().strftime('%Y-%m-%d_%H%M%S')
        return os.path.join(self._folder, '{}.h264'.format(timestamp))

    def complete_path(self, file_name: str) -> str:
        return os.path.join(self._folder, file_name)

    def list_videos(self) -> List[Tuple[datetime.date, List[Video]]]:
        """Returns a list of tuples sorted in descending order by date
        with the first item the date and the second the list of video files
        available
        :return a list of tuples with (date, <list of video instances>)
        """
        folder = Path(self._folder)
        videos = defaultdict(list)
        for video in folder.glob('*.mp4'):
            name_parts = Video.NAME_RE.match(video.name)
            if name_parts:
                try:
                    timestamp = datetime.strptime(name_parts.group(1),
                                                  '%Y-%m-%d_%H%M%S')
                    timestamp = make_aware(timestamp, pytz.utc)
                    duration = int(name_parts.group(2))
                    video_inst = Video(timestamp,
                                       video.name,
                                       timedelta(seconds=duration),
                                       '{}.jpg'.format(video.name))
                    videos[video_inst.timestamp.date()].append(video_inst)
                except ValueError:
                    pass
        video_keys = sorted(list(videos.keys()), reverse=True)
        for k in video_keys:
            videos[k] = sorted(videos[k], key=lambda x: x.timestamp,
                               reverse=True)
        return [(k, videos[k]) for k in video_keys]

    def apply_storage_policy(self, max_mbytes: int, max_days_kept: int):
        """Checks that all videos in the list of available videos are
        compliant with the storage policies
        :param max_mbytes: maximum space taken up by videos in MBytes
        :param max_days_kept: maximum number of days kept
        """
        # First apply maximum number of days
        video_list = self.list_videos()
        if not video_list:
            return
        first_date = video_list[0][0]
        for video_date, videos in self.list_videos():
            if (first_date - video_date).days > max_days_kept:
                for video in videos:
                    file_path = os.path.join(self._folder, video.file)
                    self.remove_even_thumbnail(file_path)
        # Then delete videos, oldest first, until the space used is less
        # than the max_mbytes
        video_list = self.list_videos()
        max_size_in_bytes = max_mbytes * (1024 * 1024)
        total_size = 0
        for _, video_files in video_list:
            for v in video_files:
                try:
                    video_size = os.stat(os.path.join(self._folder, v.file)).st_size
                    total_size += video_size
                except IOError:
                    pass
        while len(video_list) > 0 and total_size > max_size_in_bytes:
            last_video = video_list[-1][1][-1]
            file_path = os.path.join(self._folder, last_video.file)
            size_to_delete = os.stat(file_path).st_size
            # We may fail for whatever IO reason but we assume we've
            # deleted the file(s)
            self.remove_even_thumbnail(file_path)
            total_size -= size_to_delete
            video_list[-1] = (video_list[-1][0], video_list[-1][1][:-1])
            if len(video_list[-1][1]) == 0:
                video_list = video_list[:-1]


class LiveFeed:

    def __init__(self,
                 usage_lock: Lock,
                 usage_counter: RawValue,
                 buffer_index: RawValue,
                 buffers: List[RawArray]):
        """Creates a LiveFeed object that can update the images in a
        buffer list. The buffer_index parameter indicates which buffer
        is available in each moment, or -1 if there is none.
        The idea is that client classes use one of the two buffers,
        the one signaled by the buffer_ready
        :param usage_lock: the barrier used to update the snapshot.
        :param usage_counter: the counter of users of the current snapshot.
        If this counter is not zero we do not update the snapshot.
        :param buffer_index: the shared object holding the value that
        tells which buffer is the last updated. A value of -1 flags that
        no image has been captured yet
        :param buffers: a list of buffers that we're rotating on.
        Each one has to be big enough to contain a snapshot plus four bytes
        at the beggining that contain the length of the image file that is
        dumped in the buffer
        """
        self._buffers = buffers
        self._usage_lock = usage_lock
        self._usage_counter = usage_counter
        self._buffer_index = buffer_index

    def take_snapshot(self, cam: picamera.PiCamera, new_buffer_index: int):
        """Talks a snapshot and stores it in the shared buffer. Assumes that
        the buffer is not being used
        :param cam: the PiCamera instance that is used
        :param new_buffer_index: the buffer that will hold the snapshot image
        """
        iobuff = io.BytesIO()
        cam.capture(iobuff, 'jpeg', use_video_port=True)
        buffer = iobuff.getvalue()
        buffer_len = len(buffer)
        self._buffers[new_buffer_index][:4] = struct.pack('I', buffer_len)
        self._buffers[new_buffer_index][4:4 + buffer_len] = buffer[:]
        self._buffer_index.value = new_buffer_index

    def capture_frame(self, cam: picamera.PiCamera):
        """Waits until a buffer is available and uses it to store a captured
        frame
        """
        if self._buffer_index.value == -1:
            self.take_snapshot(cam, 0)
        else:
            with self._usage_lock:
                if self._usage_counter.value != 0:
                    return
                new_buffer_index = (1 + self._buffer_index.value) % len(self._buffers)
                self.take_snapshot(cam, new_buffer_index)


def video_conversion(framerate: int, capture_file: str, full_video_fname: str):
    """Perform the ffmpeg conversion in an independent thread and delete the
    capture file on termination. ffmpeg is very verbose but we do not hide
    its output so that potential problems are easier to diagnose.
    :param framerate: the intended frame rate
    :param capture_file: the source file
    :param full_video_fname: the resulting file
    """
    subprocess.run(('ffmpeg',
                    '-framerate', str(framerate),
                    '-r', str(framerate),
                    '-i', capture_file,
                    '-vcodec', 'copy',
                    full_video_fname))
    os.remove(capture_file)


class VideoCapture:

    def __init__(self, cam: picamera.PiCamera, preview_freq: int,
                 file_manager: FileManager, live_feed: LiveFeed):
        self._camera = cam
        self._preview_frequency = preview_freq
        self._file_manager = file_manager
        self._capture_file = None
        self._live_feed = live_feed

    def start_recording(self):
        """Start recording and grab a thumbnail frame
        """
        self._camera.annotate_background = picamera.Color('black')
        timestamp = localtime(now())
        self._camera.annotate_text = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        self._capture_file = self._file_manager.new_filename()
        self._camera.start_recording(self._capture_file)
        self._thumbnail_file = '{}.jpg'.format(self._capture_file)
        self._camera.capture(self._thumbnail_file, use_video_port=True)
        self._start_record_time = now()

    def keep_recording(self, seconds: int):
        """Enter a loop that ensures a still frame is captured for live preview
        up to the specified time lapse. At least one still frame is guaranteed to
        be captured no matter how short the seconds interval value is
        """
        elapsed_time = 0
        self._live_feed.capture_frame(self._camera)
        while elapsed_time < seconds:
            self._camera.wait_recording(self._preview_frequency)
            elapsed_time += self._preview_frequency
            self._live_feed.capture_frame(self._camera)

    def stop_recording(self):
        self._camera.stop_recording()
        self._camera.annotate_text = None
        video_duration = (now() - self._start_record_time).seconds
        video_fname = '{}_{}.mp4'.format(splitext(basename(self._capture_file))[0], str(video_duration))
        shutil.move(self._thumbnail_file, self._file_manager.complete_path('{}.jpg'.format(video_fname)))
        full_video_fname = self._file_manager.complete_path(video_fname)
        Process(target=video_conversion,
                args=(self._camera.framerate,
                      self._capture_file,
                      full_video_fname)).start()


def capture_loop(file_manager: FileManager,
                 stop_queue: Queue,
                 settings_queue: Queue,
                 usage_lock: Lock,
                 usage_counter: RawValue,
                 buff_index: RawValue,
                 buffer1: RawArray,
                 buffer2: RawArray):
    with GPIOBoard():
        with picamera.PiCamera() as camera:
            camera.resolution = settings.CAMERA_RESOLUTION
            camera.framerate = settings.CAMERA_FRAMERATE
            movement = GPIOInput(settings.MOTION_SENSOR_IOPORT)
            live_feed = LiveFeed(usage_lock, usage_counter, buff_index,
                                 [buffer1, buffer2])
            # Wait for camera settings to arrive before starting the actual
            # capture loop
            while settings_queue.empty():
                sleep(.5)
            while stop_queue.empty():
                camera_settings = settings_queue.get()
                camera_settings.apply_to(camera)
                while stop_queue.empty() and settings_queue.empty():
                    if movement.wait(GPIO.BOTH, ms_timeout=settings.MOTION_SENSOR_TIMEOUT) is not None:
                        print("Motion Detected!")
                        file_name = file_manager.new_filename()
                        capture = VideoCapture(camera,
                                               settings.CAMERA_PREVIEW_FREQ,
                                               file_manager,
                                               live_feed)
                        capture.start_recording()
                        capture.keep_recording(settings.MOTION_SENSOR_SETTLE)
                        missed_movements = 0
                        while stop_queue.empty() and missed_movements < settings.MOTION_SENSOR_RETRIES:
                            if movement.wait(GPIO.BOTH, ms_timeout=settings.MOTION_SENSOR_TIMEOUT) is not None:
                                print('Motion detected again')
                                missed_movements = 0
                                capture.keep_recording(settings.MOTION_SENSOR_SETTLE)
                            else:
                                print('Missed motion {}'.format(missed_movements))
                                missed_movements += 1
                                capture.keep_recording(0)   # Force still frame
                        capture.stop_recording()
                        file_manager.apply_storage_policy(camera_settings.max_mb, camera_settings.days_kept)
                    live_feed.capture_frame(camera)


class Capture:

    MAX_BUFFER_SIZE = 2592 * 1944 * 3 + 4
    CAMERA_CONTENT_MANAGER = None
    CAMERA_STOP_DAEMON_QUEUE = Queue()
    CAMERA_SETTINGS_QUEUE = Queue()
    CAMERA_FEED_BUFFERS = None
    CAMERA_CURRENT_FEED_LOCK = Lock()
    CAMERA_CURRENT_FEED_USAGE = RawValue(ctypes.c_uint)
    CAMERA_CURRENT_FEED_BUFFER = RawValue(ctypes.c_int)

    @classmethod
    def init_buffers(cls):
        cls.CAMERA_FEED_BUFFERS = list()
        for i in range(2):
            cls.CAMERA_FEED_BUFFERS.append(RawArray(ctypes.c_byte,
                                           cls.MAX_BUFFER_SIZE))
        cls.CAMERA_CURRENT_FEED_BUFFER.value = -1

    @classmethod
    def start_daemon(cls, content_folder):
        """Ensures that the daemon is running. Note that this does not prevent
        attempting to start twice when there are multiple processes or threads
        running, which results in a resource contention as the camera is a
        singleton. So it is up to you to ensure that everything runs in the
        same process and that there are no two threads using the Capture class
        """
        if cls.CAMERA_CONTENT_MANAGER is None:
            cls.init_buffers()
            cls.CAMERA_CONTENT_MANAGER = FileManager(content_folder)
            Process(target=capture_loop,
                    args=(cls.CAMERA_CONTENT_MANAGER,
                          cls.CAMERA_STOP_DAEMON_QUEUE,
                          cls.CAMERA_SETTINGS_QUEUE,
                          cls.CAMERA_CURRENT_FEED_LOCK,
                          cls.CAMERA_CURRENT_FEED_USAGE,
                          cls.CAMERA_CURRENT_FEED_BUFFER,
                          cls.CAMERA_FEED_BUFFERS[0],
                          cls.CAMERA_FEED_BUFFERS[1]),
                    daemon=False).start()

    @classmethod
    def stop_daemon(cls):
        cls.CAMERA_STOP_DAEMON_QUEUE.put(True)
