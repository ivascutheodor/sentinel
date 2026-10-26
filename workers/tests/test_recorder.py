import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from recorder import IncidentRecorder  # noqa: E402

T0 = datetime(2026, 1, 1, tzinfo=UTC)


class FakeClock:
    """Each call is one second later, so frame i is processed at T0 + i seconds."""

    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return T0 + timedelta(seconds=self.calls - 1)


class FakeWriter:
    def __init__(self):
        self.frames = []
        self.released = False

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.released = True


def make_recorder(tmp_path, pre=3, post=2, presence=2):
    writers = []

    def factory(path):
        writers.append(FakeWriter())
        return writers[-1]

    return IncidentRecorder(factory, tmp_path, pre, post, presence), writers


def test_brief_presence_does_not_record(tmp_path):
    rec, writers = make_recorder(tmp_path)
    for i, present in enumerate([False, True, False, False]):
        rec.update(i, present)
    assert not writers


def test_records_with_pre_and_post_roll(tmp_path):
    rec, writers = make_recorder(tmp_path)
    presence = [False, False, False, True, True, True, False, False, False, False]
    results = [rec.update(i, p) for i, p in enumerate(presence)]
    # starts on frame 4 (2nd frame in a row), flushes the 3 buffered frames 2,3,4
    # then writes frame 5, and 2 post-roll frames 6,7; frame 8 closes the clip
    assert writers[0].frames == [2, 3, 4, 5, 6, 7]
    assert writers[0].released
    assert results[8] is not None
    assert not rec.is_recording


def test_close_saves_unfinished_clip(tmp_path):
    rec, writers = make_recorder(tmp_path)
    for i in range(3):
        rec.update(i, True)
    incident = rec.close("stream_lost")
    assert incident is not None
    assert incident.end_reason == "stream_lost"
    assert writers[0].released


def test_incident_times(tmp_path):
    rec = IncidentRecorder(lambda path: FakeWriter(), tmp_path, 3, 2, 2, clock=FakeClock())
    presence = [False, False, False, True, True, True, False, False, False, False]
    results = [rec.update(i, p) for i, p in enumerate(presence)]
    incident = results[8]

    def at(seconds):
        return T0 + timedelta(seconds=seconds)

    # same frames as test_records_with_pre_and_post_roll: the file holds frames 2..7
    assert incident.started_at == at(3)  # first frame of the presence streak
    assert incident.last_person_seen_at == at(5)
    assert incident.recorded_start_at == at(2)  # pre-roll goes back one more frame
    assert incident.recorded_end_at == at(7)  # last post-roll frame
    assert incident.closed_at == at(9)  # the clock call in _finish(), after frame 8
    assert incident.end_reason == "person_absent"
