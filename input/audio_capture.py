# ============================================================
# ProctorAI — input/audio_capture.py
# Captures microphone audio using sounddevice (or PyAudio fallback).
# Runs in a background thread; main thread reads .audio_level
# ============================================================

import threading
import numpy as np
from utils.helpers import get_logger
from config.settings import (
    AUDIO_SAMPLE_RATE, AUDIO_CHUNK_SIZE,
    AUDIO_CHANNELS, AUDIO_DEVICE_INDEX
)

logger = get_logger("AudioCapture")


class AudioCapture:
    """
    Opens the microphone and continuously reads audio chunks.
    Exposes the current RMS amplitude via the audio_level property.

    Tries sounddevice first (works on Python 3.14+), falls back to PyAudio.

    Usage:
        mic = AudioCapture()
        mic.start_microphone()
        level = mic.audio_level   # float, 0.0 to ~0.1+
        mic.stop_microphone()
    """

    def __init__(self):
        self._stream      = None
        self._running     = threading.Event()
        self._level       = 0.0
        self._lock        = threading.Lock()
        self._available   = False
        self._backend     = None    # "sounddevice" or "pyaudio"

        # Try sounddevice first (pure Python + cffi, works on Python 3.14)
        try:
            import sounddevice as sd
            self._sd = sd
            self._backend = "sounddevice"
            self._available = True
            logger.info("AudioCapture using sounddevice backend")
        except ImportError:
            pass

        # Fall back to PyAudio
        if not self._available:
            try:
                import pyaudio
                self._pyaudio = pyaudio
                self._backend = "pyaudio"
                self._available = True
                logger.info("AudioCapture using PyAudio backend")
            except ImportError:
                logger.warning(
                    "No audio backend available — microphone monitoring disabled.\n"
                    "  Install: pip install sounddevice   (recommended)\n"
                    "  Or:      pip install pyaudio"
                )

    def start_microphone(self) -> bool:
        """
        Open microphone stream and start background capture.
        Returns True if started, False if no audio backend is available.
        """
        if not self._available:
            return False

        if self._backend == "sounddevice":
            return self._start_sounddevice()
        else:
            return self._start_pyaudio()

    # ── sounddevice backend ────────────────────────────────────
    def _start_sounddevice(self) -> bool:
        try:
            device = AUDIO_DEVICE_INDEX
            self._running.set()
            self._stream = self._sd.InputStream(
                samplerate=AUDIO_SAMPLE_RATE,
                channels=AUDIO_CHANNELS,
                dtype="float32",
                blocksize=AUDIO_CHUNK_SIZE,
                device=device,
                callback=self._sd_callback,
            )
            self._stream.start()
            logger.info(f"Microphone started (sounddevice) at {AUDIO_SAMPLE_RATE}Hz")
            return True
        except Exception as e:
            logger.error(f"Failed to open microphone (sounddevice): {e}")
            return False

    def _sd_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            logger.debug(f"Audio stream status: {status}")
        rms = float(np.sqrt(np.mean(indata ** 2)))
        with self._lock:
            self._level = rms

    # ── PyAudio backend ─────────────────────────────────────────
    def _start_pyaudio(self) -> bool:
        try:
            self._pa = self._pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=self._pyaudio.paFloat32,
                channels=AUDIO_CHANNELS,
                rate=AUDIO_SAMPLE_RATE,
                input=True,
                input_device_index=AUDIO_DEVICE_INDEX,
                frames_per_buffer=AUDIO_CHUNK_SIZE,
            )
            self._running.set()
            self._thread = threading.Thread(
                target=self._pyaudio_capture_loop,
                daemon=True,
                name="AudioCaptureThread"
            )
            self._thread.start()
            logger.info(f"Microphone started (PyAudio) at {AUDIO_SAMPLE_RATE}Hz")
            return True
        except Exception as e:
            logger.error(f"Failed to open microphone (PyAudio): {e}")
            return False

    def _pyaudio_capture_loop(self):
        """Background thread for PyAudio: continuously reads audio chunks."""
        while self._running.is_set():
            try:
                raw = self._stream.read(
                    AUDIO_CHUNK_SIZE, exception_on_overflow=False
                )
                samples = np.frombuffer(raw, dtype=np.float32)
                rms = float(np.sqrt(np.mean(samples ** 2)))
                with self._lock:
                    self._level = rms
            except Exception as e:
                logger.debug(f"Audio read error: {e}")

    # ── Common methods ──────────────────────────────────────────
    def stop_microphone(self):
        """Stop microphone capture and release resources."""
        self._running.clear()
        if self._stream:
            try:
                if self._backend == "sounddevice":
                    self._stream.stop()
                    self._stream.close()
                else:
                    self._stream.stop_stream()
                    self._stream.close()
            except Exception:
                pass
        if self._backend == "pyaudio" and hasattr(self, "_pa") and self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
        logger.info("Microphone stopped.")

    @property
    def audio_level(self) -> float:
        """Current RMS amplitude of the microphone (thread-safe)."""
        with self._lock:
            return self._level

    @property
    def is_available(self) -> bool:
        return self._available
