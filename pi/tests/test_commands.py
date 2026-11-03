import json

from receiver.commands import MqttCommandPublisher, command_payload
from receiver.storage import CommandRecord


class FakeInfo:
    def __init__(self, rc):
        self.rc = rc


class FakeClient:
    def __init__(self, connected=True, rc=0):
        self.connected = connected
        self.rc = rc
        self.published = []

    def is_connected(self):
        return self.connected

    def publish(self, topic, payload, qos, retain):
        self.published.append((topic, payload, qos, retain))
        return FakeInfo(self.rc)


def test_payload_format():
    data = json.loads(command_payload(CommandRecord("pause", "five", 1793679259.6512)))
    assert data == {"command": "pause", "label": "five", "ts": 1793679259.65}


def test_publishes_qos1_without_retain():
    client = FakeClient()
    assert MqttCommandPublisher(client, "air-dj/commands").send(CommandRecord("next", "one", 1.0)) is True
    topic, payload, qos, retain = client.published[0]
    assert (topic, qos, retain) == ("air-dj/commands", 1, False)
    assert json.loads(payload)["command"] == "next"


def test_disconnected_drops_instead_of_queueing():
    client = FakeClient(connected=False)
    assert MqttCommandPublisher(client, "t").send(CommandRecord("play", "ok", 1.0)) is False
    assert client.published == []


def test_publish_error_returns_false():
    assert MqttCommandPublisher(FakeClient(rc=4), "t").send(CommandRecord("play", "ok", 1.0)) is False
