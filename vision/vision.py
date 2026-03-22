import cv2
import numpy as np
from ultralytics import YOLO
from deepface import DeepFace
from deep_sort_realtime.deepsort_tracker import DeepSort

# ---------------------------
# MODELLER
# ---------------------------

print("YOLO yükleniyor...")
model = YOLO("yolov8n.pt")

print("Tracker başlatılıyor...")
tracker = DeepSort(max_age=30)

print("Hazır ✅")

person_cache = {}

# ---------------------------
# AYARLAR
# ---------------------------

SCALE_FACTOR = 0.5  # Boy kalibrasyon sabiti (sonradan ayarlanabilir)

def estimate_height(pixel_height):
    return round(pixel_height * SCALE_FACTOR, 1)

def classify_body_type(width, height):
    ratio = width / height
    if ratio < 0.40:
        return "Slim"
    elif ratio < 0.55:
        return "Medium"
    else:
        return "Heavy"

# ---------------------------
# KAMERA
# ---------------------------

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, verbose=False)

    detections_for_tracker = []

    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            if cls in [0, 2, 5, 7]:  # person + vehicles
                detections_for_tracker.append(
                    ([x1, y1, x2 - x1, y2 - y1], conf, cls)
                )

    tracks = tracker.update_tracks(detections_for_tracker, frame=frame)

    for track in tracks:
        if not track.is_confirmed():
            continue

        track_id = track.track_id
        l, t, r, b = track.to_ltrb()

        l, t, r, b = int(l), int(t), int(r), int(b)

        l = max(0, l)
        t = max(0, t)
        r = min(frame.shape[1], r)
        b = min(frame.shape[0], b)

        width = r - l
        height = b - t

        label = f"ID {track_id}"

        # ---------------------------
        # PERSON ANALYSIS
        # ---------------------------
        if track.det_class == 0:

            # Height estimation
            height_cm = estimate_height(height)

            # Body type classification
            body_type = classify_body_type(width, height)

            label += f" | {height_cm}cm | {body_type}"

            # Age/Gender sadece ilk sefer
            if track_id not in person_cache:

                person_crop = frame[t:b, l:r]

                if person_crop.size > 0:
                    try:
                        result = DeepFace.analyze(
                            person_crop,
                            actions=["age", "gender"],
                            enforce_detection=False,
                            detector_backend="opencv"
                        )

                        age = result[0]["age"]
                        gender = result[0]["dominant_gender"]

                        person_cache[track_id] = {
                            "age": age,
                            "gender": gender
                        }

                    except:
                        pass

            if track_id in person_cache:
                age = person_cache[track_id]["age"]
                gender = person_cache[track_id]["gender"]
                label += f" | {gender} {age}"

        # ---------------------------
        # DRAW
        # ---------------------------
        cv2.rectangle(frame, (l, t), (r, b), (0, 255, 0), 2)
        cv2.putText(frame, label,
                    (l, t - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2)

    cv2.imshow("UMAY - Height & Body Type", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
