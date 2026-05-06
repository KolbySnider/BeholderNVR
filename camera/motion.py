import cv2
import numpy as np


class MotionDetector:
    def __init__(self, min_area=500):
        self.min_area = min_area
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=70,
            detectShadows=False
        )

    def update_threshold(self, value: int):
        """Recreate background subtractor with new threshold"""
        self.var_threshold = value
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=value,
            detectShadows=False
        )

    def detect(self, frame) -> bool:
        """Returns True if meaningful motion is detected in frame"""
        mask = self.bg_subtractor.apply(frame)

        # Remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.dilate(mask, kernel, iterations=2)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            if cv2.contourArea(contour) >= self.min_area:
                return True

        return False