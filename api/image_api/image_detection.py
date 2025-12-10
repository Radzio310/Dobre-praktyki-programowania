# image_api/image_detection.py
import cv2
import numpy as np
import requests


# Jeden globalny detektor HOG – nie tworzymy go za każdym razem.
_hog = cv2.HOGDescriptor()
_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def download_image_to_cv2(image_url: str) -> np.ndarray:
    """
    Pobiera obraz z podanego URL i zwraca go jako macierz OpenCV (BGR).
    """
    resp = requests.get(image_url, timeout=10)
    resp.raise_for_status()
    data = np.frombuffer(resp.content, np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Nie udało się zdekodować obrazu z podanego URL.")
    return img


def count_people_on_image(img: np.ndarray) -> int:
    """
    Zwraca liczbę wykrytych osób na obrazie.
    """
    # resize dla przyspieszenia (opcjonalnie)
    height, width = img.shape[:2]
    max_width = 1600
    if width > max_width:
        scale = max_width / float(width)
        img = cv2.resize(img, (int(width * scale), int(height * scale)))

    rects, _ = _hog.detectMultiScale(img, winStride=(8, 8))
    return len(rects)


def count_people_from_url(image_url: str) -> int:
    """
    Helper łączący pobranie obrazu z liczeniem osób.
    """
    img = download_image_to_cv2(image_url)
    return count_people_on_image(img)
