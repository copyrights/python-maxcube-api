#! /usr/bin/python
from datetime import datetime
from maxcube.connection import MaxCubeConnection
from maxcube.cube import MaxCube, DAYS
from maxcube.device import \
    MAX_DEVICE_MODE_AUTOMATIC, \
    MAX_DEVICE_MODE_MANUAL, \
    MAX_DEVICE_MODE_BOOST
import paho.mqtt.client as mqtt
import logging
import json
import time
import sys

DAY_COMFORT_BEGIN = 700
DAY_COMFORT_END = 1800

MAX_DEVICE_MODE_HOME = 4

PUBLISH_ONLY_CHANGES = 0
PUBLISH_ALL = 1

# INIT LOGGER
FORMAT = '%(asctime)-15s %(levelname)s %(name)s [%(funcName)s] %(message)s'
LOGFILE = "/home/pi/eq3/maxcubed.log"
#logging.basicConfig(filename=LOGFILE, format=FORMAT, level=logging.DEBUG)
logging.basicConfig(filename=LOGFILE, format=FORMAT, level=logging.INFO)
logger=logging.getLogger(__name__)

# INIT CUBE
#try:
cube = MaxCube(MaxCubeConnection('192.168.0.16', 62910))
#except:
#  logger.error("Could not initialize cube. Exiting")
#  exit()
logger.info("Cube initialized")

# INIT MQTT
success = False
while not success:
  try:
    client = mqtt.Client("maxcubed")
    success = True
  except:
    logger.warning("Could not connect to MQTT. Will retry")
    time.sleep(5)
logger.info("MQTT initialized")

# INIT TODO LIST
todo_list = []
todo_list_updated = 0
todo_list_lockedby = 0


def cube_update():
  try:
    cube.update()
  except:
    logger.warning("Could not connect to cube")


def publish(scope):
  cube_max_valve_position = 0
  cube_open_valve_position = 0
  cube_total_valve_position = 0
  cube_sum_valve_position = 0
  published = False

  
  for room in cube.rooms:
    has_thermostat = False
    room_actual_temperature = None
    room_battery = None
    room_valve_position = None
    room_is_open = None

    payload = "{ \"room_id\": \""+str(room.id)+"\""
    payload += ", \"room_name\": \""+room.name+"\""

    for device in cube.devices_by_room(room):
      if device.is_thermostat() or device.is_wallthermostat():
        if not has_thermostat:
          has_thermostat = True
          room_target_temperature = device.target_temperature
          room_mode = device.mode
        else:
          if device.target_temperature > room_target_temperature:
            room_target_temperature = device.target_temperature
            if room_mode != MAX_DEVICE_MODE_BOOST:
              room_mode = device.mode
          if device.mode == MAX_DEVICE_MODE_BOOST:
            room_mode = device.mode

        if device.actual_temperature is not None:
          if room_actual_temperature is None:
            room_actual_temperature = device.actual_temperature
          else:
            room_actual_temperature = min(room_actual_temperature, device.actual_temperature)

        if device.battery is not None:
          if room_battery is None:
            room_battery = device.battery
          else:
            room_battery = max(room_battery, device.battery)

        if device.valve_position is not None:
          cube_max_valve_position = max(cube_max_valve_position, device.valve_position)
          cube_sum_valve_position += device.valve_position
          cube_total_valve_position += 1
          if device.valve_position > 0:
            cube_open_valve_position += 1
          if room_valve_position is None:
            room_valve_position = device.valve_position
          else:
            room_valve_position = max(room_valve_position, device.valve_position)

      if device.is_windowshutter():
        if room_is_open is None:
          room_is_open = device.is_open
        else:
          room_is_open = max(room_is_open, device.is_open)

    if has_thermostat:
#      if room.day_comfort and (room_mode != MAX_DEVICE_MODE_MANUAL):
#        room.day_comfort = False
      if room.day_comfort and (room_mode != MAX_DEVICE_MODE_BOOST):
        room_mode = MAX_DEVICE_MODE_HOME
      payload += ", \"mode\": \""+str(room_mode)+"\""

      if room_target_temperature == 4.5:
        room_target_temperature = "OFF"
      payload += ", \"target_temperature\": \""+str(room_target_temperature)+"\""

      if room_actual_temperature is not None:
        payload += ", \"actual_temperature\": \""+str(room_actual_temperature)+"\""

      if room_battery is not None:
        payload += ", \"battery\": \""+str(room_battery)+"\""

      if room_valve_position is not None:
        payload += ", \"valve_pos\": \""+str(room_valve_position)+"\""

    if room_is_open is not None:
      payload += ", \"is_open\": \""+str(room_is_open)+"\""
    payload += " }"

    if scope == PUBLISH_ALL:
      topic = "eq3/maxcube/room/"+str(room.id)
      client.publish(topic, payload, 1)
      logger.debug('MQTT sent - topic %s payload %s' % (topic, payload))
      published = True

    if scope == PUBLISH_ONLY_CHANGES and room.get_changed():
      topic = "eq3/maxcube/room/"+str(room.id)
      client.publish(topic, payload, 1)
      logger.info('MQTT sent - topic %s payload %s' % (topic, payload))
      published = True

  if published:
    payload = "{ \"open_valves\": \""+str(cube_open_valve_position)+"\""
    payload += ", \"max_valve_pos\": \""+str(cube_max_valve_position)+"\""
    payload += ", \"mean_valve_pos\": \""+str(cube_sum_valve_position/max(cube_total_valve_position,1))+"\""
    if cube.duty_cycle is not None:
      payload += ", \"duty_cycle\": "+str(cube.duty_cycle)
    if cube.memory_slots is not None:
      payload += ", \"memory_slots\": "+str(cube.memory_slots)
    payload += " }"
    topic = "eq3/maxcube/global"
    client.publish(topic, payload, 1)
    if scope == PUBLISH_ONLY_CHANGES:
      logger.info('MQTT sent - topic %s payload %s' % (topic, payload))
    else:
      logger.debug('MQTT sent - topic %s payload %s' % (topic, payload))


def numeric_time():
  return int(datetime.now().strftime("%H%M"))


def on_mqtt_connect(client, userdata, flags, rc):
  if rc==0:
    client.connected_flag=True #set flag
    logger.info("MQTT status - connected OK")
    publish(PUBLISH_ALL)
  else:
    logger.error("MQTT status - bad connection returned code=",rc)


def on_mqtt_message(mosq, obj, msg):
  topic=msg.topic.split('/')
  object_type=topic[3]
  object_id=topic[4]
  action=topic[5]
  value=msg.payload
  logger.info('MQTT recv - topic %s payload %s' % (msg.topic, msg.payload))
  logger.debug("  REQUEST: Change "+action+" of "+object_type+" "+object_id+" to "+value)

  if object_type == "room":
    device = cube.group_device_by_room(cube.room_by_id(int(object_id)))
    logger.debug("    Affects device: "+device.rf_address)

  if object_type == "device":
    device = cube.device_by_rf(object_id)

  if action == "temperature":
    if value == "eco":
      target = device.eco_temperature
    elif value == "comfort":
      target = device.comfort_temperature
    elif value == "OFF":
      target = 4.5
    else:
      target = float(value)
    todo_list_add (device, action, target)
  
  if action == "mode":
    if int(value) == MAX_DEVICE_MODE_HOME:
      cube.room_by_id(device.room_id).day_comfort = True
      handle_day_comfort(device)
    else:
      if int(value) != MAX_DEVICE_MODE_BOOST:
        cube.room_by_id(device.room_id).day_comfort = False
      todo_list_add (device, action, int(value))

  if action == "program":
    todo_list_add (device, action, value)


def todo_list_lock(originator):
  global todo_list_lockedby

  if todo_list_lockedby == originator:
    return

  logger.debug("TODO list requested by "+str(originator))

  while todo_list_lockedby >0:
    logger.warning("TODO list lock not available for "+str(originator)+" (locked by "+str(todo_list_lockedby)+") - will retry")
    time.sleep (1)
  todo_list_lockedby = originator
  logger.debug("TODO list locked by "+str(todo_list_lockedby))


def todo_list_unlock():
  global todo_list_lockedby

  logger.debug("TODO list released by "+str(todo_list_lockedby))
  todo_list_lockedby = 0


def todo_list_add(device, action, target):
  global todo_list
  global todo_list_updated
  locker_id = 1

  todo_list_lock(locker_id)
  found = False
  
  for todo in todo_list:
    if todo[0] == device and todo[1] == action:
      todo_list_updated = time.time()
      todo[2] = target
      found = True
  
  if not found:
    todo_list_updated = time.time()
    todo_list.append([device, action, target])

  logger.debug("  TODO list: "+str(todo_list))

  todo_list_unlock()
  

def todo_list_process():
  global todo_list
  global todo_list_updated
  locker_id = 2

  todo_list_lock(locker_id)

  logger.debug("Processing todo list")
  for todo in todo_list:
    device = todo[0]
    action = todo[1]
    target = todo[2]

    if action == "temperature":
      target_temp = target
      if target_temp < 5:
        target_mode = MAX_DEVICE_MODE_MANUAL
      else:
        target_mode = device.mode

      logger.info("Setting temp/mode for "+cube.room_by_id(device.room_id).name+"/"+device.name+" from "+str(device.target_temperature)+"/"+str(device.mode)+" to "+str(target_temp)+"/"+str(target_mode))
      if target_temp != device.target_temperature or target_mode != device.mode:
        try:
          if not cube.set_temperature_mode(device, target_temp, target_mode):
            logger.error("Error setting temp/mode for "+cube.room_by_id(device.room_id).name+"/"+device.name+" from "+str(device.target_temperature)+"/"+str(device.mode)+" to "+str(target_temp)+"/"+str(target_mode))
            todo_list_updated = time.time()
            todo_list_unlock()
            return
        except:
          logger.error("Cube error: "+str(sys.exc_info()[0]))
          todo_list_updated = time.time()
          todo_list_unlock()
          return

    if action == "mode":
      target_mode = target
      if target_mode == MAX_DEVICE_MODE_AUTOMATIC:
        target_temp = 0 # get temperature from daily program
      else:
        target_temp = device.target_temperature
          
      logger.info("Setting temp/mode for "+cube.room_by_id(device.room_id).name+"/"+device.name+" from "+str(device.target_temperature)+"/"+str(device.mode)+" to "+str(target_temp)+"/"+str(target_mode))
      if target_temp != device.target_temperature or target_mode != device.mode:
        try:
          if not cube.set_temperature_mode(device, target_temp, target_mode):
            logger.error("Error setting temp/mode for "+cube.room_by_id(device.room_id).name+"/"+device.name+" from "+str(device.target_temperature)+"/"+str(device.mode)+" to "+str(target_temp)+"/"+str(target_mode))
            todo_list_updated = time.time()
            todo_list_unlock()
            return
        except:
          logger.error("Cube error: "+str(sys.exc_info()[0]))
          todo_list_updated = time.time()
          todo_list_unlock()
          return

    if action == "program":
      config_file = "/home/pi/eq3/programs/prog_"+target+".json"
      programme = json.load(open(config_file,'r'))
      logger.info("Setting program "+target+" for "+cube.room_by_id(device.room_id).name+"/"+device.name)
      for day, metadata in programme.items():
        if device.is_thermostat():
          try:
            if not cube.set_programme(device, day, metadata):
              logger.error("Error sending program file "+config_file+" to "+cube.room_by_id(device.room_id).name+"/"+device.name)
              todo_list_updated = time.time()
              todo_list_unlock()
              return
          except:
            logger.error("Cube error: "+str(sys.exc_info()[0]))
            todo_list_updated = time.time()
            todo_list_unlock()
            return

  todo_list = []
  todo_list_unlock()


def todo_list_verify():
  if len(todo_list) > 0 and ((time.time() - todo_list_updated) > 2):
    todo_list_process()


def handle_day_comfort(device):
  current_time = numeric_time()
  if current_time >= DAY_COMFORT_BEGIN and current_time < DAY_COMFORT_END:
    logger.info("activating home mode")
    todo_list_add (device, "mode", MAX_DEVICE_MODE_MANUAL)
    todo_list_add (device, "temperature", device.comfort_temperature)
  else:
    logger.info("deactivating home mode")
    todo_list_add (device, "mode", MAX_DEVICE_MODE_AUTOMATIC)
  

if __name__ == "__main__":
  lastUpdateTime = 0
  lastPublishTime = 0
  lastActionTime = 0
  client.username_pw_set(username="<my_MQTT_user>",password="<my_MQTT_password>")
  client.on_connect = on_mqtt_connect
  client.on_message = on_mqtt_message
  client.connect("<my_MQTT_server>", 1883, 60)
  client.subscribe("eq3/maxcube/set/#", 0)

  client.loop_start()

  current_time = numeric_time()

  while True :
    previous_time = current_time
    current_time = numeric_time()
    if (previous_time < DAY_COMFORT_BEGIN and current_time >= DAY_COMFORT_BEGIN) or (previous_time < DAY_COMFORT_END and current_time >= DAY_COMFORT_END):
      for room in cube.rooms:
        if room.day_comfort:
          handle_day_comfort(cube.group_device_by_room(room))

    if (time.time() - lastUpdateTime) > 1:
      lastUpdateTime = time.time()
      cube_update()
      publish(PUBLISH_ONLY_CHANGES)

    if (time.time() - lastPublishTime) > 300:
      lastPublishTime = time.time()
      publish(PUBLISH_ALL)

    if (time.time() - lastActionTime) > 1:
      lastActionTime = time.time()
      todo_list_verify()

    time.sleep(.1)

  client.loop_stop()
