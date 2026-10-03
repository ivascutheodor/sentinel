import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from recorder import IncidentRecorder  # noqa: E402


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
    assert rec.close() is not None
    assert writers[0].released
