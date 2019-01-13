"""
Django settings for tusacam project.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = ['*']

LOGIN_URL = '/login'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

INSTALLED_APPS += [
    'camera',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tusacam.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # 'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tusacam.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'es-ES'

TIME_ZONE = 'Europe/Madrid'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/static/'
CAMERA_STORAGE_FOLDER = '/home/pi/capture'
MEDIA_ROOT = CAMERA_STORAGE_FOLDER
MEDIA_URL = 'media/'

STATICFILES_DIRS = ('static',)
STATIC_ROOT = 'collectstatic'
CAMERA_SERVER_PORT = 10000

# Camera capture settings
CAMERA_RESOLUTION = (640, 480)
CAMERA_FRAMERATE = 25
# Time in seconds between each frame captured in live preview
CAMERA_PREVIEW_FREQ = 0.5

# The GPIO port that the motion sensor is attached to, in GPIO.BOARD notation.
#
# GPIO.BOARD notation numbers ports according to the board layout. Putting
# the Raspberry PI such as in the top left is the outermost pin of the GPIO
# connector, the first row of ports is all even numbers from 2 to 40 and
# the second row is odd numbers from 1 to 39.
#
# Something like this:
#
#  2  4  6  8 ..... 38 40
#  1  3  5  7 ..... 37 39
#
MOTION_SENSOR_IOPORT = 8
# Time in seconds that the sensor needs to rest so that is able signal again
# after it detects motion. Means that this will be the minimum amount of time
# that the camera records since it starts just after detecting motion
# and then has to wait this time.
MOTION_SENSOR_SETTLE = 10
# Time in milliseconds to wait each time we check if the motion sensor
# has raised the voltage level in the pin that indicates motion detection
MOTION_SENSOR_TIMEOUT = 500
# How many times we attempt to detect motion after the initial motion detection.
# Since each time we wait MOTION_SENSOR_TIMEOUT milliseconds, the total time
# that will be recorded after the MOTION_SENSOR_SETTLE time in seconds
# will be equal to MOTION_SENSOR_TIMEOUT * <this value>
MOTION_SENSOR_RETRIES = 20

# See https://github.com/johnsensible/django-sendfile for configuration
# details particular to your web server
SENDFILE_BACKEND = 'sendfile.backends.xsendfile'   # Apache
