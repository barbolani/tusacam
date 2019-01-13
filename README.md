# Welcome to Tusacam

Tusacam was created to fulfill the need of a cheap and simple 
surveillance system that had their own storage (no cloud required), ran
on an inexpensive platform and was simple to operate.

The end result is a simple web app intended to run on a Raspberry PI 
that starts recording on the Pi camera based on the output of a 
motion sensor and stores the resulting video so that using the app you 
can browse recorded videos, define basic storage policies (how much 
space you want your recorded videos to take and how long you want to 
keep them), replay videos and have a basic live preview of what the 
camera is seeing at any moment.

The hardware used is:

+ Raspberry Pi: Development was done on a Pi 3B+, but any Pi that has
a camera slot should suffice
+ Pi Camera: either the PiNoir or the standard Pi Camera can be used
+ Motion sensor: I used the HC-SR501 PIR sensor

# Basic setup steps

## Create a Python virtual environment

This environment ensures that all the python modules and packages 
needed are available without messing up your system global python
configuration

```
virtualenv -p python3 <environment folder>
```

## Clone the app repository

From now on the `<app folder>` will be the "tusacam" folder inside the 
location where you have cloned the repo, so if you are at `/home/pi` and
do a git clone the `<app folder>` will be `/home/pi/tusacam`

Activate your virtual environment and install the python packages

```
source <environment folder>/bin/activate
pip install <app folder>/requirements.txt
```

## Obtain a secret key for your Django server instance

First, generate a secret key by, for example, using what is provided
by [this handy service](https://www.miniwebtool.com/django-secret-key-generator/)
and changing it to suit your tastes (do not leave the default value 
provided just in case someone hijacks that site) Since the resulting
key is likely to include characters systemd does not like you may need
to run the result via the systemd-escape utility to get a value that
you can use in systemd service configuration files.

Once you have a key you can use in systemd, copy the result 
into the clipboard. You will need that later to configure your services

## Configure your Django app

Create the Django root user, will be the one you use to log into the app.
You may want to create the superuser first and then use the admin 
module in /admin to create regular users that can login without admin
powers. Tusacam is a rather simple app so unless you enrich it a lot
you're not likely going to need much more than an admin user.

```
source <environment folder>/bin/activate
cd <app folder>
python manage.py migrate
python manage.py createsuperuser
```

provide user name and password as responses to the prompts

Configure the PiCamera settings by changing the values in 
`<app folder>/tusacam/settings.py`

## Configure Apache to serve your app

First install apache and mods

```
sudo apt-get install apache libapache2-mod-xsendfile libapache2-mod-wsgi-py3
```

Edit the apache configuration file 

```
sudo vim /etc/apache2/apache2.conf
```

```
XSendFile On
XSendFilePath /home/pi/capture/

# We use user=pi because our app is installed on a folder that is
# read-write accessible by the user pi

WSGIDaemonProcess tusacam user=pi processes=2 threads=4 python-home=<environment folder> python-path=<app folder>
WSGIProcessGroup tusacam
WSGIScriptAlias / <app folder>/tusacam/wsgi.py process-group=tusacam

Alias /robots.txt <app folder>/static/robots.txt
Alias /favicon.ico <app folder>/static/favicon.ico
Alias /static <app folder>/collectstatic

<Directory <app folder>/collectstatic>
	Require all granted
</Directory>

<Directory <app folder>/tusacam>
	<Files wsgi.py>
		Require all granted
	</Files>
</Directory>
```

Open your apache2 service configuration with 
`sudo vim /lib/systemd/system/apache2.service` and in the `[Service]` 
section add the line

```
Environment=DJANGO_SECRET_KEY=<your secret key>
```

## Set up the camera server to run as a service using sytemd

Execute on a console

```
sudo nano /lib/systemd/system/tusacam.service
```

Type the following and exit nano saving changes:

```
[Unit]
Description=Tusacam service
After=multi-user.target

[Service]
Environment=DJANGO_SECRET_KEY=<your secret key>
WorkingDirectory=<app folder>
ExecStart=<environment folder>/bin/python manage.py camera_server
Type=idle

[Install]
WantedBy=multi-user.target
```

Now run the command

```
sudo systemctl enable tusacam.service
```

To manually start the service do a 

```
sudo systemctl start tusacam.service
```
## Testing and adjusting the hardware

At this point you should be able to access the web app from the 
```http://<your IP IP address>/browse``` URL from any device in your 
network. You should be able to see if it is working by moving something 
in from of the motion sensor. If all goes well you should be able to
see a live preview of the camera and see/change the storage policies.

You may want to adjust to trigger delay and range of the motion sensor
using its two dials, I found a nice explanation 
[here](http://qqtrading.com.my/pir-motion-sensor-module-hc-sr501)

## Making the Pi IP address fixed

Depending on your Pi model, you may have many different network 
interfaces available to connect your Pi to your home network. Plus, in
my case, I have a WiFi dongle with extra sized antennas to use in my 
home for places where the WiFi signal is weak and I do not want to use
a repeater or similar device.

Having your Pi in different IP addresses is a problem if you plan to
make it available over the internet, as if you have a domestic router
your only chance of being able to access something inside your home
network from the internet is to place a rule in your home router that
diverts incoming traffice from a certain port to a specific IP address
inside your network. Thus, that IP address inside your network has
to remain constant no matter how you connect your Pi to your home
network (wireless or cable)

I'm including these steps as it has been one of the most frustrating
parts of the entire setup. Apparently, the latest Raspberry version
is ok with using the same IP address for many interfaces and is just 
able to use this simple setup in the `/etc/dhcpcd.conf` for
each network interface (eth0, wlan0, wlan1, etc)

```
interface <interface name>
ipv4only
noipv6rs
nodhcp
static ip_address=<your fixed IP address>/24
static routers=<your router IP>
static domain_name_servers=<your domain name servers>

```
