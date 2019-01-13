import os
import pathlib
import picamera
import struct

from unittest.mock import Mock, patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from camera.capture import Capture, FileManager, LiveFeed, capture_loop, GPIOInput, video_conversion
from camera.models import CameraSettings
from multiprocessing import Process, Queue


class TestGPIOInput(SimpleTestCase):

    def test_input(self):
        with patch('camera.capture.GPIO') as GPIO:
            GPIOInput(1).input()
            self.assertEqual(GPIO.input.call_count, 1)

    def test_wait(self):
        with patch('camera.capture.GPIO') as GPIO:
            GPIOInput(1).wait()
            self.assertEqual(GPIO.wait_for_edge.call_count, 1)


class SimpleFileManager(FileManager):

    def __init__(self):
        folder = os.path.join(os.path.dirname(__file__), 'capture')
        pathlib.Path(folder).mkdir(parents=True, exist_ok=True)
        super().__init__(folder)

    def clean_files(self):
        for f in pathlib.Path(self._folder).iterdir():
            f.unlink()

    def create_file(self, fname, size=1):
        with open(os.path.join(self._folder, fname), 'w') as f:
            f.write('1' * size)


class TestFileManager(SimpleTestCase):

    def setUp(self):
        self.file_mngr = SimpleFileManager()

    def tearDown(self):
        self.file_mngr.clean_files()

    def test_list_videos_bad_file(self):
        self.file_mngr.create_file('text.mp4')
        self.file_mngr.create_file('2018-31-31_120000_123.mp4')
        self.assertEqual(len(self.file_mngr.list_videos()), 0)

    def test_storage_policy_empty(self):
        self.file_mngr.apply_storage_policy(1000, 16)

    def test_storage_policy_age(self):
        self.file_mngr.create_file('2018-01-01_120000_123.mp4')
        self.file_mngr.create_file('2018-01-31_120000_123.mp4')
        self.file_mngr.create_file('2018-01-15_120000_123.mp4')
        self.file_mngr.apply_storage_policy(1000, 16)
        self.assertFalse(pathlib.Path(self.file_mngr._folder, '2018-01-01_120000_123.mp4').exists())
        self.assertTrue(pathlib.Path(self.file_mngr._folder, '2018-01-31_120000_123.mp4').exists())
        self.assertTrue(pathlib.Path(self.file_mngr._folder, '2018-01-15_120000_123.mp4').exists())

    def test_storage_policy_size(self):
        self.file_mngr.create_file('2018-01-31_120000_123.mp4', 256 * 1024)
        self.file_mngr.create_file('2018-01-15_120000_123.mp4', 256 * 1024)
        self.file_mngr.create_file('2018-01-02_120000_123.mp4', 2 * 1024 * 1024)
        self.file_mngr.create_file('2018-01-01_120000_123.mp4', 2 * 1024 * 1024)
        self.file_mngr.apply_storage_policy(1, 1000)
        self.assertFalse(pathlib.Path(self.file_mngr._folder, '2018-01-01_120000_123.mp4').exists())
        self.assertFalse(pathlib.Path(self.file_mngr._folder, '2018-01-02_120000_123.mp4').exists())
        self.assertTrue(pathlib.Path(self.file_mngr._folder, '2018-01-31_120000_123.mp4').exists())
        self.assertTrue(pathlib.Path(self.file_mngr._folder, '2018-01-15_120000_123.mp4').exists())

    def test_storage_policy_size_stat_error(self):
        self.file_mngr.create_file('2018-01-31_120000_123.mp4', 2 * 1024 * 1024)
        with patch('camera.capture.os.stat', side_effect=IOError):
            self.file_mngr.apply_storage_policy(1, 1)
            self.assertTrue(pathlib.Path(self.file_mngr._folder, '2018-01-31_120000_123.mp4').exists())

    def test_cleanup_on_init(self):
        self.file_mngr.create_file('2018-01-01_120000_123.h264')
        self.file_mngr.create_file('2018-01-01_120000_123.h264.jpg')
        FileManager(self.file_mngr._folder)
        self.assertFalse(pathlib.Path(self.file_mngr._folder, '2018-01-01_120000_123.h264').exists())
        self.assertFalse(pathlib.Path(self.file_mngr._folder, '2018-01-01_120000_123.h264.jpg').exists())

    def test_path_functions(self):
        self.assertTrue(self.file_mngr.new_filename().endswith('.h264'))
        complete_path = self.file_mngr.complete_path('test')
        self.assertTrue(complete_path.startswith(self.file_mngr._folder))
        self.assertTrue(complete_path.endswith('test'))


class TestLiveFeed(SimpleTestCase):

    def setUp(self):
        super().setUp()
        Capture.init_buffers()
        self.live_feed = LiveFeed(Capture.CAMERA_CURRENT_FEED_LOCK,
                                  Capture.CAMERA_CURRENT_FEED_USAGE,
                                  Capture.CAMERA_CURRENT_FEED_BUFFER,
                                  Capture.CAMERA_FEED_BUFFERS)
        self.camera = Mock()

    def test_capture_frame_no_buffer_index(self):
        self.live_feed.capture_frame(self.camera)
        self.assertEqual(Capture.CAMERA_CURRENT_FEED_BUFFER.value, 0)
        self.assertEqual(self.camera.capture.call_count, 1)

    def test_capture_usage_counter_not_zero(self):
        Capture.CAMERA_CURRENT_FEED_BUFFER.value = 0
        Capture.CAMERA_CURRENT_FEED_USAGE.value = 1
        self.live_feed.capture_frame(self.camera)
        self.assertEqual(Capture.CAMERA_CURRENT_FEED_BUFFER.value, 0)
        self.assertEqual(self.camera.capture.call_count, 0)

    def test_capture_usage_counter_zero(self):
        Capture.CAMERA_CURRENT_FEED_BUFFER.value = 0
        Capture.CAMERA_CURRENT_FEED_USAGE.value = 0
        self.live_feed.capture_frame(self.camera)
        self.assertEqual(Capture.CAMERA_CURRENT_FEED_BUFFER.value, 1)
        self.assertEqual(self.camera.capture.call_count, 1)


class TestCapture(TestCase):

    def setUp(self):
        Capture.init_buffers()
        self.settings = CameraSettings.objects.create(days_kept=1,
                                                      max_mb=1)
        self.file_manager = SimpleFileManager()

    def tearDown(self):
        self.file_manager.clean_files()

    def test_start_daemon(self):
        with patch.object(Process, 'start'):
            Capture.start_daemon(SimpleFileManager()._folder)

    def test_capture_loop_wait_settings(self):
        with patch('camera.capture.GPIO') as GPIO:
            with patch('camera.capture.picamera.PiCamera') as PiCam:
                settings_queue = Mock()
                settings_queue.empty = Mock(side_effect=(True, False, False, False))
                stop_queue = Mock()
                stop_queue.empty = Mock(side_effect=(True, True, True, False, False))
                capture_loop(self.file_manager,
                             stop_queue,
                             settings_queue,
                             Capture.CAMERA_CURRENT_FEED_LOCK,
                             Capture.CAMERA_CURRENT_FEED_USAGE,
                             Capture.CAMERA_CURRENT_FEED_BUFFER,
                             Capture.CAMERA_FEED_BUFFERS[0],
                             Capture.CAMERA_FEED_BUFFERS[1])

    def test_video_conversion(self):
        """Ok, this is not very useful but included for completeness, we
        simply check that the file is deleted after calling the ffmpeg
        conversion but we don't actually perform any testing that ffmpeg
        is running correctly
        """
        self.file_manager.create_file('simple.h264')
        with patch('camera.capture.subprocess.run'):
            video_conversion(1, self.file_manager.complete_path('simple.h264'), 'nothing')
        self.assertFalse(pathlib.Path(self.file_manager._folder,
                                      'simple.h264').exists())

    def test_capture_loop_movement(self):
        allow_retries = (True,) * settings.MOTION_SENSOR_RETRIES
        stop_queue = Mock()
        stop_queue.empty = Mock(side_effect=(True, True) + allow_retries + (False, False, False))
        with patch('camera.capture.GPIO'):
            with patch.object(GPIOInput, 'wait') as wait:
                wait.side_effect = (True, True) + (None,) * settings.MOTION_SENSOR_RETRIES
                settings_queue = Queue()
                settings_queue.put(self.settings)
                with patch('camera.capture.picamera.PiCamera') as PiCam:
                    with patch('camera.capture.shutil.move'):
                        with patch('camera.capture.os.remove'):
                            with patch('camera.capture.subprocess.run'):
                                capture_loop(self.file_manager,
                                             stop_queue,
                                             settings_queue,
                                             Capture.CAMERA_CURRENT_FEED_LOCK,
                                             Capture.CAMERA_CURRENT_FEED_USAGE,
                                             Capture.CAMERA_CURRENT_FEED_BUFFER,
                                             Capture.CAMERA_FEED_BUFFERS[0],
                                             Capture.CAMERA_FEED_BUFFERS[1])
