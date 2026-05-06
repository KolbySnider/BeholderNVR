import numpy as np
import cv2
import onnxruntime as ort
import time

# Pick the best available provider in priority order
_AVAILABLE = set(ort.get_available_providers())
_PROVIDER_PREFERENCE = [
    "TensorrtExecutionProvider",   # NVIDIA, best
    "CUDAExecutionProvider",       # NVIDIA, fast
    "DmlExecutionProvider",        # Windows + any GPU
    "CoreMLExecutionProvider",     # Mac, Apple Silicon
    "CPUExecutionProvider",        # Universal fallback
]
_PROVIDERS = [p for p in _PROVIDER_PREFERENCE if p in _AVAILABLE]
print(f"[YOLO] Using providers: {_PROVIDERS}")

session = ort.InferenceSession("models/yolov8m.onnx", providers=_PROVIDERS)

input_name = session.get_inputs()[0].name
CONF_THRESHOLD = 0.60
NMS_THRESHOLD = 0.4

# There are more options but realistically this is all i'll see
CLASSES = [
    "person", "bicycle", "car", "motorcycle",
    "bird", "cat", "dog"
]


def preprocess(frame):
    img = cv2.resize(frame, (640, 640))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))
    return img


def postprocess(output, orig_h, orig_w):
    predictions = np.squeeze(output).T

    boxes = []
    confidences = []
    class_ids = []

    for pred in predictions:
        scores = pred[4:]
        class_id = np.argmax(scores)
        confidence = scores[class_id]

        if confidence < CONF_THRESHOLD:
            continue

        x, y, w, h = pred[0], pred[1], pred[2], pred[3]
        x1 = int((x - w / 2) * orig_w / 640)
        y1 = int((y - h / 2) * orig_h / 640)
        x2 = int((x + w / 2) * orig_w / 640)
        y2 = int((y + h / 2) * orig_h / 640)

        boxes.append([x1, y1, x2 - x1, y2 - y1])
        confidences.append(float(confidence))
        class_ids.append(class_id)

    if not boxes:
        return []

    # NMS - removes overlapping boxes for the same object
    indices = cv2.dnn.NMSBoxes(
        boxes, confidences, CONF_THRESHOLD, NMS_THRESHOLD
    )

    detections = []
    for i in indices.flatten():
        x1, y1, w, h = boxes[i]
        cls_idx = class_ids[i]
        if cls_idx >= len(CLASSES):
            continue
        detections.append({
            "class": CLASSES[class_ids[i]],
            "confidence": confidences[i],
            "bbox": [x1, y1, x1 + w, y1 + h],
            "timestamp": time.time()
        })

    return detections


def run_detection(frame) -> list:
    orig_h, orig_w = frame.shape[:2]
    tensor = np.expand_dims(preprocess(frame), axis=0)
    outputs = session.run(None, {input_name: tensor})
    return postprocess(outputs[0][0], orig_h, orig_w)