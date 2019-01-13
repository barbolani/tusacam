
from django.test import TestCase
from unittest.mock import Mock
from camera.models import CameraSettings


class TestModels(TestCase):

    def test_apply_to(self):
        picamera = Mock(brightness=0, hflip=False, vflip=True,
                        contrast=10)
        camera_settings = CameraSettings(brightness=1, hflip=True, 
                                         vflip=False, contrast=20)
        camera_settings.apply_to(picamera)
        self.assertEqual(picamera.brightness, 1)
        self.assertEqual(picamera.hflip, True)
        self.assertEqual(picamera.vflip, False)
        self.assertEqual(picamera.contrast, 20)
