import os
import math
import cv2
from cvzone.HandTrackingModule import HandDetector
import numpy as np
import winsound
import time
import pyttsx3
import threading
import queue
import re
import subprocess
import concurrent.futures
from datetime import datetime
import speech_recognition as sr

# Variables
from face_verification import face_verify
from ppt_splitter import ppt_to_images
from speaker_verification import load_verifier, audio_from_microphone

width = 1280
height = 720

# Drawing tool panel (shown on the right side of the slide window)
PANEL_W = 220
COLORS = [
    ("Blue",  (255, 0, 0)),
    ("Red",   (0, 0, 255)),
    ("Green", (0, 200, 0)),
]
# "Free" is the normal pen used for writing; the other four are the shapes
SHAPES = ["Free", "Line", "Rectangle", "Circle", "Star"]
THICKNESSES = [2, 4, 6]

# Eraser (closed fist) - rubs out ink under the hand like a real eraser
ERASER_RADIUS = 25
MAX_UNDO = 20

# Selection gestures (thumb is ignored, only index, middle, ring, pinky are checked)
# These only work when the hand is BELOW the yellow gesture line
SELECT_GESTURES = {
    "color":     [1, 0, 0, 1],   # Index + Pinky   (rock sign)
    "shape":     [0, 0, 0, 1],   # Pinky only
    "thickness": [0, 1, 1, 1],   # Middle + Ring + Pinky (index folded)
    "brightness increase":   [1, 1, 0, 1],   # Index + Middle + Pinky (ring folded)
    "brightness decrease": [0, 1, 0, 1],   # Middle + Pinky (index and ring folded)
    "clear all": [0, 0, 1, 1],   # Ring + Pinky
}
selectHoldFrames = 10   # frames a selection gesture must be held before it is applied

# Screenshot gesture: open palm (all four fingers up, thumb ignored), works anywhere, hold to take
SCREENSHOT_GESTURE = [1, 1, 1, 1]
SCREENSHOT_FOLDER = "screenshots"

# Screen brightness (laptop / built-in display, set through Windows WMI)
BRIGHTNESS_STEP = 5
brightness_result_queue = queue.Queue()
_brightness_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)   # one change at a time

# Voice commands (recognized in a background thread, handled in the main loop)
voice_command_queue = queue.Queue()
voice_status = {"text": "Mic: starting..."}


def listen_for_commands(stop_listening, voiceprint=None):
    """Continuously listen for voice commands in a separate thread.
    With a voiceprint, only commands spoken by the presenter are passed on."""
    verifier = None
    if voiceprint:
        voice_status["text"] = "Mic: loading voice model..."
        try:
            verifier = load_verifier(voiceprint)
        except Exception as e:
            # The presenter enrolled a voice but it cannot be checked: do not let anyone in
            print(f"Voice commands disabled (speaker verification error): {e}")
            voice_status["text"] = "Voice check failed: cmds off"
            return
    if verifier is None:
        print("Speaker verification off (no voiceprint) - any voice is accepted")

    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.6        # silence that ends a phrase
    recognizer.non_speaking_duration = 0.4

    try:
        microphone = sr.Microphone()
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
    except Exception as e:
        print(f"Voice control disabled (microphone error): {e}")
        voice_status["text"] = "Mic: not available"
        return

    # The microphone stays open and records in its own thread, so nothing said while an
    # earlier phrase is still being recognized / verified is lost.
    audio_queue = queue.Queue()
    stop_recording = recognizer.listen_in_background(
        microphone, lambda _r, audio: audio_queue.put(audio), phrase_time_limit=4)
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def transcribe(audio):
        return recognizer.recognize_google(audio).lower().strip()

    voice_status["text"] = "Mic: listening (presenter)" if verifier else "Mic: listening (any voice)"
    while not stop_listening.is_set():
        try:
            audio = audio_queue.get(timeout=0.3)
        except queue.Empty:
            continue
        # Fell behind: drop stale phrases so commands do not run late
        while audio_queue.qsize() > 1:
            audio = audio_queue.get_nowait()
        try:
            # Speech-to-text (network) and speaker check (CPU) run at the same time
            check = pool.submit(verifier.verify, audio_from_microphone(audio)) if verifier else None
            command = transcribe(audio)
            print(f"Voice command detected: '{command}'")
            if parse_voice_command(command) is None:
                voice_status["text"] = 'No command: "' + command + '"'
                continue
            if check is not None:
                accepted, score = check.result()
                print(f"  speaker similarity {score:.2f} -> {'presenter' if accepted else 'OTHER SPEAKER, ignored'}")
                if not accepted:
                    voice_status["text"] = 'Not presenter: "' + command + '"'
                    continue
            voice_command_queue.put(command)
        except sr.UnknownValueError:
            pass  # Could not understand audio
        except sr.RequestError as e:
            print(f"Speech recognition service error: {e}")
            voice_status["text"] = "Mic: no internet"
        except Exception as e:
            print(f"Listening error: {e}")
    stop_recording(wait_for_stop=False)
    pool.shutdown(wait=False)


def parse_voice_command(command):
    """Map a recognized phrase to an action name, or None (whole words only)."""
    words = set(re.findall(r"[a-z]+", command))
    if words & {"bright", "brightness", "brighter", "dim", "dark", "darker"}:
        if words & {"down", "decrease", "reduce", "lower", "dim", "dark", "darker", "less"}:
            return "brightness down"
        if words & {"up", "increase", "raise", "higher", "brighter", "more"}:
            return "brightness up"
    if words & {"clear", "wipe", "reset"} or "erase all" in command:
        return "clear all"
    if words & {"screenshot", "capture"} or "screen shot" in command:
        return "screenshot"
    if "next" in words:
        return "next"
    if words & {"previous", "back"}:
        return "previous"
    if words & {"close slide", "close", "exit slide", "exit", "quit"}:
        return "close"
    return None


def _set_brightness(delta):
    """Change the screen brightness by delta (0-100) and report the new level."""
    script = (
        "$b = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness | "
        "Select-Object -First 1).CurrentBrightness; "
        f"$n = [Math]::Max(0, [Math]::Min(100, $b + ({delta}))); "
        "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
        "Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{Timeout=0; Brightness=[byte]$n} | Out-Null; "
        "$n"
    )
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        level = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if result.returncode == 0 and level.isdigit():
            print("Brightness set to", level)
            brightness_result_queue.put(f"Brightness: {level}%")
            return
        print("Brightness change failed:", result.stderr.strip())
    except Exception as e:
        print("Brightness change failed:", e)
    brightness_result_queue.put("Brightness control not supported on this display")


def change_brightness(delta):
    print("Called update")
    """Runs in the background so the video does not freeze while PowerShell starts."""
    _brightness_pool.submit(_set_brightness, delta)


def save_screenshot(img):
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    filename = datetime.now().strftime("slide_%Y%m%d_%H%M%S_%f")[:-3] + ".png"
    path = os.path.join(SCREENSHOT_FOLDER, filename)
    cv2.imwrite(path, img)
    winsound.MessageBeep()
    print("Screenshot saved:", path)
    return path


def star_points(center, outer_radius):
    cx, cy = center
    inner_radius = outer_radius * 0.4
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = outer_radius if i % 2 == 0 else inner_radius
        pts.append((int(cx + r * math.cos(angle)), int(cy + r * math.sin(angle))))
    return np.array(pts, np.int32).reshape((-1, 1, 2))


def draw_annotation(img, ann, color=None):
    pts = ann["points"]
    color = ann["color"] if color is None else color
    t = ann["thickness"]
    if ann["shape"] == "Free":
        for j in range(1, len(pts)):
            cv2.line(img, pts[j-1], pts[j], color, t)
    elif len(pts) >= 2:
        p1, p2 = pts[0], pts[-1]
        if ann["shape"] == "Line":
            cv2.line(img, p1, p2, color, t)
        elif ann["shape"] == "Rectangle":
            cv2.rectangle(img, p1, p2, color, t)
        elif ann["shape"] == "Circle":
            radius = int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            cv2.circle(img, p1, radius, color, t)
        elif ann["shape"] == "Star":
            radius = int(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            cv2.polylines(img, [star_points(p1, radius)], True, color, t)


def draw_panel(h, colorIndex, shapeIndex, thicknessIndex, selectGesture, selectHold):
    panel = np.full((h, PANEL_W, 3), 40, np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    white = (255, 255, 255)
    highlight = (0, 255, 255)

    # Color section
    cv2.putText(panel, "COLOR", (15, 28), font, 0.6, white, 2)
    for i, (name, bgr) in enumerate(COLORS):
        x0 = 15 + i * 65
        y0 = 40
        cv2.rectangle(panel, (x0, y0), (x0 + 50, y0 + 40), bgr, cv2.FILLED)
        if i == colorIndex:
            cv2.rectangle(panel, (x0 - 3, y0 - 3), (x0 + 53, y0 + 43), white, 3)
        else:
            cv2.rectangle(panel, (x0, y0), (x0 + 50, y0 + 40), (120, 120, 120), 1)

    # Shape section
    cv2.putText(panel, "SHAPE", (15, 112), font, 0.6, white, 2)
    for i, name in enumerate(SHAPES):
        y0 = 122 + i * 28
        selected = i == shapeIndex
        if selected:
            cv2.rectangle(panel, (10, y0), (PANEL_W - 10, y0 + 25), (90, 90, 90), cv2.FILLED)
        c = highlight if selected else white
        if name == "Free":
            cv2.line(panel, (20, y0 + 18), (28, y0 + 6), c, 2)
            cv2.line(panel, (28, y0 + 6), (36, y0 + 18), c, 2)
            cv2.line(panel, (36, y0 + 18), (44, y0 + 6), c, 2)
        elif name == "Line":
            cv2.line(panel, (20, y0 + 20), (44, y0 + 5), c, 2)
        elif name == "Rectangle":
            cv2.rectangle(panel, (20, y0 + 5), (44, y0 + 20), c, 2)
        elif name == "Circle":
            cv2.circle(panel, (32, y0 + 12), 8, c, 2)
        elif name == "Star":
            cv2.polylines(panel, [star_points((32, y0 + 13), 10)], True, c, 1)
        label = "Pen (free)" if name == "Free" else name
        cv2.putText(panel, label, (55, y0 + 18), font, 0.5, c, 1)

    # Thickness section
    cv2.putText(panel, "THICKNESS", (15, 285), font, 0.6, white, 2)
    for i, t in enumerate(THICKNESSES):
        y0 = 295 + i * 28
        selected = i == thicknessIndex
        if selected:
            cv2.rectangle(panel, (10, y0), (PANEL_W - 10, y0 + 25), (90, 90, 90), cv2.FILLED)
        c = highlight if selected else white
        cv2.line(panel, (20, y0 + 12), (130, y0 + 12), COLORS[colorIndex][1] if selected else c, t)
        cv2.putText(panel, str(t) + "px", (145, y0 + 18), font, 0.5, c, 1)

    # Gesture hints
    hints = ["Fist : Eraser",
             "Open palm : Screenshot",
             "Below yellow line:",
             "Index+Pinky : Color",
             "Pinky only  : Shape",
             "Mid+Ring+Pinky : Size",
             "Idx+Mid+Pinky : Bright +",
             "Mid+Pinky : Bright -"
             "Ring+Pinky : Clear all",]
    for i, text in enumerate(hints):
        cv2.putText(panel, text, (12, 388 + i * 14), font, 0.42, (200, 200, 200), 1)

    # Voice control status / last command heard
    cv2.putText(panel, voice_status["text"][:30], (12, 506), font, 0.42, (120, 220, 120), 1)

    # Hold progress for the selection gesture currently being made
    if selectGesture:
        progress = min(selectHold / selectHoldFrames, 1.0)
        cv2.putText(panel, "Hold: " + selectGesture, (12, h - 22), font, 0.45, highlight, 1)
        cv2.rectangle(panel, (12, h - 15), (PANEL_W - 12, h - 7), (120, 120, 120), 1)
        cv2.rectangle(panel, (12, h - 15), (12 + int((PANEL_W - 24) * progress), h - 7), highlight, cv2.FILLED)

    return panel


# -----------------------------
# Presenter detection: only the hands of the person whose face matches the
# reference image are used for gestures (other people in the frame are ignored)
# -----------------------------
REFERENCE_IMAGE = "a.jpg"   # default reference face; main_func can be given another one
MAX_HANDS = 4                   # detect several hands, then keep only the presenter's
FACE_CHECK_INTERVAL = 0.5       # seconds between face recognition runs (runs in the background)
FACE_SCALE = 0.5                # frame is shrunk for face recognition (faster)
FACE_TOLERANCE = 0.5            # lower = stricter face match
PRESENTER_MEMORY = 2.0          # keep using the last presenter position this long if the face is lost
MAX_HAND_DISTANCE = 6.0         # a hand farther than this (in face widths) from every face is ignored


class PresenterTracker:
    """Finds the presenter's face in the background, a couple of times per second.
    The main loop only reads the latest result, so the video never waits for face recognition."""

    def __init__(self, reference_path):
        print("Tracking ", reference_path)
        # reference_path=r"C:\Users\Project\PycharmProjects\hand_gestured_based_ppt_controlling\images\\"+reference_path
        import face_recognition
        self.fr = face_recognition
        image = face_recognition.load_image_file(reference_path)
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            raise ValueError(f"No face found in reference image '{reference_path}'")
        self.reference = encodings[0]
        self.frame = None
        self.faces = []             # [((left, top, right, bottom), is_presenter)] in frame pixels
        self.last_seen = 0.0        # time the presenter's face was last recognized
        self.stop_event = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def update(self, frame):
        self.frame = frame

    def stop(self):
        self.stop_event.set()

    def presenter_visible(self):
        return time.time() - self.last_seen <= PRESENTER_MEMORY

    def _run(self):
        while not self.stop_event.is_set():
            started = time.time()
            frame = self.frame
            if frame is not None:
                try:
                    self._check(frame)
                except Exception as e:
                    print("Face check error:", e)
            self.stop_event.wait(max(0.0, FACE_CHECK_INTERVAL - (time.time() - started)))

    def _check(self, frame):
        small = cv2.resize(frame, None, fx=FACE_SCALE, fy=FACE_SCALE)
        rgb = np.ascontiguousarray(small[:, :, ::-1])
        locations = self.fr.face_locations(rgb)
        if not locations:
            if not self.presenter_visible():
                self.faces = []
            return
        encodings = self.fr.face_encodings(rgb, locations)
        distances = self.fr.face_distance(encodings, self.reference)
        best = int(np.argmin(distances))
        presenter = best if distances[best] <= FACE_TOLERANCE else None

        faces = []
        for i, (top, right, bottom, left) in enumerate(locations):
            box = tuple(int(v / FACE_SCALE) for v in (left, top, right, bottom))
            faces.append((box, i == presenter))
        if presenter is not None:
            self.last_seen = time.time()
            self.faces = faces
        elif not self.presenter_visible():
            self.faces = faces
        # else: presenter briefly not recognized (head turned) - keep the last known positions


def select_presenter_hand(hands, faces):
    """Each hand belongs to the face nearest to its wrist (horizontal distance counts
    more, since hands are usually beside / below their own face). Returns the
    presenter's hand closest to their face, or None."""
    best_hand, best_dist = None, None
    for hand in hands:
        wx, wy = hand["lmList"][0][:2]
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


def draw_presenter_info(img, faces, presenter_hand, tracking):
    """Face boxes (green = presenter, red = others) and the hand in use, on the webcam preview."""
    for (left, top, right, bottom), is_presenter in faces:
        color = (0, 255, 0) if is_presenter else (0, 0, 255)
        cv2.rectangle(img, (left, top), (right, bottom), color, 6)
        cv2.putText(img, "PRESENTER" if is_presenter else "IGNORED", (left, max(40, top - 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.6, color, 4)
    if presenter_hand is not None:
        x, y, bw, bh = presenter_hand["bbox"]
        cv2.rectangle(img, (x - 20, y - 20), (x + bw + 20, y + bh + 20), (0, 255, 0), 6)
    if not tracking:
        cv2.putText(img, "Presenter not found", (20, height - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 5)


def main_func(ppt_path, reference_image=REFERENCE_IMAGE, voiceprint=None):
    ppt_to_images(ppt_path)
    folderPath = "Resources"
    w = 960
    h = 540

    # Camera Setup
    cap = cv2.VideoCapture(0)
    cap.set(3, width)
    cap.set(4, height)

    # Get the list of presentation images
    pathImages = sorted(os.listdir(folderPath), key=len)
    # print(pathImages)

    # Variables
    imgNumber = 0
    ws, hs = 213, 120
    gestureThreshold = 300
    buttonPressed = False
    buttonCounter = 0
    buttonDelay = 20
    annotationStart = False

    # Ink is kept as a pixel layer so the eraser can rub out any part of it.
    # inkMask > 0 marks the pixels that currently have ink, inkLayer holds their colors.
    inkLayer = np.zeros((h, w, 3), np.uint8)
    inkMask = np.zeros((h, w), np.uint8)
    currentAnn = None       # stroke / shape being drawn right now (not yet on the ink layer)
    undoStack = []          # snapshots of (inkLayer, inkMask) for the undo gesture
    erasing = False
    prevEraserPos = None

    # Screenshot (voice or open-palm gesture) and on-slide message
    takeScreenshot = False
    screenshotRelease = False   # palm must be lowered before another gesture screenshot
    message = ""
    messageFrames = 0

    # Drawing tool selection
    colorIndex = 0
    shapeIndex = 0
    thicknessIndex = 1
    selectGesture = None
    selectHold = 0

    # Hand Detector (several hands; only the presenter's is used)
    detector = HandDetector(detectionCon=0.7, maxHands=MAX_HANDS)

    # Presenter face tracking. Without a usable reference image every hand is
    # accepted, like before.
    try:
        tracker = PresenterTracker(reference_image)
        print("Presenter tracking enabled with", reference_image)
    except Exception as e:
        tracker = None
        print("Presenter tracking disabled:", e)

    def save_undo():
        undoStack.append((inkLayer.copy(), inkMask.copy()))
        if len(undoStack) > MAX_UNDO:
            undoStack.pop(0)

    def clear_ink():
        inkLayer[:] = 0
        inkMask[:] = 0
        undoStack.clear()

    def clear_all_ink():
        """Wipe all annotations on the slide; the undo gesture can restore them."""
        nonlocal annotationStart, currentAnn
        annotationStart = False
        currentAnn = None
        save_undo()
        inkLayer[:] = 0
        inkMask[:] = 0

    # Start voice listening thread (each presentation gets its own stop flag)
    while not voice_command_queue.empty():
        voice_command_queue.get_nowait()
    stop_listening = threading.Event()
    threading.Thread(target=listen_for_commands, args=(stop_listening, voiceprint), daemon=True).start()
    print("Voice commands available: 'next slide', 'previous slide', 'screenshot', "
          "'brightness up', 'brightness down', 'clear'")

    while True:
        # Import Images
        success, img = cap.read()
        img = cv2.flip(img, 1)

        # Voice commands
        while not voice_command_queue.empty():
            command = voice_command_queue.get_nowait()
            action = parse_voice_command(command)
            voice_status["text"] = 'Heard: "' + command + '"'
            if action == "next" and imgNumber < len(pathImages) - 1:
                annotationStart = False
                currentAnn = None
                clear_ink()
                imgNumber += 1
            elif action == "previous" and imgNumber > 0:
                annotationStart = False
                currentAnn = None
                clear_ink()
                imgNumber -= 1
            elif action == "clear all":
                clear_all_ink()
            elif action == "screenshot":
                takeScreenshot = True
            elif action == "brightness up" or action == "brightness increase":
                print("Calling BU")
                change_brightness(BRIGHTNESS_STEP)
            elif action == "brightness down" or action == "brightness decrease":
                print("Calling BD")
                change_brightness(-BRIGHTNESS_STEP)
            elif action == "close":
                stop_listening.set()
                if tracker is not None:
                    tracker.stop()
                cv2.destroyAllWindows()
                return "ok"

        # Result of the last brightness change (comes from the background worker)
        while not brightness_result_queue.empty():
            message = brightness_result_queue.get_nowait()
            messageFrames = 45

        pathFullImage = os.path.join(folderPath, pathImages[imgNumber])
        imgCurrent = cv2.imread(pathFullImage)
        imgSlide = cv2.resize(imgCurrent, (w, h))

        drawColor = COLORS[colorIndex][1]
        drawThickness = THICKNESSES[thicknessIndex]
        cursor = None   # (position, radius, color, thickness) drawn on top of the ink

        hands, img = detector.findHands(img, draw=False)
        if tracker is not None:
            tracker.update(img.copy())
            faces = tracker.faces
            tracking = tracker.presenter_visible()
            presenterHand = select_presenter_hand(hands, faces) if tracking else None
            hands = [presenterHand] if presenterHand is not None else []
            draw_presenter_info(img, faces, presenterHand, tracking)
        else:
            hands = hands[:1]
        cv2.line(img, (0, gestureThreshold), (width, gestureThreshold), (0, 255, 255), 5)

        isFist = False

        if hands and buttonPressed is False:
            hand = hands[0]
            fingers = detector.fingersUp(hand)
            cx, cy = hand['center']
            lmList = hand['lmList']

            # Constrain values for easier pointer drawing

            xVal = int(np.interp(lmList[8][0], [width // 2, w], [0, width]))
            yVal = int(np.interp(lmList[8][1], [150, height-150], [0, height]))
            indexFinger = xVal, yVal

            # Closed fist (all four fingers folded, thumb ignored)
            isFist = fingers[1:] == [0, 0, 0, 0]

            if cy <= gestureThreshold: # If hand is at the height of the face
                annotationStart = False
                print("Fingers : ", fingers)
                # Gesture 1 - Left : previous slide
                if fingers == [1, 0, 0, 1, 0]:
                    annotationStart = False
                    if imgNumber > 0:
                        buttonPressed = True
                        currentAnn = None
                        clear_ink()
                        imgNumber -= 1

                # Gesture 2 - Right : next slide
                if fingers == [1, 0, 0, 0, 1]:
                    annotationStart = False
                    if imgNumber < len(pathImages) - 1:
                        buttonPressed = True
                        currentAnn = None
                        clear_ink()
                        imgNumber += 1

            # Gestures 6, 7, 8, 11 - Select color / shape / thickness, brightness +/- (hand below the line, hold to apply)
            currentSelect = None
            if cy > gestureThreshold:
                for name, pattern in SELECT_GESTURES.items():
                    if fingers[1:] == pattern:
                        currentSelect = name

            # Gesture 10 - Screenshot (open palm anywhere, hold to apply)
            if fingers[1:] == SCREENSHOT_GESTURE:
                if not screenshotRelease:
                    currentSelect = "screenshot"
            else:
                screenshotRelease = False
            if currentSelect is not None and currentSelect == selectGesture:
                selectHold += 1
            else:
                selectHold = 0
            selectGesture = currentSelect
            if selectGesture and selectHold >= selectHoldFrames:
                print("Slected gesture:", selectGesture)
                print(selectHold,">", selectHoldFrames)
                if selectGesture == "color":
                    colorIndex = (colorIndex + 1) % len(COLORS)
                elif selectGesture == "shape":
                    shapeIndex = (shapeIndex + 1) % len(SHAPES)
                elif selectGesture == "thickness":
                    thicknessIndex = (thicknessIndex + 1) % len(THICKNESSES)
                elif selectGesture == "screenshot":
                    takeScreenshot = True
                    screenshotRelease = True
                elif selectGesture == "clear all":
                    clear_all_ink()
                elif selectGesture == "brightness up" or selectGesture == "brightness increase":
                    change_brightness(BRIGHTNESS_STEP)
                elif selectGesture == "brightness down" or selectGesture == "brightness decrease":
                    change_brightness(-BRIGHTNESS_STEP)
                selectGesture = None
                selectHold = 0
                buttonPressed = True

            # Gesture 3 - Show Pointer
            if fingers == [0, 1, 1, 0, 0] or fingers == [1, 1, 1, 0, 0]:
                cursor = (indexFinger, 10, (0, 0, 255), cv2.FILLED)
                annotationStart = False

            # Gesture 4 - Draw Pointer (uses selected color, shape and thickness)
            if fingers == [0, 1, 0, 0, 0] or fingers == [1, 1, 0, 0, 0]:
                if annotationStart is False:
                    annotationStart = True
                    currentAnn = {"shape": SHAPES[shapeIndex],
                                  "color": drawColor,
                                  "thickness": drawThickness,
                                  "points": [indexFinger]}
                elif currentAnn["shape"] == "Free":
                    currentAnn["points"].append(indexFinger)
                else:
                    # Line / Rectangle / Circle / Star: first point is fixed, second follows the finger
                    currentAnn["points"][1:] = [indexFinger]
                cursor = (indexFinger, max(5, drawThickness // 2 + 2), drawColor, cv2.FILLED)

            else:
                annotationStart = False

            # Gesture 5 - Undo (restores the ink as it was before the last stroke / erase)
            if fingers == [0, 1, 1, 1, 0] or fingers == [1, 1, 1, 1, 0]:
                if undoStack:
                    inkLayer[:], inkMask[:] = undoStack.pop()
                    buttonPressed = True
        else:
            annotationStart = False
            if not hands:
                selectGesture = None
                selectHold = 0

        # A finished stroke / shape is burned into the ink layer
        if annotationStart is False and currentAnn is not None:
            save_undo()
            draw_annotation(inkLayer, currentAnn)
            draw_annotation(inkMask, currentAnn, 255)
            currentAnn = None

        # Gesture 9 - Eraser (closed fist): rubs out ink under the hand
        if isFist:
            eraserPos = (int(np.interp(cx, [width // 2, w], [0, width])),
                         int(np.interp(cy, [150, height-150], [0, height])))
            if not erasing:
                save_undo()
                erasing = True
                prevEraserPos = eraserPos
            # Erase along the path from the last position so fast moves leave no gaps
            cv2.line(inkMask, prevEraserPos, eraserPos, 0, ERASER_RADIUS * 2)
            cv2.circle(inkMask, eraserPos, ERASER_RADIUS, 0, cv2.FILLED)
            prevEraserPos = eraserPos
            cursor = (eraserPos, ERASER_RADIUS, (80, 80, 80), 2)
        else:
            erasing = False
            prevEraserPos = None

        # Button Pressed Iterations
        if buttonPressed:
            buttonCounter += 1
            if buttonCounter > buttonDelay:
                buttonCounter = 0
                buttonPressed = False

        inked = inkMask > 0
        imgSlide[inked] = inkLayer[inked]
        if currentAnn is not None:
            draw_annotation(imgSlide, currentAnn)
        # Screenshot = slide + drawings (without the cursor, webcam preview and panel)
        if takeScreenshot:
            path = save_screenshot(imgSlide)
            message = "Screenshot saved: " + os.path.basename(path)
            messageFrames = 45
            takeScreenshot = False

        if cursor is not None:
            cv2.circle(imgSlide, *cursor)

        if messageFrames > 0:
            messageFrames -= 1
            cv2.rectangle(imgSlide, (10, h - 45), (w - 10, h - 10), (0, 0, 0), cv2.FILLED)
            cv2.putText(imgSlide, message, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Adding a webcam image on the slides
        imgSmall = cv2.resize(img, (ws, hs))
        imgSlide[0:hs, w-ws:w] = imgSmall

        # Adding the color / shape / thickness panel next to the slide
        panel = draw_panel(h, colorIndex, shapeIndex, thicknessIndex, selectGesture, selectHold)
        imgWindow = np.hstack((imgSlide, panel))

        cv2.imshow("Slides", imgWindow)
        # cv2.imshow("Image", img)
        key = cv2.waitKey(1)
        if key == ord('q'):
            # break
            stop_listening.set()
            if tracker is not None:
                tracker.stop()
            return "ok"
        # Keyboard shortcuts for the panel
        elif key == ord('c'):
            colorIndex = (colorIndex + 1) % len(COLORS)
        elif key == ord('s'):
            shapeIndex = (shapeIndex + 1) % len(SHAPES)
        elif key == ord('t'):
            thicknessIndex = (thicknessIndex + 1) % len(THICKNESSES)

# filepath="abc.pptx"
# main_func(filepath)
