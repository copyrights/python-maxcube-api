from maxcube.device import MaxDevice


class MaxWallThermostat(MaxDevice):
    def __init__(self):
        super(MaxWallThermostat, self).__init__()
        self.comfort_temperature = None
        self.eco_temperature = None
        self.max_temperature = None
        self.min_temperature = None
        self.programme = None
        self.target_temperature = None
        self.actual_temperature = None
        self.locked = None
        self.mode = None
        self.vacation_until = None  # if mode is vacation: end date in format YYYY-MM-DD hh:mm
