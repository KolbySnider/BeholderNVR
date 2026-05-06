# BeholderNVR

Multi-camera NVR with real-time object detection, tracking, and a Kafka event pipeline.

Beholder ingests RTSP streams, runs motion-gated YOLO inference per camera, tracks objects across frames with DeepSORT, and publishes events to Kafka. Independent consumers persist events to Postgres and emit alerts. The PyQt6 dashboard shows live feeds and a searchable detection log with snapshot galleries.

<img width="1220" height="429" alt="Beholder" src="https://github.com/user-attachments/assets/f62794de-f10d-4b14-9eca-92dfa4f6458e" />
<img width="985" height="515" alt="Beholder2" src="https://github.com/user-attachments/assets/87232797-9a63-4aaf-8a06-a01781834353" />

## Features

- Multi-camera live RTSP feeds with per-camera detection toggles
- YOLOv8 object detection on ONNX Runtime
- DeepSORT tracking with persistent IDs
- MOG2 motion gating to skip inference on idle cameras
- Kafka event bus with independent consumers for persistence and alerts
- Searchable detection log with snapshot galleries


## Setup

```bash
git clone https://github.com/KolbySnider/BeholderNVR.git
cd BeholderNVR
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Install the ONNX Runtime variant for your hardware (pick one):

| Hardware | Install |
|---|---|
| NVIDIA GPU | `pip install onnxruntime-gpu` |
| AMD / Intel GPU on Windows | `pip install onnxruntime-directml` |
| Apple Silicon | `pip install onnxruntime-silicon` |
| CPU only | `pip install onnxruntime` |

Drop a YOLOv8/v9/v10/v11 ONNX model into the projects models folder as `yolov8m.onnx`. Any size works (`n`/`s`/`m`/`l`/`x`).

You'll also need `ffmpeg` and `ffprobe` on your PATH, and Docker Desktop running.

## Run

```bash
python main.py
```

This brings up Kafka and Postgres in Docker, starts the consumer processes, and launches the dashboard. Click **Add Stream**, paste an RTSP URL, then click **DETECT** on the camera tile.

`Ctrl+C` in the launcher terminal stops everything cleanly.

## License

MIT
