import json
import base64
import struct

from maxcube.device import \
    MaxDevice, \
    MAX_CUBE, \
    MAX_THERMOSTAT, \
    MAX_THERMOSTAT_PLUS, \
    MAX_WINDOW_SHUTTER, \
    MAX_WALL_THERMOSTAT, \
    MAX_DEVICE_MODE_AUTOMATIC, \
    MAX_DEVICE_MODE_MANUAL, \
    MAX_DEVICE_MODE_VACATION, \
    MAX_DEVICE_BATTERY_OK, \
    MAX_DEVICE_BATTERY_LOW
from maxcube.room import MaxRoom
from maxcube.thermostat import MaxThermostat
from maxcube.wallthermostat import MaxWallThermostat
from maxcube.windowshutter import MaxWindowShutter
import logging

logger = logging.getLogger(__name__)

CMD_SET_PROG = "10"
UNKNOWN = "00"
RF_FLAG_IS_ROOM = "04"
RF_FLAG_IS_DEVICE = "00"
RF_NULL_ADDRESS = "000000"
DAYS = ['saturday', 'sunday', 'monday', 'tuesday', 'wednesday', 'thursday',
        'friday', 'saturday', 'sunday']
MODES = ['auto', 'manu', 'vacation', 'boost']


class MaxCube(MaxDevice):
    def __init__(self, connection):
        super(MaxCube, self).__init__()
        self.connection = connection
        self.name = 'Cube'
        self.type = MAX_CUBE
        self.firmware_version = None
        self.duty_cycle = None
        self.command_result = None
        self.memory_slots = None
        self.devices = []
        self.rooms = []
        self.init()

    def init(self):
        self.connect() # get H and C message
        self.update()  # get L message
        self.log()

    def log(self):
        logger.info('Cube (rf=%s, firmware=%s)' % (self.rf_address, self.firmware_version))
        for room in self.rooms:
            logger.info('Room (id=%s, name=%s, group_rf=%s' % (room.id, room.name, room.group_rf_address))
            
            for device in self.devices_by_room(room):
                if device.is_thermostat():
                    log_string = 'Thermostat ('
                    log_string += 'type=' + str(device.type)
                    log_string += ', rf=' + device.rf_address
                    log_string += ', serial=' + device.serial
                    log_string += ', firmware=' + device.firmware
                    log_string += ', name=' + device.name
                    log_string += ', room=' + str(device.room_id)
                    log_string += ', initialized=' + str(device.initialized)
                    log_string += ', battery=' + str(device.battery)
                    log_string += ', comfort temp=' + str(device.comfort_temperature)
                    log_string += ', eco temp=' + str(device.eco_temperature)
                    log_string += ', min temp=' + str(device.min_temperature)
                    log_string += ', max temp=' + str(device.max_temperature)
                    log_string += ', temp offset=' + str(device.temperature_offset)
                    log_string += ', max valve=' + str(device.max_valve_setting)
                    log_string += ', valve offset=' + str(device.valve_offset)
                    log_string += ', window open temp=' + str(device.window_open_temperature)
                    log_string += ', window open duration=' + str(device.window_open_duration)
                    log_string += ', boost duration=' + str(device.boost_duration)
                    log_string += ', boost valve pos=' + str(device.boost_valve_position)
                    log_string += ', decalcification=' + device.decalcification
                    log_string += ', locked=' + str(device.locked)
                    log_string += ', mode=' + MODES[device.mode]
                    if device.mode == MAX_DEVICE_MODE_VACATION:
                        log_string += ' until ' + device.vacation_until
                    log_string += ', target temp=' + str(device.target_temperature)
                    if device.actual_temperature is not None:
                        log_string += ', actual temp=' + str(device.actual_temperature)
                    if device.valve_position is not None:
                        log_string += ', valve pos=' + str(device.valve_position)
                    log_string += ')'

                    logger.info(log_string)
                elif device.is_wallthermostat():
                    log_string = 'WallThermostat ('
                    log_string += 'type=' + str(device.type)
                    log_string += ', rf=' + device.rf_address
                    log_string += ', serial=' + device.serial
                    log_string += ', firmware=' + device.firmware
                    log_string += ', name=' + device.name
                    log_string += ', room=' + str(device.room_id)
                    log_string += ', initialized=' + str(device.initialized)
                    log_string += ', battery=' + str(device.battery)
                    log_string += ', comfort temp=' + str(device.comfort_temperature)
                    log_string += ', eco temp=' + str(device.eco_temperature)
                    log_string += ', min temp=' + str(device.min_temperature)
                    log_string += ', max temp=' + str(device.max_temperature)
                    log_string += ', locked=' + str(device.locked)
                    log_string += ', mode=' + MODES[device.mode]
                    if device.mode == MAX_DEVICE_MODE_VACATION:
                        log_string += ' until ' + device.vacation_until
                    log_string += ', target temp=' + str(device.target_temperature)
                    if device.actual_temperature is not None:
                        log_string += ', actual temp=' + str(device.actual_temperature)
                    log_string += ')'

                    logger.info(log_string)
                elif device.is_windowshutter():
                    log_string = 'WindowShutter ('
                    log_string += 'type=' + str(device.type)
                    log_string += ', rf=' + device.rf_address
                    log_string += ', serial=' + device.serial
                    log_string += ', firmware=' + device.firmware
                    log_string += ', name=' + device.name
                    log_string += ', room=' + str(device.room_id)
                    log_string += ', initialized=' + str(device.initialized)
                    log_string += ', battery=' + str(device.battery)
                    log_string += ', is open=' + str(device.is_open)
                    log_string += ')'

                    logger.info(log_string)
                else:
                    logger.info('Device (rf=%s, name=%s' % (device.rf_address, device.name))

    def connect(self):
        self.connection.connect()
        response = self.connection.response
        self.parse_response(response)

    def update(self):
        return self.send_command('l:\r\n')

    def send_command(self, command):
        logger.debug('Sending command: ' + command)
        if self.connection.send(command):
            logger.debug('Command response: ' + self.connection.response)
            response = self.connection.response
            self.parse_response(response)
            if self.command_result > 0:
                logger.error('Command failed: Result=%s, Duty Cycle=%s, Memory Slots=%s' % (self.command_result, self.duty_cycle, self.memory_slots))
                return False
            return True
        else:
            logger.error('Command failed: Connection error')
            return False

    def get_devices(self):
        return self.devices

    def device_by_rf(self, rf):
        for device in self.devices:
            if device.rf_address == rf:
                return device
        return None

    def devices_by_room(self, room):
        devices = []

        for device in self.devices:
            if device.room_id == room.id:
                devices.append(device)

        return devices

    def group_device_by_room(self, room):
        return self.device_by_rf(room.group_rf_address)

    def get_rooms(self):
        return self.rooms

    def room_by_id(self, id):
        for room in self.rooms:
            if room.id == id:
                return room
        return None

    def parse_response(self, response):
        try:
            lines = str.split(str(response), '\n')
        except:
            lines = str.split(response, '\n')

        for line in lines:
            line = line.strip()
            if line and len(line) > 8:
                if line[:1] == 'C':
                    self.parse_c_message(line.strip())
                elif line[:1] == 'H':
                    self.parse_h_message(line.strip())
                elif line[:1] == 'L':
                    self.parse_l_message(line.strip())
                elif line[:1] == 'M':
                    self.parse_m_message(line.strip())
                elif line[:1] == 'S':
                    self.parse_s_message(line.strip())
                else:
                    logger.warning(line[:1] + '-Message not handled by parser: ' + message)

    def parse_c_message(self, message):
        logger.debug('Parsing c_message: ' + message)
        device_rf_address = message[1:].split(',')[0][1:].upper()
        data = bytearray(base64.b64decode(message[2:].split(',')[1]))

        length = data[0]
        rf_address = self.to_hex_string(data[1: 3])
        device_type = data[4]

        device = self.device_by_rf(device_rf_address)

        if device:
            self.set_device_room_id(device, data[5])
            self.set_device_firmware(device, str(data[6] >> 4).zfill(2) + '.' + str(data[6] & 0x0F).zfill(2))
            self.set_device_serial(device, data[8:17].decode('utf-8'))

        # Thermostat or Wall Thermostat
        if device and (device.is_thermostat() or device.is_wallthermostat()):
            self.set_device_comfort_temperature(device, data[18] / 2.0)
            self.set_device_eco_temperature(device, data[19] / 2.0)
            self.set_device_max_temperature(device, data[20] / 2.0)
            self.set_device_min_temperature(device, data[21] / 2.0)
            self.set_device_programme(device, get_programme(data[29:210]))

        # Thermostat
        if device and device.is_thermostat():
            self.set_device_temperature_offset(device, (data[22] / 2.0) - 3.5)
            self.set_device_window_open_temperature(device, data[23] / 2.0)
            self.set_device_window_open_duration(device, data[24] * 5)
            boost_duration = (data[25] & 0xE0) >> 5
            if boost_duration == 7:
                self.set_device_boost_duration(device, 60)
            else:
                self.set_device_boost_duration(device, boost_duration * 5)
            self.set_device_boost_valve_position(device, (data[25] & 0x1F) * 5)
            self.set_device_decalcification(device, DAYS[(data[26] & 0xE0) >> 1] + ' ' + str(data[26] & 0x1F).zfill(2) + ':00')
            self.set_device_max_valve_setting(device, data[27] & 0xFF * 100 / 255)
            self.set_device_valve_offset(device, data[28] & 0xFF * 100 / 255)

    def parse_h_message(self, message):
        logger.debug('Parsing h_message: ' + message)
        tokens = message[2:].split(',')
        self.rf_address = tokens[1]
        self.firmware_version = (tokens[2][0:2]) + '.' + (tokens[2][2:4])

    def parse_m_message(self, message):
        logger.debug('Parsing m_message: ' + message)
        data = bytearray(base64.b64decode(message[2:].split(',')[2]))
        num_rooms = data[2]

        pos = 3
        for _ in range(0, num_rooms):
            room_id = struct.unpack('bb', data[pos:pos + 2])[0]
            name_length = struct.unpack('bb', data[pos:pos + 2])[1]
            pos += 1 + 1
            name = data[pos:pos + name_length].decode('utf-8')
            pos += name_length
            group_rf_address = self.to_hex_string(data[pos: pos + 3])
            pos += 3

            room = self.room_by_id(room_id)

            if not room:
                room = MaxRoom()

                if room:
                    room.id = room_id
                    self.rooms.append(room)

            if room:
                room.name = name
                room.group_rf_address = group_rf_address

        num_devices = data[pos]
        pos += 1

        for device_idx in range(0, num_devices):
            device_type = data[pos]
            device_rf_address = self.to_hex_string(data[pos + 1: pos + 1 + 3])
            device_serial = data[pos + 4: pos + 14].decode('utf-8')
            device_name_length = data[pos + 14]
            device_name = data[pos + 15: pos + 15 + device_name_length].decode('utf-8')
            room_id = data[pos + 15 + device_name_length]

            device = self.device_by_rf(device_rf_address)

            if not device:
                if device_type == MAX_THERMOSTAT or device_type == MAX_THERMOSTAT_PLUS:
                    device = MaxThermostat()

                if device_type == MAX_WINDOW_SHUTTER:
                    device = MaxWindowShutter()

                if device_type == MAX_WALL_THERMOSTAT:
                    device = MaxWallThermostat()

                if device:
                    self.devices.append(device)

            if device:
                device.type = device_type
                device.rf_address = device_rf_address
                device.room_id = room_id
                device.name = device_name
                device.serial = device_serial

            pos += 1 + 3 + 10 + device_name_length + 2

    def parse_l_message(self, message):
        logger.debug('Parsing l_message: ' + message)
        data = bytearray(base64.b64decode(message[2:]))
        pos = 0

        while pos < len(data):
            length = data[pos]
            device_rf_address = self.to_hex_string(data[pos + 1: pos + 4])
            flags = data[pos + 5: pos + 7]
            bits1, bits2 = struct.unpack('BB', flags)

            device = self.device_by_rf(device_rf_address)

            if device:
                self.set_device_initialized(device, (bits1 & 0x02) >> 1)
                self.set_device_battery(device, bits2 >> 7)

            # Thermostat or Wall Thermostat
            if device and (device.is_thermostat() or device.is_wallthermostat()):
                self.set_device_target_temperature(device, (data[pos + 8] & 0x7F) / 2.0)
                self.set_device_locked(device, (bits2 & 0x20) >> 5)
                self.set_device_mode(device, bits2 & 0x03)
                if device.mode == MAX_DEVICE_MODE_VACATION:
                    if (data[pos + 11] & 0x01) == 0:
                        minutes_until = '00'
                    else:
                        minutes_until = '30'
                    self.set_device_vacation_until(device, '20' + str(data[pos + 10] & 0x1F).zfill(2)
                                                  + '-' + str(((data[pos + 9] & 0xE0) >> 4) + ((data[pos + 10] & 0x40) >> 6)).zfill(2)
                                                  + '- ' + str(data[pos + 9] & 0x1F).zfill(2)
                                                  + ' ' + str((data[pos + 11] & 0xFF) >> 1).zfill(2)
                                                  + ':' + minutes_until)
                else:
                    self.set_device_vacation_until(device, None)

            # Thermostat
            if device and device.is_thermostat():
                if device.mode == MAX_DEVICE_MODE_MANUAL or device.mode == MAX_DEVICE_MODE_AUTOMATIC:
                    actual_temperature = ((data[pos + 9] & 0xFF) * 256 + (data[pos + 10] & 0xFF)) / 10.0
                    if actual_temperature != 0:
                        self.set_device_actual_temperature(device, actual_temperature)
                else:
                    self.set_device_actual_temperature(device, None)
                self.set_device_valve_position(device, data[pos + 7])

            # Wall Thermostat
            if device and device.is_wallthermostat():
                self.set_device_actual_temperature(device, (((data[pos + 8] & 0x80) << 1) + data[pos + 12]) / 10.0)

            # Window Shutter
            if device and device.is_windowshutter():
                self.set_device_is_open(device, (bits2 & 0x02) >> 1)

            # Advance our pointer to the next submessage
            pos += length + 1

    def parse_s_message(self, message):
        logger.debug('Parsing s_message: ' + message)
        tokens = message[2:].split(',')
        self.duty_cycle = int(tokens[0], 16)
        self.command_result = int(tokens[1])
        self.memory_slots = int(tokens[2], 16)

    def set_target_temperature(self, thermostat, temperature):
        if not thermostat.is_thermostat() and not thermostat.is_wallthermostat():
            logger.error('%s is no (wall-)thermostat!', thermostat.rf_address)
            return

        self.set_temperature_mode(thermostat, temperature, thermostat.mode)

    def set_mode(self, thermostat, mode):
        if not thermostat.is_thermostat() and not thermostat.is_wallthermostat():
            logger.error('%s is no (wall-)thermostat!', thermostat.rf_address)
            return

        self.set_temperature_mode(thermostat, thermostat.target_temperature, mode)

    def set_temperature_mode(self, thermostat, temperature, mode):
        logger.debug('Setting temperature %s and mode %s on %s!', temperature, mode, thermostat.rf_address)

        if not thermostat.is_thermostat() and not thermostat.is_wallthermostat():
            logger.error('%s is no (wall-)thermostat!', thermostat.rf_address)
            return True

        rf_address = thermostat.rf_address
        room = str(thermostat.room_id).zfill(2)
        target_temperature = int(temperature * 2) + (mode << 6)

        byte_cmd = '000440000000' + rf_address + room + to_hex(target_temperature)
        logger.debug('Request: ' + byte_cmd)
        command = 's:' + base64.b64encode(bytearray.fromhex(byte_cmd)).decode('utf-8') + '\r\n'
        if self.send_command(command):
            self.set_device_target_temperature(thermostat, int(temperature * 2) / 2.0)
            self.set_device_mode(thermostat, mode)
            return True
        return False

    def set_programme(self, thermostat, day, metadata):
        made_changes = False
        heat_time_tuples = [
            (x["temp"], x["until"]) for x in metadata]
        # pad heat_time_tuples so that there are always seven
        for _ in range(7 - len(heat_time_tuples)):
            heat_time_tuples.append((0, "00:00"))
        command = ""
        if thermostat.is_room():
            rf_flag = RF_FLAG_IS_ROOM
#            devices = self.cube.devices_by_room(thermostat)
            devices = [self.device_by_rf(thermostat.group_rf_address)]
        else:
            rf_flag = RF_FLAG_IS_DEVICE
            devices = [thermostat]
        command += UNKNOWN + rf_flag + CMD_SET_PROG + RF_NULL_ADDRESS
        for device in devices:
            # compare with current programme
            if device.programme[day] != metadata:
                command += device.rf_address
                command += to_hex(device.room_id)
                command += to_hex(n_from_day_of_week(day))
                for heat, time in heat_time_tuples:
                    command += temp_and_time(heat, time)
                device.programme[day] = metadata
                logger.debug('Setting program for %s: %s' % (day, metadata))
                made_changes = True
            else:
                logger.debug('Skipping program for %s (unchanged)' % (day))
        logger.debug('Request: ' + command)
        command = 's:' + base64.b64encode(
            bytearray.fromhex(command)).decode('utf-8') + '\r\n'
        if made_changes:
            return self.send_command(command)
        else:
            return True

    def devices_as_json(self):
        devices = []
        for device in self.devices:
            devices.append(device.to_dict())
        return json.dumps(devices, indent=2)

    def set_programmes_from_config(self, config_file):
        config = json.load(config_file)
        for device_config in config:
            device = self.device_by_rf(device_config['rf_address'])
            programme = device_config['programme']
            if not programme:
                # e.g. a wall thermostat
                continue
            for day, metadata in programme.items():
                if not self.set_programme(device, day, metadata):
                    return False
        return True

    @classmethod
    def to_hex_string(cls, address):
        return ''.join('{:02X}'.format(x) for x in address)

    def set_device_room_id(self, device, value):
        if device.room_id != value:
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed before id update')
            self.room_id = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed after id update')
        
    def set_device_rf_address(self, device, value):
        device.rf_address = value

    def set_device_type(self, device, value):
        device.type = value

    def set_device_room_id(self, device, value):
        device.room_id = value

    def set_device_firmware(self, device, value):
        device.firmware = value

    def set_device_serial(self, device, value):
        device.serial = value

    def set_device_name(self, device, value):
        device.name = value

    def set_device_initialized(self, device, value):
        if device.initialized != value:
            device.initialized = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on initialized update')

    def set_device_battery(self, device, value):
        if device.battery != value:
            device.battery = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on battery update')

    def set_device_comfort_temperature(self, device, value):
        if device.comfort_temperature != value:
            device.comfort_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on comfort temperature update')
        
    def set_device_eco_temperature(self, device, value):
        if device.eco_temperature != value:
            device.eco_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on eco temperature update')

    def set_device_max_temperature(self, device, value):
        if device.max_temperature != value:
            device.max_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on max temperature update')

    def set_device_min_temperature(self, device, value):
        if device.min_temperature != value:
            device.min_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on min temperature update')

    def set_device_programme(self, device, value):
        if device.programme != value:
            device.programme = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on program update')

    def set_device_target_temperature(self, device, value):
        if device.target_temperature != value:
            device.target_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on target temperature update')

    def set_device_actual_temperature(self, device, value):
        if device.actual_temperature != value:
            device.actual_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on actual temperature update')

    def set_device_locked(self, device, value):
        if device.locked != value:
            device.locked = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on locked update')

    def set_device_mode(self, device, value):
        if device.mode != value:
            device.mode = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on mode update')

    def set_device_vacation_until(self, device, value):
        if device.vacation_until != value:
            device.vacation_until = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on vacation until update')

    def set_device_temperature_offset(self, device, value):
        if device.temperature_offset != value:
            device.temperature_offset = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on temperature offset update')

    def set_device_window_open_temperature(self, device, value):
        if device.window_open_duration != value:
            device.window_open_duration = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on window open temperature update')

    def set_device_window_open_duration(self, device, value):
        if device.window_open_temperature != value:
            device.window_open_temperature = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on window open duration update')

    def set_device_boost_duration(self, device, value):
        if device.boost_duration != value:
            device.boost_duration = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on boost duration update')

    def set_device_boost_valve_position(self, device, value):
        if device.boost_valve_position != value:
            device.boost_valve_position = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on boost valve position update')

    def set_device_decalcification(self, device, value):
        if device.decalcification != value:
            device.decalcification = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on decalcification update')

    def set_device_max_valve_setting(self, device, value):
        if device.max_valve_setting != value:
            device.max_valve_setting = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on max valve setting update')

    def set_device_valve_offset(self, device, value):
        if device.valve_offset != value:
            device.valve_offset = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on valve offset update')

    def set_device_valve_position(self, device, value):
        if device.valve_position != value:
            device.valve_position = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on valve position update')

    def set_device_is_open(self, device, value):
        if device.is_open != value:
            device.is_open = value
            try:
                self.room_by_id(device.room_id).set_changed()
            except:
                logger.error('Error while marking room ' + str(device.room_id) + ' changed on window open state update')

def get_programme(bits):
    n = 26
    programme = {}
    days = [bits[i:i + n] for i in range(0, len(bits), n)]
    for j, day in enumerate(days):
        n = 2
        settings = [day[i:i + n] for i in range(0, len(day), n)]
        day_programme = []
        for setting in settings:
            word = format(setting[0], "08b") + format(setting[1], "08b")
            temp = int(word[:7], 2) / 2.0
            time_mins = int(word[7:], 2) * 5
            mins = time_mins % 60
            hours = int((time_mins - mins) / 60)
            time = "{:02d}:{:02d}".format(hours, mins)
            day_programme.append({"temp": temp, "until": time})
            if time == "24:00":
                # This appears to flag the end of useable set points
                break
        programme[day_of_week_from_n(j)] = day_programme
    return programme


def n_from_day_of_week(day):
    return DAYS.index(day)


def day_of_week_from_n(day):
    return DAYS[day]


def temp_and_time(temp, time):
    temp = float(temp)
    assert temp <= 32, "Temp must be 32 or lower"
    assert temp % 0.5 == 0, "Temp must be increments of 0.5"
    temp = int(temp * 2)
    hours, mins = [int(x) for x in time.split(":")]
    assert mins % 5 == 0, "Time must be a multiple of 5 mins"
    mins = hours * 60 + mins
    bits = format(temp, "07b") + format(int(mins/5), "09b")
    return to_hex(int(bits, 2))


def to_hex(value):
    "Return value as hex word"
    return format(value, "02x")
