from deep_sort_realtime.deepsort_tracker import DeepSort

class ObjectTracker:
    def __init__(self):
        self.tracker = DeepSort(
            max_age=15,
            n_init=2,
            max_cosine_distance=0.4,
            nn_budget=100,
        )
        self._last_conf = {}  # track_id -> last real confidence

    def update(self, detections: list, frame):
        ds_input = []
        if detections:
            for d in detections:
                x1, y1, x2, y2 = d["bbox"]
                w, h = x2 - x1, y2 - y1
                ds_input.append(([x1, y1, w, h], d["confidence"], d["class"]))

        tracks = self.tracker.update_tracks(ds_input, frame=frame)

        tracked = []
        active_ids = set()
        for track in tracks:
            if not track.is_confirmed():
                continue
            tid = track.track_id
            active_ids.add(tid)

            conf = track.get_det_conf()
            if conf is None:
                conf = self._last_conf.get(tid, 0.0)
            else:
                self._last_conf[tid] = conf

            x1, y1, x2, y2 = [int(v) for v in track.to_ltrb()]
            tracked.append({
                "track_id": tid,
                "class": track.get_det_class(),
                "confidence": conf,
                "bbox": [x1, y1, x2, y2],
            })

        # Garbage-collect stale entries
        for tid in list(self._last_conf):
            if tid not in active_ids:
                del self._last_conf[tid]

        return tracked