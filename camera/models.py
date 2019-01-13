import picamera

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from django.utils.translation import ugettext_lazy as _


class CameraSettings(models.Model):

    brightness = models.IntegerField(_('Brightness'), default=50,
                                     validators=(MaxValueValidator(100),
                                                 MinValueValidator(0)))
    contrast = models.IntegerField(_('Contrast'), default=0,
                                   validators=(MaxValueValidator(100),
                                               MinValueValidator(-100)))
    hflip = models.BooleanField(_('Flip Image Horizontal'), default=False)
    vflip = models.BooleanField(_('Flip Image Vertical'), default=False)
    days_kept = models.IntegerField(_('Storage Retention days'), default=30,
                                    validators=(MinValueValidator(1),))
    max_mb = models.IntegerField(_('Storage Retention MB'), default=256,
                                 validators=(MinValueValidator(256),))

    def apply_to(self, camera: picamera.PiCamera):
        camera.brightness = self.brightness
        camera.hflip = self.hflip
        camera.vflip = self.vflip
        camera.contrast = self.contrast
