import sys
import platform
import subprocess
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from queue import Queue

# Detect sounddevice and query devices to test PortAudio DLL presence
HAS_SOUNDDEVICE = False
try:
    import sounddevice as sd
    sd.query_devices()
    HAS_SOUNDDEVICE = True
except Exception:
    HAS_SOUNDDEVICE = False


class AudioRecorder(QThread):
    # Signals
    amplitude_updated = pyqtSignal(float)      # Live volume (RMS) for visualizer (0.0 to 1.0)
    speech_started = pyqtSignal()             # Emitted when voice activity starts
    speech_chunk = pyqtSignal(bytes)           # Emitted with raw PCM bytes during voice activity
    speech_finalized = pyqtSignal()           # Emitted when the user pauses speaking
    status_msg = pyqtSignal(str)               # Status updates (e.g. backend used)
    error_occurred = pyqtSignal(str)           # Audio capture errors

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sample_rate = 16000
        self.channels = 1
        self.sample_width = 2  # 16-bit (2 bytes per sample)
        self.chunk_size = 800  # 800 samples = 0.05s at 16000Hz

        self.running = False
        self.is_speaking = False
        self.silence_timer = 0.0

        # VAD Parameters (user-adjustable via GUI)
        self.silence_threshold = 0.03  # RMS threshold
        self.silence_timeout = 1.0     # Time (s) of silence to trigger finalization

        self.backend = None

    def run(self):
        self.running = True
        self.is_speaking = False
        self.silence_timer = 0.0

        # Choose backend
        use_sounddevice = HAS_SOUNDDEVICE
        # Forced fallback test on Linux
        if platform.system() == "Linux" and not HAS_SOUNDDEVICE:
            use_sounddevice = False

        if use_sounddevice:
            self.status_msg.emit("Recording via: sounddevice (PortAudio)")
            self.backend = SoundDeviceBackend(self)
        else:
            if platform.system() == "Linux":
                self.status_msg.emit("Recording via: arecord (ALSA)")
                self.backend = ArecordBackend(self)
            else:
                self.error_occurred.emit("No audio backend available. On Linux, install 'alsa-utils'.")
                self.running = False
                return

        try:
            self.backend.start()
        except Exception as e:
            self.error_occurred.emit(f"Failed to start recording backend: {str(e)}")
            self.running = False
            return

        chunk_duration = self.chunk_size / self.sample_rate  # 0.05 seconds

        while self.running:
            raw_chunk = self.backend.read_chunk()
            if raw_chunk is None:
                if not self.running:
                    break
                QThread.msleep(10)
                continue

            # Convert bytes to numpy array to compute RMS
            pcm_data = np.frombuffer(raw_chunk, dtype=np.int16)
            if len(pcm_data) == 0:
                continue

            # Compute RMS amplitude normalized to [0.0, 1.0]
            samples = pcm_data.astype(np.float32) / 32768.0
            
            # Remove DC offset (zero-center the signal) to prevent silent hum/DC bias from keeping VAD active
            samples = samples - np.mean(samples)
            rms = np.sqrt(np.mean(samples ** 2))

            # Emit volume level to GUI visualizer
            self.amplitude_updated.emit(rms)

            # Voice Activity Detection (VAD) Logic
            if rms >= self.silence_threshold:
                if not self.is_speaking:
                    self.is_speaking = True
                    self.speech_started.emit()
                self.silence_timer = 0.0
                self.speech_chunk.emit(raw_chunk)
            else:
                if self.is_speaking:
                    self.silence_timer += chunk_duration
                    self.speech_chunk.emit(raw_chunk)  # Keep buffering short silences inside words
                    if self.silence_timer >= self.silence_timeout:
                        self.is_speaking = False
                        self.speech_finalized.emit()

        # Stop backend on exit
        try:
            self.backend.stop()
        except Exception:
            pass

    def stop(self):
        self.running = False
        # If we were in the middle of speaking, finalize on stop
        if self.is_speaking:
            self.is_speaking = False
            self.speech_finalized.emit()
        self.wait()


class SoundDeviceBackend:
    def __init__(self, recorder):
        self.recorder = recorder
        self.q = Queue()
        self.stream = None

    def callback(self, indata, frames, time_info, status):
        self.q.put(indata.copy().tobytes())

    def start(self):
        self.stream = sd.InputStream(
            samplerate=self.recorder.sample_rate,
            channels=self.recorder.channels,
            dtype='int16',
            blocksize=self.recorder.chunk_size,
            callback=self.callback
        )
        self.stream.start()

    def read_chunk(self):
        try:
            # Block briefly to wait for data, return None if timeout
            return self.q.get(timeout=0.1)
        except Exception:
            return None

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None


class ArecordBackend:
    def __init__(self, recorder):
        self.recorder = recorder
        self.process = None

    def start(self):
        cmd = [
            'arecord',
            '-q',
            '-D', 'default',
            '-f', 'S16_LE',
            '-c', str(self.recorder.channels),
            '-r', str(self.recorder.sample_rate),
            '-t', 'raw'
        ]
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

    def read_chunk(self):
        if not self.process or self.process.poll() is not None:
            return None
        
        # 16-bit mono = 2 bytes per sample
        bytes_to_read = self.recorder.chunk_size * 2
        try:
            data = self.process.stdout.read(bytes_to_read)
            if len(data) < bytes_to_read:
                return None
            return data
        except Exception:
            return None

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
