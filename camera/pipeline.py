import threading
import time
import os
import cv2
import queue
import numpy as np
from camera.capture import CameraCapture
from camera.motion import MotionDetector
from camera.tracker import ObjectTracker
from camera.detector import preprocess, postprocess, session, input_name

SNAPSHOT_DIR = "snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
YOLO_EVERY_N_FRAMES = 3

_inference_queue = queue.Queue(maxsize=32)
_results = {}
_results_lock = threading.Lock()


def _inference_worker():
    print("[YOLO] Inference worker started")
    while True:
        try:
            name, frame = _inference_queue.get(timeout=1.0)
        except queue.Empty:
            continue
        try:
            orig_h, orig_w = frame.shape[:2]
            tensor = np.expand_dims(preprocess(frame), axis=0)
            outputs = session.run(None, {input_name: tensor})
            detections = postprocess(outputs[0][0], orig_h, orig_w)
            with _results_lock:
                _results[name] = (detections, frame)
        except Exception as e:
            print(f"[YOLO ERROR] {e}")


threading.Thread(target=_inference_worker, daemon=True).start()


class CameraPipeline:
    def __init__(self, name: str, url: str):
        self.name = name
        self.running = True
        self.detection_active = False

        self.capture = CameraCapture(name, url)
        self.motion = MotionDetector()
        self.tracker = ObjectTracker()

        self.current_tracks = []
        self.lock = threading.Lock()
        self.tracker_lock = threading.Lock()
        self._frame_count = 0
        self._last_snapshot_time = 0

        threading.Thread(target=self._pipeline_loop, daemon=True).start()
        threading.Thread(target=self._results_loop, daemon=True).start()

        self.settings = {
            "show_bbox": True,
            "motion_sensitivity": 70,  # min_area
            "confidence_threshold": 0.60,
            "enabled_classes": {"person", "car", "truck", "motorcycle", "bicycle", "dog", "cat"},
        }

    def update_setting(self, key, value):
        self.settings[key] = value
        # Apply changes to running components
        if key == "motion_sensitivity":
            self.motion.min_area = value

    def _pipeline_loop(self):
        while self.running:
            frame = self.capture.get_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            if not self.detection_active:
                time.sleep(0.03)
                continue

            self._frame_count += 1
            has_motion = self.motion.detect(frame)

            if has_motion and self._frame_count % YOLO_EVERY_N_FRAMES == 0:
                try:
                    _inference_queue.put_nowait((self.name, frame.copy()))
                except queue.Full:
                    pass

            if has_motion:
                time.sleep(0.033)
            else:
                with self.lock:
                    self.current_tracks = []
                time.sleep(0.1)

    def _results_loop(self):
        from pipeline.event_manager import event_manager
        while self.running:
            result = None
            with _results_lock:
                if self.name in _results:
                    result = _results.pop(self.name)

            if result is None:
                time.sleep(0.033)
                continue

            detections, frame = result

            # Apply per-camera filters
            filtered = [
                d for d in detections
                if d["confidence"] >= self.settings["confidence_threshold"]
                   and d["class"] in self.settings["enabled_classes"]
            ]

            with self.tracker_lock:
                tracks = self.tracker.update(filtered, frame)

            with self.lock:
                self.current_tracks = tracks

            if tracks:
                snapshot_path = self._save_snapshot(frame)
                if snapshot_path:
                    event_manager.process(self.name, tracks, snapshot_path)

    def _save_snapshot(self, frame) -> str:
        now = time.time()
        if now - self._last_snapshot_time < 2.0:
            return ""
        self._last_snapshot_time = now
        filename = f"{self.name.replace(' ', '_')}_{int(now)}.jpg"
        path = os.path.abspath(os.path.join(SNAPSHOT_DIR, filename))
        cv2.imwrite(path, frame)
        return path

    def get_frame(self):
        return self.capture.get_frame()

    def get_tracks(self):
        with self.lock:
            return self.current_tracks.copy()

    def start_detection(self):
        self.detection_active = True
        print(f"[PIPELINE] {self.name} detection started")

    def stop_detection(self):
        self.detection_active = False
        with self.lock:
            self.current_tracks = []
        print(f"[PIPELINE] {self.name} detection stopped")

    def stop(self):
        self.running = False
        self.capture.stop()