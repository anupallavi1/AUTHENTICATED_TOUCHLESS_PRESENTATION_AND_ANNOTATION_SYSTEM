import os
import cv2
import numpy as np
import time
import pyttsx3
import speech_recognition as sr
import threading
import queue

# Variables
from face_verification import face_verify
from ppt_splitter import ppt_to_images
from speaker_verification import load_verifier, audio_from_microphone

width = 1280
height = 720

# Voice command queue for thread-safe communication
voice_command_queue = queue.Queue()
stop_listening = False
voice_status = {"text": "Mic: starting..."}


def listen_for_commands(voiceprint=None):
    """Continuously listen for voice commands in a separate thread.
    With a voiceprint, only commands spoken by the presenter are passed on."""
    global stop_listening
    verifier = None
    if voiceprint:
        voice_status["text"] = "Loading voice model..."
        try:
            verifier = load_verifier(voiceprint)
        except Exception as e:
            # The presenter enrolled a voice but it cannot be checked: do not let anyone in
            print(f"Voice commands disabled (speaker verification error): {e}")
            voice_status["text"] = "Voice check failed - voice commands off"
            return
    if verifier is None:
        print("Speaker verification off (no voiceprint) - any voice is accepted")
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.5

    microphone = sr.Microphone()

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)

    voice_status["text"] = "Listening (presenter's voice only)" if verifier else "Listening (any voice)"
    while not stop_listening:
        try:
            with microphone as source:
                audio = recognizer.listen(source, timeout=2, phrase_time_limit=3)

            try:
                command = recognizer.recognize_google(audio).lower().strip()
                print(f"Voice command detected: '{command}'")
                if verifier is not None:
                    accepted, score = verifier.verify(audio_from_microphone(audio))
                    print(f"  speaker similarity {score:.2f} -> {'presenter' if accepted else 'OTHER SPEAKER, ignored'}")
                    if not accepted:
                        voice_status["text"] = 'Ignored, not the presenter: "' + command + '"'
                        continue
                voice_status["text"] = 'Heard: "' + command + '"'
                voice_command_queue.put(command)
            except sr.UnknownValueError:
                pass  # Could not understand audio
            except sr.RequestError as e:
                print(f"Speech recognition service error: {e}")
        except sr.WaitTimeoutError:
            pass  # No speech detected within timeout
        except Exception as e:
            print(f"Listening error: {e}")
            time.sleep(0.5)


def main_func2(ppt_path, voiceprint=None):
    global stop_listening

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

    # Variables
    imgNumber = 0
    ws, hs = 213, 120

    # Start voice listening thread
    stop_listening = False
    listener_thread = threading.Thread(target=listen_for_commands, args=(voiceprint,), daemon=True)
    listener_thread.start()

    # TTS engine for feedback
    engine = pyttsx3.init()
    engine.setProperty('rate', 180)

    print("Voice commands available: 'next', 'previous', 'close'")
    print("Listening for commands...")

    while True:
        # Import Images
        success, img = cap.read()
        if not success:
            break
        img = cv2.flip(img, 1)
        pathFullImage = os.path.join(folderPath, pathImages[imgNumber])
        imgCurrent = cv2.imread(pathFullImage)
        imgSlide = cv2.resize(imgCurrent, (w, h))

        # Process any pending voice commands
        try:
            while not voice_command_queue.empty():
                command = voice_command_queue.get_nowait()
                print("Comm  ", command)

                if "next slide" in command:
                    if imgNumber < len(pathImages) - 1:
                        imgNumber += 1
                        print(f"Next slide -> {imgNumber + 1}/{len(pathImages)}")
                    else:
                        print("Already at the last slide")

                elif "previous slide" in command or "back" in command:
                    if imgNumber > 0:
                        imgNumber -= 1
                        print(f"Previous slide -> {imgNumber + 1}/{len(pathImages)}")
                    else:
                        print("Already at the first slide")

                elif "close" in command or "exit" in command or "quit" in command:
                    print("Closing presentation...")
                    stop_listening = True
                    cap.release()
                    cv2.destroyAllWindows()
                    return "ok"
        except queue.Empty:
            pass

        # Display slide number overlay
        cv2.putText(imgSlide, f"Slide {imgNumber + 1}/{len(pathImages)}",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Voice status (listening / last command / ignored speaker)
        cv2.putText(imgSlide, voice_status["text"][:60], (20, h - 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Display voice command hints
        cv2.putText(imgSlide, "Commands: 'next slide' | 'previous slide' | 'close'",
                    (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # Adding a webcam image on the slides
        imgSmall = cv2.resize(img, (ws, hs))
        imgSlide[0:hs, w - ws:w] = imgSmall

        cv2.imshow("Slides", imgSlide)

        key = cv2.waitKey(1)
        if key == ord('q'):
            stop_listening = True
            cap.release()
            cv2.destroyAllWindows()
            return "ok"


            # filepath = "abc.pptx"
            # main_func(filepath)