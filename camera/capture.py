import subprocess
import threading
import numpy as np
import json
import os
import cv2
import time

SNAPSHOT_DIR = "snapshots"
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


class CameraCapture:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.running = True
        self.latest_frame = None
        self.lock = threading.Lock()

        self.width, self.height = self._probe_resolution()
        print(f"[CAPTURE] {name} resolution: {self.width}x{self.height}")

        threading.Thread(target=self._capture_loop, daemon=True).start()

    def _probe_resolution(self):
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-rtsp_transport", "tcp",
                "-print_format", "json",
                "-show_streams", self.url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            info = json.loads(result.stdout)
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    return stream["width"], stream["height"]
        except Exception as e:
            print(f"[CAPTURE] Could not probe resolution: {e}, using fallback")
        return 1280, 720

    def _capture_loop(self):
        cmd = [
            "ffmpeg",
            "-hwaccel", "d3d11va",
            "-rtsp_transport", "tcp",
            "-i", self.url,
            "-vf", "fps=30",
            "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-f", "rawvideo",
            "-"
        ]

        print(f"[CAPTURE] {self.name} starting ffmpeg stream...")

        while self.running:
            pipe = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=10 ** 8
            )

            frame_size = self.width * self.height * 3

            try:
                while self.running:
                    raw = pipe.stdout.read(frame_size)
                    if len(raw) != frame_size:
                        print(f"[CAPTURE] {self.name} stream dropped, reconnecting...")
                        break
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                        (self.height, self.width, 3)
                    )
                    with self.lock:
                        self.latest_frame = frame.copy()
            except Exception as e:
                print(f"[CAPTURE] {self.name} error: {e}")
            finally:
                pipe.kill()
                pipe.wait()

            if self.running:
                time.sleep(2)  # wait before reconnect

    def get_frame(self):
        with self.lock:
            return self.latest_frame

    def save_snapshot(self, timestamp: float) -> str:
        frame = self.get_frame()
        if frame is None:
            return ""
        filename = f"{self.name.replace(' ', '_')}_{int(timestamp)}.jpg"
        path = os.path.abspath(os.path.join(SNAPSHOT_DIR, filename))
        cv2.imwrite(path, frame)
        return path

    def stop(self):
        self.running = False