import os
import subprocess

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import UpdateView

from camera.capture import FileManager
from camera.client import CameraClient, FeedCommand
from camera.management.commands.camera_server import Command
from camera.models import CameraSettings

from sendfile import sendfile


@require_http_methods(["GET"])
def browse(request):
    videos = FileManager(settings.CAMERA_STORAGE_FOLDER).list_videos()
    return render(request, 'browse.html', context=dict(videos=videos))


@require_http_methods(["GET"])
def live_preview(request):
    return render(request, 'live_preview.html')


@require_http_methods(["GET"])
def still_frame(request):
    feed = FeedCommand()
    response = HttpResponse(bytes(feed.response), content_type='img/jpg')
    response['Cache-Control'] = 'max-age=0, must-revalidate'
    return response


@require_http_methods(["GET"])
def media_file(request, path):
    """Wrapper that protects video files from being retrieved by
    non-authenticated users
    """
    return sendfile(request, os.path.join(settings.MEDIA_ROOT, path))


@require_http_methods(["GET"])
def shutdown(request):
    os.system('sudo systemctl isolate poweroff.target')
    return render(request, 'shutdown.html')


class ConfigView(UpdateView, LoginRequiredMixin):

    model = CameraSettings
    fields = '__all__'
    template_name = 'camerasettings_form.html'
    success_url = '/browse'

    def get_object(self):
        camera_settings = CameraSettings.objects.first()
        if not camera_settings:
            camera_settings = CameraSettings.objects.create()
        return camera_settings

    def form_valid(self, form):
        result = super().form_valid(form)
        form.save()
        CameraClient(Command.SERVER_SETTINGS)
        return result
