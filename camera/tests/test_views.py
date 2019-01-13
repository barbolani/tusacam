
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.urls import reverse
from django.test import TestCase

from camera.client import CameraClient, FeedCommand
from camera.management.commands.camera_server import Command
from camera.models import CameraSettings


class FakeFeedCommand:
    def __init__(self):
        self.response = b''


class TestViews(TestCase):

    def setUp(self):
        user = User.objects.create(username='test')
        self.client.force_login(user)

    def test_get_views(self):
        for view_name in ('browse', 'live_preview', 'camera_config'):
            view_url = reverse(view_name)
            result = self.client.get(view_url)
            self.assertEqual(result.status_code, 200)

    def test_still_frame(self):
        view_url = reverse('still_frame')
        with patch('camera.views.FeedCommand', return_value=FakeFeedCommand()):
            result = self.client.get(view_url)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(result.content), 0)
            self.assertEqual(result['Cache-Control'], 'max-age=0, must-revalidate')

    def test_media_file(self):
        url = reverse('media_file', args=('notfound.txt',))
        result = self.client.get(url)
        self.assertEqual(result.status_code, 404)

    def test_shutdown(self):
        view_url = reverse('shutdown')
        with patch('camera.views.os.system') as osys:
            result = self.client.get(view_url)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(osys.call_count, 1)

    def test_config_post(self):
        post_data = dict(brightness=11, hflip=True, vflip=True,
                         contrast=21, days_kept=300, max_mb=1000)
        url = reverse('camera_config')
        with patch('camera.views.CameraClient') as init:
            result = self.client.post(url, post_data)
            self.assertEqual(result.status_code, 302)
            self.assertEqual(init.call_count, 1)
            self.assertEqual(init.call_args[0], (Command.SERVER_SETTINGS,))
            cam_settings = CameraSettings.objects.first()
            self.assertEqual(cam_settings.brightness, 11)
            self.assertEqual(cam_settings.hflip, True)
            self.assertEqual(cam_settings.vflip, True)
            self.assertEqual(cam_settings.contrast, 21)
            self.assertEqual(cam_settings.days_kept, 300)
            self.assertEqual(cam_settings.max_mb, 1000)
