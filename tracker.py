from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot


@dataclass
class Track:
    track_id: int
    class_name: str
    box: tuple[int, int, int, int]
    confidence: float
    center: tuple[float, float]
    first_seen_frame: int
    last_seen_frame: int
    hits: int = 1
    missed_frames: int = 0
    estimated_speed: float = 0.0
    history: list[tuple[float, float]] = field(default_factory=list)


class CentroidTracker:
    def __init__(self, max_distance: float = 80.0, max_missed_frames: int = 20) -> None:
        self.max_distance = max_distance
        self.max_missed_frames = max_missed_frames
        self.next_track_id = 1
        self.tracks: dict[int, Track] = {}

    def update(self, detections: list[dict], frame_index: int) -> list[Track]:
        unmatched_track_ids = set(self.tracks.keys())

        for detection in detections:
            center = compute_center(detection["box"])
            matched_track = self._find_best_track(
                class_name=detection["class_name"],
                center=center,
                unmatched_track_ids=unmatched_track_ids,
            )

            if matched_track is None:
                track = Track(
                    track_id=self.next_track_id,
                    class_name=detection["class_name"],
                    box=detection["box"],
                    confidence=detection["confidence"],
                    center=center,
                    first_seen_frame=frame_index,
                    last_seen_frame=frame_index,
                    history=[center],
                )
                self.tracks[self.next_track_id] = track
                self.next_track_id += 1
                detection["track_id"] = track.track_id
                detection["track_age_frames"] = 1
                detection["estimated_speed"] = 0.0
                continue

            unmatched_track_ids.discard(matched_track.track_id)
            speed = euclidean_distance(matched_track.center, center)
            matched_track.box = detection["box"]
            matched_track.confidence = detection["confidence"]
            matched_track.center = center
            matched_track.last_seen_frame = frame_index
            matched_track.hits += 1
            matched_track.missed_frames = 0
            matched_track.estimated_speed = speed
            matched_track.history.append(center)
            if len(matched_track.history) > 30:
                matched_track.history.pop(0)

            detection["track_id"] = matched_track.track_id
            detection["track_age_frames"] = frame_index - matched_track.first_seen_frame + 1
            detection["estimated_speed"] = round(speed, 3)

        self._age_unmatched_tracks(unmatched_track_ids)
        return list(self.tracks.values())

    def _find_best_track(
        self,
        class_name: str,
        center: tuple[float, float],
        unmatched_track_ids: set[int],
    ) -> Track | None:
        best_track = None
        best_distance = self.max_distance

        for track_id in unmatched_track_ids:
            track = self.tracks[track_id]
            if track.class_name != class_name:
                continue

            distance = euclidean_distance(track.center, center)
            if distance <= best_distance:
                best_track = track
                best_distance = distance

        return best_track

    def _age_unmatched_tracks(self, unmatched_track_ids: set[int]) -> None:
        expired_track_ids = []
        for track_id in unmatched_track_ids:
            track = self.tracks[track_id]
            track.missed_frames += 1
            if track.missed_frames > self.max_missed_frames:
                expired_track_ids.append(track_id)

        for track_id in expired_track_ids:
            del self.tracks[track_id]


def compute_center(box: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def euclidean_distance(point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    return hypot(point_a[0] - point_b[0], point_a[1] - point_b[1])
