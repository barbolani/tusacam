# Generated by Django 2.0.7 on 2018-09-11 20:29

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CameraSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brightness', models.IntegerField(default=50, validators=[django.core.validators.MaxValueValidator(100), django.core.validators.MinValueValidator(0)], verbose_name='Brightness')),
                ('contrast', models.IntegerField(default=0, validators=[django.core.validators.MaxValueValidator(100), django.core.validators.MinValueValidator(-100)], verbose_name='Contrast')),
                ('hflip', models.BooleanField(default=False, verbose_name='Flip Image Horizontal')),
                ('vflip', models.BooleanField(default=False, verbose_name='Flip Image Vertical')),
                ('days_kept', models.IntegerField(default=30, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Storage Retention days')),
                ('max_mb', models.IntegerField(default=256, validators=[django.core.validators.MinValueValidator(256)], verbose_name='Storage Retention MB')),
            ],
        ),
    ]
