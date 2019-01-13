from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.urls import path
from camera.views import browse, still_frame, live_preview, ConfigView, shutdown
from camera.views import media_file


urlpatterns = [
    path('browse', login_required(browse), name='browse'),
    path('still_frame', login_required(still_frame), name='still_frame'),
    path('live_preview', login_required(live_preview), name='live_preview'),
    path('shutdown', login_required(shutdown), name='shutdown'),
    url('camera_config/$', ConfigView.as_view(), name='camera_config'),
    url('media/(?P<path>.*)$', login_required(media_file), name='media_file')
]
