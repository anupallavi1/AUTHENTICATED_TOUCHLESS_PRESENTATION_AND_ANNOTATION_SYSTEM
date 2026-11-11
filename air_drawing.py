# """
# Air Drawing Application with Hand Gesture Recognition
# Requires: opencv-python, mediapipe, numpy, Pillow
# Install: pip install opencv-python mediapipe numpy Pillow
# """
#
# import cv2
# import mediapipe as mp
# from mediapipe.tasks import python
# from mediapipe.tasks.python import vision
# import numpy as np
# from PIL import Image, ImageDraw
# import math
# import os
# selected_color=(255, 0 ,0)
#
# # -----------------------------
# # Configuration
# # -----------------------------
# CANVAS_W, CANVAS_H = 1280, 720
# TOP_BAR_HEIGHT = 90
# BRUSH_THICKNESS = 6
#
# # Path to the model file (place it in the same directory as this script)
# MODEL_PATH = 'hand_landmarker.task'
#
# COLORS = [
#     ("Red",    (255, 0, 0)),
#     ("Green",  (0, 200, 0)),
#     ("Blue",   (0, 0, 255)),
#     ("Black",  (0, 0, 0)),
# ]
#
# SHAPES = ["Circle", "Square", "Rectangle", "Star"]
# SHAPE_SIZE = 30
#
# # -----------------------------
# # MediaPipe Tasks Setup
# # -----------------------------
# base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
# options = vision.HandLandmarkerOptions(
#     base_options=base_options,
#     num_hands=1,
#     min_hand_detection_confidence=0.7,
#     min_hand_presence_confidence=0.6,
#     min_tracking_confidence=0.6,
#     running_mode=vision.RunningMode.IMAGE
# )
# landmarker = vision.HandLandmarker.create_from_options(options)
#
# # Define hand connections manually (pairs of landmark indices)
# HAND_CONNECTIONS = [
#     (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
#     (0, 5), (5, 6), (6, 7), (7, 8),        # Index
#     (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
#     (9, 13), (13, 14), (14, 15), (15, 16), # Ring
#     (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
#     (0, 17)                                 # Palm base
# ]
#
# # -----------------------------
# # Custom Landmark Drawing Function
# # -----------------------------
# def draw_landmarks_custom(frame, hand_landmarks):
#     """Draw landmarks and connections on the frame."""
#     h, w, _ = frame.shape
#     # Draw connections first
#     for connection in HAND_CONNECTIONS:
#         start_idx, end_idx = connection
#         start = hand_landmarks[start_idx]
#         end = hand_landmarks[end_idx]
#         start_point = (int(start.x * w), int(start.y * h))
#         end_point = (int(end.x * w), int(end.y * h))
#         cv2.line(frame, start_point, end_point, (0, 255, 0), 2)
#     # Draw landmarks
#     for lm in hand_landmarks:
#         x, y = int(lm.x * w), int(lm.y * h)
#         cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)
#         cv2.circle(frame, (x, y), 7, (255, 255, 255), 1)
#
# # -----------------------------
# # App state
# # -----------------------------
# class AppState:
#     def __init__(self):
#         self.image = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
#         self.draw = ImageDraw.Draw(self.image)
#         self.current_color = (255, 0, 0)
#         self.prev_point = None
#         self.mode = "draw"
#         self.selected_shape = "Circle"
#         self.last_action_frame = 0
#         self.finger_count_history = []
#
# state = AppState()
#
# # -----------------------------
# # Helpers (unchanged logic, updated for landmark objects)
# # -----------------------------
# def get_palette_positions():
#     n = len(COLORS)
#     spacing = CANVAS_W // (n + 1)
#     positions = []
#     for i, (name, color) in enumerate(COLORS):
#         cx = spacing * (i + 1)
#         cy = TOP_BAR_HEIGHT // 2
#         r = 30
#         positions.append((cx, cy, r, color, name))
#     return positions
#
# def draw_top_bar(img_bgr):
#     cv2.rectangle(img_bgr, (0, 0), (CANVAS_W, TOP_BAR_HEIGHT), (240, 240, 240), -1)
#     for cx, cy, r, color, name in get_palette_positions():
#         bgr = (color[2], color[1], color[0])
#         cv2.circle(img_bgr, (cx, cy), r, bgr, -1)
#         cv2.circle(img_bgr, (cx, cy), r, (50, 50, 50), 2)
#         if color == state.current_color:
#             cv2.circle(img_bgr, (cx, cy), r + 5, (0, 255, 255), 3)
#     cv2.putText(img_bgr, f"Shape: {state.selected_shape}",
#                 (CANVAS_W - 260, 35), cv2.FONT_HERSHEY_SIMPLEX,
#                 0.7, (0, 0, 0), 2)
#     cv2.putText(img_bgr, "Mode: DRAW",
#                 (CANVAS_W - 260, 70), cv2.FONT_HERSHEY_SIMPLEX,
#                 0.6, (0, 120, 0), 2)
#
# def fingers_up(hand_landmarks):
#     """Return list of 5 booleans [thumb, index, middle, ring, pinky]."""
#     # hand_landmarks is now a list of NormalizedLandmark objects
#     lm = hand_landmarks
#     tips = [4, 8, 12, 16, 20]
#     pips = [3, 6, 10, 14, 18]
#     fingers = []
#     if lm[tips[0]].x < lm[pips[0]].x:
#         fingers.append(True)
#     else:
#         fingers.append(False)
#     for i in range(1, 5):
#         fingers.append(lm[tips[i]].y < lm[pips[i]].y)
#     return fingers
#
# def classify_gesture(fingers):
#     thumb, index, middle, ring, pinky = fingers
#     if not index and middle and not ring and not pinky:
#         return ("COLOR", (255, 0, 0))
#     if not index and not middle and ring and not pinky:
#         return ("COLOR", (0, 0, 0))
#     if index and not middle and ring and not pinky:
#         return ("COLOR", (0, 200, 0))
#     if not index and not middle and not ring and pinky:
#         return ("COLOR", (0, 0, 255))
#     if index and not middle and not ring and not pinky:
#         return ("COLOR", state.current_color)
#
#     if thumb and index and middle and ring and pinky:
#         state.image = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
#         state.draw = ImageDraw.Draw(state.image)
#         # return ("SHAPE", "Circle")
#     if not index and not middle and ring and  pinky:
#         return ("SHAPE", "Square")
#     if not index and middle and  ring and not pinky:
#         return ("SHAPE", "Star")
#     if not index and not middle and not ring and not pinky:
#         return ("SHAPE", "Circle")
#     return ("NONE", None)
#
# def draw_star(draw, cx, cy, size, color, outline=3):
#     points = []
#     for i in range(10):
#         angle = math.pi / 2 + i * math.pi / 5
#         r = size if i % 2 == 0 else size * 0.4
#         x = cx + r * math.cos(angle)
#         y = cy - r * math.sin(angle)
#         points.append((x, y))
#     draw.polygon(points, fill=color, outline=color)
#
# def draw_shape(draw, shape_name, cx, cy, color):
#     s = SHAPE_SIZE
#     if shape_name == "Circle":
#         draw.ellipse([cx - s, cy - s, cx + s, cy + s], fill=color, outline=color)
#     elif shape_name == "Square":
#         draw.rectangle([cx - s, cy - s, cx + s, cy + s], fill=color, outline=color)
#     elif shape_name == "Rectangle":
#         draw.rectangle([cx - s, cy - s // 2, cx + s, cy + s // 2],
#                        fill=color, outline=color)
#     elif shape_name == "Star":
#         draw_star(draw, cx, cy, s, color)
#
# def inside_top_bar(x, y):
#     return y < TOP_BAR_HEIGHT
#
# # -----------------------------
# # Main loop
# # -----------------------------
# def main3():
#     cap = cv2.VideoCapture(0)
#     if not cap.isOpened():
#         print("ERROR: Cannot open webcam.")
#         return
#
#     cap.set(cv2.CAP_PROP_FRAME_WIDTH, CANVAS_W)
#     cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CANVAS_H)
#
#     last_gesture = "NONE"
#     gesture_stable_frames = 0
#     REQUIRED_STABLE = 4
#
#     while True:
#         success, frame = cap.read()
#         if not success:
#             break
#
#         frame = cv2.flip(frame, 1)
#         frame = cv2.resize(frame, (CANVAS_W, CANVAS_H))
#         rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#
#         # Create a MediaPipe Image object
#         mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
#
#         # Detect hand landmarks
#         detection_result = landmarker.detect(mp_image)
#
#         cursor_pos = None
#
#         # Process results - check if any hand landmarks were detected
#         if detection_result.hand_landmarks:
#             # Get the first hand's landmarks (list of NormalizedLandmark)
#             hand_landmarks = detection_result.hand_landmarks[0]
#
#             # Draw landmarks using custom function
#             draw_landmarks_custom(frame, hand_landmarks)
#
#             fingers = fingers_up(hand_landmarks)
#             gesture, value = classify_gesture(fingers)
#
#             if gesture == last_gesture:
#                 gesture_stable_frames += 1
#             else:
#                 gesture_stable_frames = 0
#                 last_gesture = gesture
#
#             if gesture_stable_frames == REQUIRED_STABLE:
#                 if gesture == "COLOR" and value is not None:
#                     state.current_color = value
#                     state.mode = "draw"
#                     state.prev_point = None
#                 elif gesture == "SHAPE" and value is not None:
#                     state.selected_shape = value
#                     state.mode = "shape"
#                     state.prev_point = None
#
#             h, w, _ = frame.shape
#             # Access landmark 8 directly from the list
#             idx_tip = hand_landmarks[8]
#             ix, iy = int(idx_tip.x * w), int(idx_tip.y * h)
#             cursor_pos = (ix, iy)
#
#             if gesture == "COLOR" and value == state.current_color \
#                     and not inside_top_bar(ix, iy):
#                 if state.prev_point is not None:
#                     state.draw.line([state.prev_point, (ix, iy)],
#                                     fill=state.current_color,
#                                     width=BRUSH_THICKNESS)
#                 state.prev_point = (ix, iy)
#             else:
#                 state.prev_point = None
#
#             if state.mode == "shape" and gesture == "SHAPE" \
#                     and gesture_stable_frames == REQUIRED_STABLE \
#                     and not inside_top_bar(ix, iy):
#                 draw_shape(state.draw, state.selected_shape, ix, iy,
#                            state.current_color)
#                 state.mode = "draw"
#                 gesture_stable_frames = 0
#
#             cv2.circle(frame, (ix, iy), 10, (255, 0, 255), 2)
#
#         canvas_np = np.array(state.image)
#         canvas_bgr = cv2.cvtColor(canvas_np, cv2.COLOR_RGB2BGR)
#
#         mask = np.any(canvas_np != 255, axis=2)
#         frame[mask] = canvas_bgr[mask]
#
#         draw_top_bar(frame)
#
#         cv2.putText(frame,
#                     "Gestures: Middle=Red | Ring=Black | Index+Ring=Green | "
#                     "Pinky=Blue",
#                     (10, CANVAS_H - 50), cv2.FONT_HERSHEY_SIMPLEX,
#                     0.5, (0, 0, 0), 1)
#         cv2.putText(frame,
#                     "Shapes: Fist=Circle | Index+Middle=Rectangle | "
#                     "Index+Middle+Ring=Square | All=Star",
#                     (10, CANVAS_H - 25), cv2.FONT_HERSHEY_SIMPLEX,
#                     0.5, (0, 0, 0), 1)
#
#         cv2.imshow("Air Drawing - Hand Gesture", frame)
#
#         key = cv2.waitKey(1) & 0xFF
#         if key == ord('q'):
#             break
#         elif key == ord('c'):
#             state.image = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
#             state.draw = ImageDraw.Draw(state.image)
#
#     cap.release()
#     cv2.destroyAllWindows()
#
#
# if __name__ == "__main__":
#     # Check if model file exists
#     if not os.path.exists(MODEL_PATH):
#         print(f"ERROR: Model file '{MODEL_PATH}' not found.")
#         print("Please download it from: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
#     else:
#         main3()







"""
Air Drawing Application with Hand Gesture Recognition + Handwritten Text Recognition
White drawing board on the left, tool panel (webcam, color, shape, thickness,
recognized text) on the right.

Text recognition uses Gemini Vision when it is reachable (much better at handwriting)
and falls back to Tesseract OCR (offline) otherwise.

Requires: opencv-contrib-python, mediapipe, numpy, Pillow, pytesseract, google-generativeai
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
from PIL import Image
import math
import os
import threading
import time
import concurrent.futures
import pytesseract
from main import PresenterTracker, REFERENCE_IMAGE, MAX_HANDS, MAX_HAND_DISTANCE

# -----------------------------
# Configuration
# -----------------------------
CANVAS_W, CANVAS_H = 1280, 720
PANEL_W = 300                      # right panel width
DRAW_W = CANVAS_W - PANEL_W        # white drawing board width
PREVIEW_H = PANEL_W * 9 // 16      # webcam preview at the top of the panel

MODEL_PATH = 'hand_landmarker.task'

# Same tools as the slide window (main.py). Colors are BGR.
COLORS = [
    ("Blue",  (255, 0, 0)),
    ("Red",   (0, 0, 255)),
    ("Green", (0, 200, 0)),
]
# "Free" is the normal pen used for writing; the other four are the shapes
SHAPES = ["Free", "Line", "Rectangle", "Circle", "Star"]
THICKNESSES = [2, 4, 6]

ERASER_RADIUS = 30
MAX_UNDO = 20
SMOOTHING = 0.5         # 0 = no smoothing, closer to 1 = smoother but laggier pen
HOLD_FRAMES = 10        # frames a "hold" gesture must be held before it is applied

# Finger patterns ignore the thumb: [index, middle, ring, pinky]
GESTURE_DRAW = [1, 0, 0, 0]
GESTURE_MOVE = [1, 1, 0, 0]
GESTURE_ERASE = [0, 0, 0, 0]
HOLD_GESTURES = {
    "undo":      [1, 1, 1, 0],   # Index + Middle + Ring
    "color":     [1, 0, 0, 1],   # Index + Pinky (rock sign)
    "shape":     [0, 0, 0, 1],   # Pinky only
    "thickness": [0, 1, 1, 1],   # Middle + Ring + Pinky
    "recognize": [1, 1, 1, 1],   # Open palm
    "screenshot": [1, 1, 0, 1],  # Index + Middle + Pinky
    "clear":     [0, 0, 1, 1],   # Ring + Pinky: wipe the whole board
}
SCREENSHOT_DIR = "screenshots"

# Tesseract (offline fallback)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# Gemini (primary recognizer). Key: GEMINI_API_KEY env var, else the key in ppt_summarizer.py
GEMINI_MODEL = "gemini-flash-lite-latest"   # fast; the non-lite model can take 30+ s
GEMINI_TIMEOUT = 15
GEMINI_PROMPT = (
    "This image contains handwriting that was drawn in the air with a finger, "
    "so the strokes are shaky and letters may be uneven or joined. "
    "Transcribe exactly what is written. Keep the original line breaks. "
    "Reply with only the transcribed text and nothing else. "
    "If there is no readable text, reply with an empty response."
)

# -----------------------------
# MediaPipe Tasks Setup
# -----------------------------
base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=MAX_HANDS,        # several hands are detected, only the presenter's is used
    min_hand_detection_confidence=0.7,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.6,
    running_mode=vision.RunningMode.IMAGE
)
landmarker = vision.HandLandmarker.create_from_options(options)

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17)
]


def draw_landmarks_custom(frame, hand_landmarks):
    h, w, _ = frame.shape
    for s, e in HAND_CONNECTIONS:
        sp = (int(hand_landmarks[s].x * w), int(hand_landmarks[s].y * h))
        ep = (int(hand_landmarks[e].x * w), int(hand_landmarks[e].y * h))
        cv2.line(frame, sp, ep, (0, 255, 0), 2)
    for lm in hand_landmarks:
        x, y = int(lm.x * w), int(lm.y * h)
        cv2.circle(frame, (x, y), 5, (0, 0, 255), -1)
        cv2.circle(frame, (x, y), 7, (255, 255, 255), 1)


# -----------------------------
# App state
# -----------------------------
def blank_board():
    return np.full((CANVAS_H, DRAW_W, 3), 255, np.uint8)


class AppState:
    def __init__(self):
        self.board = blank_board()
        self.undo_stack = []
        self.color_index = 0
        self.shape_index = 0
        self.thickness_index = 1
        self.current_ann = None         # stroke / shape being drawn (not yet on the board)
        self.cursor = None              # smoothed finger position on the board
        self.prev_eraser = None
        self.erasing = False
        self.hold_gesture = None
        self.hold_count = 0
        self.hold_release = None        # hold gesture that just fired; must change before it fires again

        # Text recognition state
        self.recognized_lines = []
        self.ocr_busy = False
        self.ocr_status = "Open palm (hold) to recognize"
        self.ocr_result = None          # (text, board snapshot mask) handed from the worker thread

        # Short on-screen message (e.g. "Screenshot saved")
        self.notice = ""
        self.notice_until = 0.0

    def save_undo(self):
        self.undo_stack.append(self.board.copy())
        if len(self.undo_stack) > MAX_UNDO:
            self.undo_stack.pop(0)


state = AppState()


# -----------------------------
# Helpers
# -----------------------------
def fingers_up(hand_landmarks):
    """[thumb, index, middle, ring, pinky] - a finger is up when its tip is farther
    from the wrist than its middle joint (works even when the hand is tilted)."""
    lm = [(p.x * CANVAS_W, p.y * CANVAS_H) for p in hand_landmarks]

    def dist(a, b):
        return math.hypot(lm[a][0] - lm[b][0], lm[a][1] - lm[b][1])

    fingers = [dist(4, 17) > dist(3, 17)]                   # thumb: tip away from the pinky base
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        fingers.append(dist(tip, 0) > dist(pip, 0))
    return fingers


def to_board(lm):
    """Map a normalized landmark to board coordinates. The middle 70% of the camera
    view covers the whole board so the edges are easy to reach."""
    x = int(np.interp(lm.x, [0.15, 0.85], [0, DRAW_W - 1]))
    y = int(np.interp(lm.y, [0.15, 0.85], [0, CANVAS_H - 1]))
    return x, y


def star_points(center, outer_radius):
    cx, cy = center
    inner_radius = outer_radius * 0.4
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = outer_radius if i % 2 == 0 else inner_radius
        pts.append((int(cx + r * math.cos(angle)), int(cy + r * math.sin(angle))))
    return np.array(pts, np.int32).reshape((-1, 1, 2))


def draw_annotation(img, ann):
    pts = ann["points"]
    color = ann["color"]
    t = ann["thickness"]
    if ann["shape"] == "Free":
        if len(pts) == 1:
            cv2.circle(img, pts[0], max(1, t // 2), color, cv2.FILLED)
        for j in range(1, len(pts)):
            cv2.line(img, pts[j-1], pts[j], color, t, cv2.LINE_AA)
    elif len(pts) >= 2:
        p1, p2 = pts[0], pts[-1]
        if ann["shape"] == "Line":
            cv2.line(img, p1, p2, color, t, cv2.LINE_AA)
        elif ann["shape"] == "Rectangle":
            cv2.rectangle(img, p1, p2, color, t, cv2.LINE_AA)
        elif ann["shape"] == "Circle":
            radius = int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            cv2.circle(img, p1, radius, color, t, cv2.LINE_AA)
        elif ann["shape"] == "Star":
            radius = int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            cv2.polylines(img, [star_points(p1, radius)], True, color, t, cv2.LINE_AA)


def finish_annotation():
    if state.current_ann is not None:
        state.save_undo()
        draw_annotation(state.board, state.current_ann)
        state.current_ann = None


def apply_hold_action(name):
    if name == "undo":
        if state.undo_stack:
            state.board = state.undo_stack.pop()
    elif name == "color":
        state.color_index = (state.color_index + 1) % len(COLORS)
    elif name == "shape":
        state.shape_index = (state.shape_index + 1) % len(SHAPES)
    elif name == "thickness":
        state.thickness_index = (state.thickness_index + 1) % len(THICKNESSES)
    elif name == "recognize":
        if not state.ocr_busy:
            recognize_text_async()
    elif name == "screenshot":
        save_screenshot()
    elif name == "clear":
        state.save_undo()           # undo gesture can bring the drawing back
        state.board = blank_board()
        state.notice = "Canvas cleared (undo to restore)"
        state.notice_until = time.time() + 2.5


def save_screenshot():
    """Save the drawing board as a PNG in SCREENSHOT_DIR."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOT_DIR, time.strftime("drawing_%Y%m%d_%H%M%S.png"))
    if cv2.imwrite(path, state.board):
        print("Screenshot saved:", path)
        state.notice = "Screenshot saved: " + path
    else:
        state.notice = "Screenshot failed"
    state.notice_until = time.time() + 2.5


# -----------------------------
# Text recognition
# -----------------------------
def ink_mask(board):
    """Pixels that have been drawn on (anything that is not white)."""
    return (board.min(axis=2) < 200).astype(np.uint8) * 255


def split_lines(mask):
    """Split the ink into text lines using the horizontal ink profile.
    Returns a list of (y0, y1, x0, x1) boxes from top to bottom."""
    # Join letters of the same line, so small gaps inside a line are not treated as line breaks
    joined = cv2.dilate(mask, np.ones((25, 60), np.uint8))
    rows = np.where(joined.max(axis=1) > 0)[0]
    if len(rows) == 0:
        return []
    bands = []
    start = prev = rows[0]
    for r in rows[1:]:
        if r != prev + 1:
            bands.append((start, prev))
            start = r
        prev = r
    bands.append((start, prev))

    boxes = []
    for y0, y1 in bands:
        ys, xs = np.where(mask[y0:y1 + 1] > 0)
        if len(xs) == 0:
            continue
        # Ignore tiny specks (accidental dots)
        if ys.max() - ys.min() < 12 and xs.max() - xs.min() < 12:
            continue
        boxes.append((y0 + ys.min(), y0 + ys.max(), xs.min(), xs.max()))
    return boxes


def normalize_line(mask, box, target_h=64):
    """Crop one text line and redraw it with a uniform stroke at a fixed height:
    black text on white, which is what OCR engines expect."""
    y0, y1, x0, x1 = box
    crop = mask[y0:y1 + 1, x0:x1 + 1]

    # Thin strokes to 1px skeletons so pen thickness and hand jitter don't matter
    thin = cv2.ximgproc.thinning(crop) if hasattr(cv2, "ximgproc") else crop
    scale = target_h / max(crop.shape[0], 1)
    new_w = max(1, int(crop.shape[1] * scale))
    resized = cv2.resize(thin, (new_w, target_h), interpolation=cv2.INTER_AREA)
    resized = (resized > 0).astype(np.uint8) * 255

    # Even stroke width (about 1/10 of the line height), then a light blur to smooth jitter
    stroke = max(3, target_h // 10)
    thick = cv2.dilate(resized, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (stroke, stroke)))
    thick = cv2.GaussianBlur(thick, (3, 3), 0)
    out = cv2.bitwise_not(thick)
    return cv2.copyMakeBorder(out, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)


def build_ocr_page(line_images):
    """Stack the normalized lines into one page image (for Gemini)."""
    width = max(img.shape[1] for img in line_images)
    padded = [cv2.copyMakeBorder(img, 0, 0, 0, width - img.shape[1],
                                 cv2.BORDER_CONSTANT, value=255) for img in line_images]
    return np.vstack(padded)


def tesseract_line(img):
    """Run Tesseract with a few page modes and keep the most confident answer."""
    best_text, best_conf = "", -1.0
    for psm in (7, 8, 13):
        config = f"--oem 1 --psm {psm}"
        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
        words, confs = [], []
        for word, conf in zip(data["text"], data["conf"]):
            conf = float(conf)
            word = "".join(ch for ch in word if ch.isprintable() and ord(ch) < 128).strip()
            if word and conf >= 0:
                words.append(word)
                confs.append(conf)
        if words:
            mean_conf = sum(confs) / len(confs)
            if mean_conf > best_conf:
                best_text, best_conf = " ".join(words), mean_conf
    return best_text


_gemini_model = None
_gemini_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def gemini_recognize(page):
    global _gemini_model
    if _gemini_model is None:
        import google.generativeai as genai
        key = "AQ.Ab8RN6IUQS9vjTGZc-1ueU8nRK2N_HLozZ5eH3WgpxIx5ZOYwg"
        if not key:
            from ppt_summarizer import api_key as key
        genai.configure(api_key=key)
        _gemini_model = genai.GenerativeModel(GEMINI_MODEL)
    rgb = cv2.cvtColor(page, cv2.COLOR_GRAY2RGB)
    request = _gemini_pool.submit(_gemini_model.generate_content,
                                  [GEMINI_PROMPT, Image.fromarray(rgb)],
                                  generation_config={"temperature": 0})
    # Raises TimeoutError when there is no answer in time, so Tesseract takes over
    return request.result(timeout=GEMINI_TIMEOUT).text.strip()


def recognize_board(board):
    """Returns (text, engine name)."""
    mask = ink_mask(board)
    boxes = split_lines(mask)
    if not boxes:
        return "", None
    line_images = [normalize_line(mask, b) for b in boxes]

    try:
        text = gemini_recognize(build_ocr_page(line_images))
        return text, "Gemini"
    except Exception as e:
        print("Gemini unavailable, using Tesseract:", e)

    lines = [tesseract_line(img) for img in line_images]
    return "\n".join(l for l in lines if l), "Tesseract"


def recognize_text_async():
    """Run recognition in a background thread; the main loop applies the result."""
    snapshot = state.board.copy()
    state.ocr_busy = True
    state.ocr_status = "Recognizing..."

    def worker():
        try:
            text, engine = recognize_board(snapshot)
            text = "\n".join(" ".join(l.split()) for l in text.splitlines() if l.strip())
            if text:
                state.ocr_result = (text, ink_mask(snapshot) > 0)
                state.ocr_status = f"Recognized via {engine}"
            else:
                state.ocr_status = "No text found" if engine else "Board is empty"
        except Exception as e:
            print("OCR error:", e)
            state.ocr_status = "Recognition failed"
        finally:
            state.ocr_busy = False

    threading.Thread(target=worker, daemon=True).start()


def apply_ocr_result():
    """Add recognized text to the panel and wipe the writing that was recognized
    (anything drawn after recognition started is kept)."""
    if state.ocr_result is None:
        return
    text, recognized_mask = state.ocr_result
    state.ocr_result = None
    state.recognized_lines.extend(text.splitlines())
    state.recognized_lines = state.recognized_lines[-30:]
    state.save_undo()
    state.board[recognized_mask] = 255


# -----------------------------
# Panel
# -----------------------------
def wrap_text(text, max_chars):
    words, lines, line = text.split(), [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > max_chars:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return lines


def draw_panel(cam_frame):
    panel = np.full((CANVAS_H, PANEL_W, 3), 40, np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    white = (255, 255, 255)
    highlight = (0, 255, 255)

    # Webcam preview
    panel[0:PREVIEW_H, :] = cv2.resize(cam_frame, (PANEL_W, PREVIEW_H))

    # Color section
    y = PREVIEW_H + 25
    cv2.putText(panel, "COLOR", (15, y), font, 0.55, white, 2)
    for i, (name, bgr) in enumerate(COLORS):
        x0, y0 = 15 + i * 60, y + 10
        cv2.rectangle(panel, (x0, y0), (x0 + 45, y0 + 30), bgr, cv2.FILLED)
        if i == state.color_index:
            cv2.rectangle(panel, (x0 - 3, y0 - 3), (x0 + 48, y0 + 33), white, 3)

    # Shape section (two columns)
    y += 70
    cv2.putText(panel, "SHAPE", (15, y), font, 0.55, white, 2)
    for i, name in enumerate(SHAPES):
        x0 = 10 + (i % 2) * 140
        y0 = y + 8 + (i // 2) * 26
        selected = i == state.shape_index
        if selected:
            cv2.rectangle(panel, (x0, y0), (x0 + 135, y0 + 23), (90, 90, 90), cv2.FILLED)
        c = highlight if selected else white
        if name == "Free":
            cv2.line(panel, (x0 + 8, y0 + 17), (x0 + 14, y0 + 6), c, 2)
            cv2.line(panel, (x0 + 14, y0 + 6), (x0 + 20, y0 + 17), c, 2)
            cv2.line(panel, (x0 + 20, y0 + 17), (x0 + 26, y0 + 6), c, 2)
        elif name == "Line":
            cv2.line(panel, (x0 + 8, y0 + 18), (x0 + 26, y0 + 5), c, 2)
        elif name == "Rectangle":
            cv2.rectangle(panel, (x0 + 8, y0 + 5), (x0 + 26, y0 + 18), c, 2)
        elif name == "Circle":
            cv2.circle(panel, (x0 + 17, y0 + 11), 7, c, 2)
        elif name == "Star":
            cv2.polylines(panel, [star_points((x0 + 17, y0 + 12), 9)], True, c, 1)
        label = "Pen" if name == "Free" else name
        cv2.putText(panel, label, (x0 + 34, y0 + 17), font, 0.45, c, 1)

    # Thickness section
    y += 100
    cv2.putText(panel, "THICKNESS", (15, y), font, 0.55, white, 2)
    for i, t in enumerate(THICKNESSES):
        x0 = 10 + i * 95
        y0 = y + 8
        selected = i == state.thickness_index
        if selected:
            cv2.rectangle(panel, (x0, y0), (x0 + 88, y0 + 23), (90, 90, 90), cv2.FILLED)
        c = highlight if selected else white
        cv2.line(panel, (x0 + 6, y0 + 12), (x0 + 40, y0 + 12),
                 COLORS[state.color_index][1] if selected else c, t)
        cv2.putText(panel, f"{t}px", (x0 + 48, y0 + 17), font, 0.45, c, 1)

    # Recognized text section
    y += 60
    cv2.line(panel, (10, y - 18), (PANEL_W - 10, y - 18), (90, 90, 90), 1)
    cv2.putText(panel, "RECOGNIZED TEXT", (15, y), font, 0.55, white, 2)
    lines = []
    for text in state.recognized_lines:
        lines.extend(wrap_text(text, 26))
    max_lines = (CANVAS_H - 30 - (y + 10)) // 22
    for i, line in enumerate(lines[-max_lines:] if max_lines > 0 else []):
        cv2.putText(panel, "> " + line, (15, y + 28 + i * 22), font, 0.55, (220, 220, 220), 1)

    status_color = highlight if state.ocr_busy else (150, 220, 150)
    cv2.putText(panel, state.ocr_status, (15, CANVAS_H - 12), font, 0.45, status_color, 1)
    return panel


def draw_hints(view):
    gray = (130, 130, 130)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(view, "Index: draw | Index+Middle: move | Fist: erase | "
                "Hold - Index+Mid+Ring: undo | Open palm: recognize",
                (10, CANVAS_H - 72), font, 0.45, gray, 1)
    cv2.putText(view, "Hold - Index+Pinky: color | Pinky: shape | Mid+Ring+Pinky: size | "
                "Index+Mid+Pinky: screenshot | Ring+Pinky: clear all",
                (10, CANVAS_H - 52), font, 0.45, gray, 1)
    cv2.putText(view, "Keys: r recognize, s screenshot, x clear text, c clear board, q quit",
                (10, CANVAS_H - 32), font, 0.45, gray, 1)

    if time.time() < state.notice_until:
        cv2.putText(view, state.notice, (10, 30), font, 0.6, (0, 150, 0), 2)

    # Progress of the hold gesture currently being made
    if state.hold_gesture:
        progress = min(state.hold_count / HOLD_FRAMES, 1.0)
        cv2.putText(view, "Hold: " + state.hold_gesture, (10, CANVAS_H - 90), font, 0.55, (0, 140, 255), 2)
        cv2.rectangle(view, (10, CANVAS_H - 82), (210, CANVAS_H - 72), (150, 150, 150), 1)
        cv2.rectangle(view, (10, CANVAS_H - 82), (10 + int(200 * progress), CANVAS_H - 72),
                      (0, 140, 255), cv2.FILLED)


# -----------------------------
# Main loop
# -----------------------------
def handle_hand(hand_landmarks):
    """Update the board from one frame of hand landmarks. Returns the cursor to draw."""
    fingers = fingers_up(hand_landmarks)[1:]   # thumb ignored

    # Smooth the index fingertip so handwriting is less shaky
    target = to_board(hand_landmarks[8])
    if state.cursor is None:
        state.cursor = target
    else:
        state.cursor = (int(state.cursor[0] * SMOOTHING + target[0] * (1 - SMOOTHING)),
                        int(state.cursor[1] * SMOOTHING + target[1] * (1 - SMOOTHING)))
    pos = state.cursor
    color = COLORS[state.color_index][1]
    thickness = THICKNESSES[state.thickness_index]

    # Hold gestures (undo / color / shape / thickness / recognize)
    hold = None
    for name, pattern in HOLD_GESTURES.items():
        if fingers == pattern:
            hold = name
    if hold != state.hold_release:
        state.hold_release = None
    else:
        hold = None
    if hold is not None and hold == state.hold_gesture:
        state.hold_count += 1
    else:
        state.hold_count = 0
    state.hold_gesture = hold
    if hold and state.hold_count >= HOLD_FRAMES:
        finish_annotation()
        apply_hold_action(hold)
        state.hold_release = hold
        state.hold_gesture = None
        state.hold_count = 0

    # Draw (index finger only)
    if fingers == GESTURE_DRAW:
        if state.current_ann is None:
            state.current_ann = {"shape": SHAPES[state.shape_index], "color": color,
                                 "thickness": thickness, "points": [pos]}
        elif state.current_ann["shape"] == "Free":
            state.current_ann["points"].append(pos)
        else:
            # Line / Rectangle / Circle / Star: first point is fixed, second follows the finger
            state.current_ann["points"][1:] = [pos]
        return (pos, max(4, thickness // 2 + 2), color, cv2.FILLED)
    finish_annotation()

    # Eraser (closed fist): rubs out ink under the palm
    if fingers == GESTURE_ERASE:
        palm = to_board(hand_landmarks[9])
        if not state.erasing:
            state.save_undo()
            state.erasing = True
            state.prev_eraser = palm
        cv2.line(state.board, state.prev_eraser, palm, (255, 255, 255), ERASER_RADIUS * 2)
        cv2.circle(state.board, palm, ERASER_RADIUS, (255, 255, 255), cv2.FILLED)
        state.prev_eraser = palm
        return (palm, ERASER_RADIUS, (120, 120, 120), 2)
    state.erasing = False

    # Any other gesture just shows where the finger is (pen up)
    return (pos, 8, color, 2)


def select_presenter_hand(hands, faces, frame_w, frame_h):
    """Landmarks of the presenter's hand (the one closest to the presenter's face), or None.
    Each hand belongs to the face nearest to its wrist."""
    best_hand, best_dist = None, None
    for hand in hands:
        wx, wy = hand[0].x * frame_w, hand[0].y * frame_h
        nearest = None
        for (left, top, right, bottom), is_presenter in faces:
            face_w = max(right - left, 1)
            fx, fy = (left + right) / 2, (top + bottom) / 2
            dist = math.hypot((wx - fx) / face_w, 0.5 * (wy - fy) / face_w)
            if nearest is None or dist < nearest[0]:
                nearest = (dist, is_presenter)
        if nearest and nearest[1] and nearest[0] <= MAX_HAND_DISTANCE:
            if best_dist is None or nearest[0] < best_dist:
                best_hand, best_dist = hand, nearest[0]
    return best_hand


def draw_presenter_info(frame, faces, tracking):
    """Face boxes (green = presenter, red = others) on the webcam preview."""
    for (left, top, right, bottom), is_presenter in faces:
        color = (0, 255, 0) if is_presenter else (0, 0, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 3)
        cv2.putText(frame, "PRESENTER" if is_presenter else "IGNORED", (left, max(30, top - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
    if not tracking:
        cv2.putText(frame, "Presenter not found", (20, frame.shape[0] - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)


def main3(reference_image=REFERENCE_IMAGE):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CANVAS_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CANVAS_H)

    # Presenter face tracking (same as the slide window). Without a usable reference
    # image every hand is accepted.
    try:
        tracker = PresenterTracker(reference_image)
        print("Presenter tracking enabled with", reference_image)
    except Exception as e:
        tracker = None
        print("Presenter tracking disabled:", e)

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection_result = landmarker.detect(mp_image)

        hands = detection_result.hand_landmarks
        if tracker is not None:
            tracker.update(frame.copy())
            tracking = tracker.presenter_visible()
            presenter = select_presenter_hand(hands, tracker.faces, frame.shape[1],
                                              frame.shape[0]) if tracking else None
            hands = [presenter] if presenter is not None else []
            draw_presenter_info(frame, tracker.faces, tracking)
        else:
            hands = hands[:1]

        cursor = None
        if hands:
            hand_landmarks = hands[0]
            draw_landmarks_custom(frame, hand_landmarks)
            cursor = handle_hand(hand_landmarks)
        else:
            # Hand left the camera: finish whatever was being drawn
            finish_annotation()
            state.cursor = None
            state.erasing = False
            state.hold_gesture = None
            state.hold_count = 0

        apply_ocr_result()

        view = state.board.copy()
        if state.current_ann is not None:
            draw_annotation(view, state.current_ann)
        if cursor is not None:
            cv2.circle(view, *cursor)
        draw_hints(view)

        cv2.imshow("Air Drawing - Hand Gesture", np.hstack((view, draw_panel(frame))))

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            finish_annotation()
            state.save_undo()
            state.board = blank_board()
        elif key == ord('r'):
            finish_annotation()
            if not state.ocr_busy:
                recognize_text_async()
        elif key == ord('s'):
            finish_annotation()
            save_screenshot()
        elif key == ord('x'):
            state.recognized_lines = []

    if tracker is not None:
        tracker.stop()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if not os.path.exists(MODEL_PATH):
        print(f"ERROR: Model file '{MODEL_PATH}' not found.")
        print("Download: https://storage.googleapis.com/mediapipe-models/"
              "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task")
    else:
        main3()
