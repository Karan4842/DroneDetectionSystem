import pytest
from tracker import CentroidTracker, compute_center, euclidean_distance


def test_compute_center():
    box = (100, 100, 200, 200)
    center = compute_center(box)
    assert center == (150.0, 150.0)


def test_euclidean_distance():
    p1 = (0.0, 0.0)
    p2 = (3.0, 4.0)
    dist = euclidean_distance(p1, p2)
    assert dist == 5.0


def test_tracker_lifecycle():
    tracker = CentroidTracker(max_distance=50.0, max_missed_frames=3)

    # Frame 0: New detection
    dets_f0 = [
        {"class_name": "drone", "confidence": 0.9, "box": (100, 100, 150, 150)}
    ]
    tracks_f0 = tracker.update(dets_f0, frame_index=0)
    assert len(tracks_f0) == 1
    assert tracks_f0[0].track_id == 1
    assert dets_f0[0]["track_id"] == 1
    assert dets_f0[0]["track_age_frames"] == 1

    # Frame 1: Object moves slightly
    dets_f1 = [
        {"class_name": "drone", "confidence": 0.88, "box": (105, 105, 155, 155)}
    ]
    tracks_f1 = tracker.update(dets_f1, frame_index=1)
    assert len(tracks_f1) == 1
    assert tracks_f1[0].track_id == 1
    assert dets_f1[0]["track_age_frames"] == 2
    assert tracks_f1[0].hits == 2

    # Frame 2-5: Object disappears
    tracker.update([], frame_index=2)
    tracker.update([], frame_index=3)
    tracker.update([], frame_index=4)
    # Beyond max_missed_frames (3), track should be purged
    tracker.update([], frame_index=5)
    assert len(tracker.tracks) == 0
