"""
Speaker verification: voice commands are only accepted when they are spoken by
the logged-in presenter.

Uses a pretrained ECAPA-TDNN speaker-embedding network (SpeechBrain, trained on
the VoxCeleb dataset of 7000+ speakers). The network turns any piece of speech
into a 192-number "voiceprint" vector; recordings of the same person give vectors
that point in a similar direction (high cosine similarity).

- Registration (enroll): the uploaded mp3 / wav is split into short windows, each
  window is embedded and the average is saved as the user's voiceprint
  (voices/user_<id>.npy).
- Presentation (SpeakerVerifier.verify): each phrase heard by the microphone is
  embedded and compared with the voiceprint. Below VERIFY_THRESHOLD = other speaker.

Requires: torch, torchaudio, speechbrain (model is downloaded once, ~80 MB).
mp3 / wav are read with soundfile; ffmpeg is only needed for other formats (m4a, ...).
"""

import os
import glob
import math
import shutil
import subprocess
import threading
import numpy as np

SAMPLE_RATE = 16000
MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_DIR = os.path.join("pretrained_models", "spkrec-ecapa-voxceleb")
VOICE_DIR = "voices"

# Cosine similarity needed to accept a command as the presenter's voice.
# Higher = stricter (fewer other people accepted, but the presenter is rejected more often).
# Similarity scores are printed to the console for every command, so this can be tuned.
VERIFY_THRESHOLD = 0.35

MIN_ENROLL_SECONDS = 5.0      # speech needed in the registration recording
ENROLL_WINDOW = 3.0           # the recording is embedded in windows of this length...
ENROLL_HOP = 1.5              # ...taken every this many seconds
MIN_COMMAND_SECONDS = 0.3     # shorter phrases cannot be checked reliably

_model = None
_model_lock = threading.Lock()


def get_model():
    """Load the speaker-embedding network once (first call takes a few seconds)."""
    global _model
    with _model_lock:
        if _model is None:
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy
            _model = EncoderClassifier.from_hparams(
                source=MODEL_SOURCE, savedir=MODEL_DIR, run_opts={"device": "cpu"},
                local_strategy=LocalStrategy.COPY)   # copy instead of symlink (Windows)
        return _model


def voiceprint_path(user_id):
    return os.path.join(VOICE_DIR, f"user_{user_id}.npy")


# -----------------------------
# Audio helpers
# -----------------------------
def find_ffmpeg():
    """Full path of ffmpeg.exe. The PATH of an already-running program (IDE, terminal)
    can be older than the system PATH, so also read the saved PATH and common folders."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    folders = []
    try:
        import winreg
        for root, key in [(winreg.HKEY_LOCAL_MACHINE,
                           r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, "Environment")]:
            with winreg.OpenKey(root, key) as k:
                folders += os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]).split(";")
    except OSError:
        pass
    folders += glob.glob(r"C:\ffmpeg*\bin") + glob.glob(r"C:\Program Files\ffmpeg*\bin")
    for folder in folders:
        exe = os.path.join(folder.strip(), "ffmpeg.exe")
        if folder.strip() and os.path.isfile(exe):
            return exe
    return None


def load_audio_file(path):
    """Decode an audio file to 16 kHz mono float32. wav / mp3 / flac / ogg are read
    directly with soundfile; other formats (m4a, ...) need ffmpeg."""
    try:
        import soundfile
        data, rate = soundfile.read(path, dtype="float32", always_2d=True)
        signal = data.mean(axis=1)
        if rate != SAMPLE_RATE:
            from scipy.signal import resample_poly
            g = math.gcd(SAMPLE_RATE, rate)
            signal = resample_poly(signal, SAMPLE_RATE // g, rate // g).astype(np.float32)
        return signal
    except Exception as e:
        print("soundfile could not read the audio, trying ffmpeg:", e)

    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise ValueError("Unsupported audio format. Please upload an mp3 or wav file.")
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-f", "s16le", "-"],
        capture_output=True, timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode != 0 or not result.stdout:
        raise ValueError("Could not read the audio file: " +
                         result.stderr.decode(errors="ignore").strip()[:200])
    return np.frombuffer(result.stdout, np.int16).astype(np.float32) / 32768.0


def audio_from_microphone(audio_data):
    """speech_recognition AudioData -> 16 kHz mono float32."""
    raw = audio_data.get_raw_data(convert_rate=SAMPLE_RATE, convert_width=2)
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def trim_silence(signal, frame_ms=30):
    """Keep only the frames that contain speech (simple energy-based detection),
    so silence and background noise do not dilute the voiceprint."""
    frame = SAMPLE_RATE * frame_ms // 1000
    n = len(signal) // frame
    if n == 0:
        return signal
    frames = signal[:n * frame].reshape(n, frame)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    loud = np.percentile(rms, 95)
    keep = rms > max(loud * 0.1, 1e-3)
    return frames[keep].reshape(-1)


def embed(signal):
    """Speech -> unit-length 192-d voiceprint vector."""
    import torch
    model = get_model()
    with torch.no_grad():
        emb = model.encode_batch(torch.from_numpy(np.ascontiguousarray(signal)).unsqueeze(0))
    emb = emb.squeeze().cpu().numpy().astype(np.float32)
    return emb / (np.linalg.norm(emb) + 1e-9)


# -----------------------------
# Registration
# -----------------------------
def create_voiceprint(audio_path):
    """Build the voiceprint from a registration recording. Returns (vector, seconds of speech).
    Raises ValueError when the recording is unusable."""
    speech = trim_silence(load_audio_file(audio_path))
    seconds = len(speech) / SAMPLE_RATE
    if seconds < MIN_ENROLL_SECONDS:
        raise ValueError(f"The voice recording has only {seconds:.1f} s of speech; "
                         f"please record at least {MIN_ENROLL_SECONDS:.0f} s (15-30 s is best).")

    win, hop = int(ENROLL_WINDOW * SAMPLE_RATE), int(ENROLL_HOP * SAMPLE_RATE)
    starts = range(0, max(1, len(speech) - win + 1), hop)
    vectors = [embed(speech[s:s + win]) for s in starts]
    voiceprint = np.mean(vectors, axis=0)
    return voiceprint / np.linalg.norm(voiceprint), seconds


def save_voiceprint(voiceprint, user_id):
    os.makedirs(VOICE_DIR, exist_ok=True)
    np.save(voiceprint_path(user_id), voiceprint)


# -----------------------------
# Presentation
# -----------------------------
class SpeakerVerifier:
    """Compares phrases heard by the microphone with one user's voiceprint."""

    def __init__(self, voiceprint_file, threshold=VERIFY_THRESHOLD):
        self.voiceprint = np.load(voiceprint_file)
        self.threshold = threshold
        get_model()     # load the network now rather than on the first command

    def verify(self, signal):
        """Returns (is_presenter, similarity score)."""
        speech = trim_silence(signal)
        if len(speech) < MIN_COMMAND_SECONDS * SAMPLE_RATE:
            return False, 0.0
        score = float(np.dot(embed(speech), self.voiceprint))
        return score >= self.threshold, score


def load_verifier(voiceprint_file):
    """SpeakerVerifier for a voiceprint file, or None when the user has no voiceprint
    (users registered before voice enrollment existed: any voice is accepted)."""
    if not voiceprint_file or not os.path.exists(voiceprint_file):
        return None
    return SpeakerVerifier(voiceprint_file)
