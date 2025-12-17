from __future__ import annotations

import cv2
import numpy as np
import requests


_hog = cv2.HOGDescriptor()
_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def download_image_to_cv2(image_url: str) -> np.ndarray:
    resp = requests.get(image_url, timeout=15)
    resp.raise_for_status()
    data = np.frombuffer(resp.content, np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def count_people_on_image(img: np.ndarray) -> int:
    h, w = img.shape[:2]
    max_width = 1400
    if w > max_width:
        scale = max_width / float(w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))

    rects, _ = _hog.detectMultiScale(img, winStride=(8, 8))
    return len(rects)


def count_people_from_url(image_url: str) -> int:
    img = download_image_to_cv2(image_url)
    return count_people_on_image(img)
