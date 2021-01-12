from maxcube.wallthermostat import MaxWallThermostat


class MaxThermostat(MaxWallThermostat):
    def __init__(self):
        super(MaxThermostat, self).__init__()
        self.temperature_offset = None
        self.window_open_temperature = None
        self.window_open_duration = None
        self.boost_duration = None
        self.boost_valve_position = None
        self.decalcification = None
        self.max_valve_setting = None
        self.valve_offset = None
        self.valve_position = None
