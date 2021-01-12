class MaxRoom(object):
    def __init__(self):
        self.id = None
        self.name = None
        self.group_rf_address = None
        self.has_changed = False
        self.day_comfort = False

    def is_room(self):
        return True

    def set_changed(self):
        self.has_changed = True

    def get_changed(self):
        value = self.has_changed
        self.has_changed = False
        return value
    
