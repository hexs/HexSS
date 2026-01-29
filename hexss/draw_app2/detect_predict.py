import cv2
from pathlib import Path
from ultralytics import YOLO
import threading
import time
import json

# --- Config ---
VIDEO_PATH = 'data01/video01.mp4'
MODEL_PATH = "export_result/model/m1-/weights/best.pt"
CACHE_DIR = Path("json_cache")

# --- Init ---
if not CACHE_DIR.exists():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

model_ui_ai = YOLO(MODEL_PATH)
model_worker_ai = YOLO(MODEL_PATH)
CLASS_NAMES = list(model_worker_ai.names.values())

cap_ui = cv2.VideoCapture(VIDEO_PATH)
cap_worker = cv2.VideoCapture(VIDEO_PATH)
total_frames = int(cap_ui.get(cv2.CAP_PROP_FRAME_COUNT))

processed_frames_index = set()
current_ui_frame = 0
is_running = True


def get_json_path(frame_id):
    return CACHE_DIR / f"{frame_id}.json"


def save_to_disk(frame_id, results, img_shape):
    h, w = img_shape[:2]
    boxes_data = []

    for box in results.boxes:
        xywhn = box.xywhn.cpu().numpy()[0].tolist()
        conf = float(box.conf.cpu().numpy()[0])
        cls_id = int(box.cls.cpu().numpy()[0])
        label = results.names[cls_id]

        boxes_data.append({
            "xywhn": xywhn,
            "conf": round(conf, 4),
            "cls": cls_id,
            "label": label
        })

    data = {
        "frame_id": str(frame_id),
        "size": [h, w],
        "names": CLASS_NAMES,
        "result": {
            "boxes": boxes_data
        }
    }

    with open(get_json_path(frame_id), 'w') as f:
        json.dump(data, f, indent=4)


def load_from_disk(frame_id):
    path = get_json_path(frame_id)
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except:
            return None
    return None


def ai_worker():
    global current_ui_frame, is_running

    existing_files = list(CACHE_DIR.glob("*.json"))
    for f in existing_files:
        try:
            if f.stem.isdigit():
                processed_frames_index.add(int(f.stem))
        except:
            pass

    print(f"Worker started. Frames cached: {len(processed_frames_index)}")

    while is_running:
        target_frame = -1

        for i in range(current_ui_frame, total_frames):
            if i not in processed_frames_index:
                target_frame = i
                break
        if target_frame == -1:
            for i in range(0, current_ui_frame):
                if i not in processed_frames_index:
                    target_frame = i
                    break

        if target_frame != -1:
            cap_worker.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap_worker.read()
            if ret:
                results = model_worker_ai.predict(frame, conf=0.5, verbose=False, device=0)

                save_to_disk(target_frame, results[0], frame.shape)
                processed_frames_index.add(target_frame)
            else:
                time.sleep(0.01)
        else:
            time.sleep(1.0)


t = threading.Thread(target=ai_worker, daemon=True)
t.start()


def draw_ui(image, curr_frame, tot_frames):
    h, w = image.shape[:2]
    bar_height = 15
    bar_margin_x = 50
    bar_margin_y = 50
    x1 = bar_margin_x
    y1 = h - bar_margin_y - bar_height
    x2 = w - bar_margin_x
    y2 = h - bar_margin_y
    bar_width = x2 - x1

    cv2.rectangle(image, (x1, y1), (x2, y2), (50, 50, 50), -1)
    pixels_per_frame = bar_width / tot_frames

    for f_idx in list(processed_frames_index):
        x_pos = int(x1 + (f_idx * pixels_per_frame))
        cv2.line(image, (x_pos, y1), (x_pos, y2), (0, 200, 0), 2)

    curr_x = int(x1 + (curr_frame * pixels_per_frame))
    cv2.circle(image, (curr_x, y1 + bar_height // 2), 10, (0, 0, 255), -1)
    cv2.putText(image, f"Frame: {curr_frame}/{tot_frames}",
                (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_boxes_from_json(img, json_data):
    if json_data is None: return

    h_img, w_img = img.shape[:2]
    boxes_list = json_data.get("result", {}).get("boxes", [])

    for item in boxes_list:
        x_c, y_c, w_n, h_n = item["xywhn"]
        label = item.get("label", "")
        conf = item.get("conf", 0.0)

        x_center = x_c * w_img
        y_center = y_c * h_img
        box_width = w_n * w_img
        box_height = h_n * h_img

        x1 = int(x_center - (box_width / 2))
        y1 = int(y_center - (box_height / 2))
        x2 = int(x_center + (box_width / 2))
        y2 = int(y_center + (box_height / 2))

        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

        text = f"{label} {conf:.2f}"
        cv2.putText(img, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)


while True:
    ret, img = cap_ui.read()
    if not ret: break

    n = int(cap_ui.get(cv2.CAP_PROP_POS_FRAMES))
    current_ui_frame = n

    json_data = None

    if n in processed_frames_index:
        json_data = load_from_disk(n)
    if json_data:
        draw_boxes_from_json(img, json_data)
    else:
        results = model_ui_ai.predict(img, conf=0.5, verbose=False, device=0)
        temp_boxes = []
        for box in results[0].boxes:
            temp_boxes.append({
                "xywhn": box.xywhn.cpu().numpy()[0].tolist(),
                "label": results[0].names[int(box.cls[0])],
                "conf": float(box.conf[0])
            })

        temp_data = {"result": {"boxes": temp_boxes}}
        draw_boxes_from_json(img, temp_data)

    draw_ui(img, n, total_frames)

    display_img = cv2.resize(img, None, fx=0.7, fy=0.7)
    cv2.imshow('Smart Player', display_img)

    key = cv2.waitKey(33) & 0xFF
    char = chr(key)
    if char == 'q':
        is_running = False
        break
    if char in '0123456789':
        i = int(char)
        target_pos = int(total_frames * i / 10)
        cap_ui.set(cv2.CAP_PROP_POS_FRAMES, target_pos)
        current_ui_frame = target_pos

cap_ui.release()
cap_worker.release()
cv2.destroyAllWindows()
