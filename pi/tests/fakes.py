class FakeRepository:
    def __init__(self, fail=False):
        self.fail = fail
        self.commands = []
        self.gesture_batches = []

    def save_command(self, record):
        if self.fail:
            raise ConnectionError("db down")
        self.commands.append(record)

    def save_gestures(self, records):
        if self.fail:
            raise ConnectionError("db down")
        self.gesture_batches.append(list(records))


class FakePlayer:
    def __init__(self):
        self.commands = []

    def execute(self, command):
        self.commands.append(command)
        return True
