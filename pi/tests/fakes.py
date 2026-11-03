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


class FakeSink:
    def __init__(self):
        self.records = []

    @property
    def commands(self):
        return [r.command for r in self.records]

    def send(self, record):
        self.records.append(record)
        return True
