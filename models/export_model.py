# export_model.py in your project root
from ultralytics import YOLO

model = YOLO("yolov8m.pt")
model.export(format="onnx", imgsz=640, simplify=True, dynamic=True)
print("Export complete - yolov8m.onnx created")