Based on the great work from https://github.com/hackercowboy/python-maxcube-api and https://github.com/Bouni/max-cube-protocol (thanks to you guys)

This is my "quick & dirty" solution to manage Maxcube together with Jeedom, using Jeedom's JMQTT plugin.
This code wasn't intended to be published, so many things are hard-coded and you won't be able to take it over "as is".
Consider it as a basis for your own project. Feel free to enhance, share, etc ...

General principle:
maxcubed: is placed in /etc/init.d to launch the maxcubed.py daemon at startup on a Raspberry Pi (buster)
maxcubed.py: is a deamon that connects to the maxcube and never releases the connection to avoid the factory reset of the cube

The deamon polls the cube every second and publishes changes (if any) in the eq3/maxcube/room/<number> topic.
Then, every 5 minutes it published to the whole status in the same topics.

The deamon subscribes to the eq3/maxcube/set/# topic and accepts following commands:
eq3/maxcube/set/room/<number>/mode {0|1|2|3|4}
eq3/maxcube/set/room/<number>/temperature {eco|comfort|0-30}
eq3/maxcube/set/room/<number>/program program_filename

Note that a new mode "4" has been added to the standard maxcube modes (0=AUTO; 1=MANUAL; 2=VACATION; 3=BOOST)
Mode 4 means "I'm at home", it's kind of mixed mode that does "manual" comfort temperature from 7:00am to 6:00pm, and then returns to AUTO mode.
This is useful during vacation (or lockdown ;))

On my Jeedom widget, I have a temerature "+" button that increases the temp by 0,5°C and a temperature "-" button that decreases the temp by 0,5°C, so when I push "+" to increase the temp from 19°C to 21°C, it sends several messages:
    eq3/maxcube/set/room/3/temperature 19.5
    eq3/maxcube/set/room/3/temperature 20
    eq3/maxcube/set/room/3/temperature 20.5
    eq3/maxcube/set/room/3/temperature 21

Since I don't want to send each of the messages to the device, the deamon adds each task to a "todo list", replacing commands that are of the same type (temperature setting for room N for example). When the todo list has tasks and has not been modified within the last 2 seconds, it is processed (and locked not to accepts new tasks before the end of pocessing). This way, I can press 4 times "+" and have only one changes actually sent to the device.

For setting programs, I use files preset files. My need was to change somme programs every week (kids at home / kids not at home).
Here's an example of a program file:
/home/pi/eq3/programs/prog_kid_not_at_home.json:
{
  "monday": [
    {
      "until": "06:00",
      "temp": 19
    },
    {
      "until": "07:30",
      "temp": 20
    },
    {
      "until": "24:00",
      "temp": 17
    }
  ],
  "tuesday": [
    {
      "until": "24:00",
      "temp": 17
    }
  ],
  "wednesday": [
  ...
  ],
  ...
}
It can then easily be applied with:
eq3/maxcube/set/room/2/program kid_not_at_home

