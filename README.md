# BraviaRC Python Package

Installation
------------

-  ``pip3 install git+https://github.com/aparraga/braviarc.git``

About
=====

``BraviaRC`` is a Python library for remote communication with Sony Bravia TVs 2013 and newer
(http://info.tvsideview.sony.net/en_ww/home_device.html#bravia)

Requirements
============

Python 3.3 or 3.4 is required.

Usage
=====

```python

#new instance for TV at 192.168.1.25
braviarc = BraviaRC('192.168.1.25')

#connect to the instance (or register)
pin = '1878'
braviarc.connect(pin, 'my_device_id', 'my device name')

#check connection
if braviarc.is_connected():

  #get playing info
  playing_content = braviarc.get_playing_info()

  #print current playing channel
  print (playing_content.get('title')

  #get volume info
  volume_info = braviarc.get_volume_info()

  #print current volume
  print (volume_info.get('volume'))

  #change channel
  braviarc.play_content(uri)

  #turn off the TV
  braviarc.turn_off()

