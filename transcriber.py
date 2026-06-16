import io
import wave
import time
import speech_recognition as sr
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker


def pcm_to_wav(pcm_bytes, sample_rate=16000, channels=1, sample_width=2):
    """
    Converts raw PCM bytes to WAV format in memory.
    """
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)
    wav_io.seek(0)
    return wav_io


class Transcriber(QThread):
    # Signals
    # text, is_final
    transcription_chunk = pyqtSignal(str, bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recognizer = sr.Recognizer()
        
        # Configure recognizer thresholds for better responsiveness
        self.recognizer.dynamic_energy_threshold = False
        
        self.language = "en-US"
        self.running = False
        
        # Thread safety mutex
        self.mutex = QMutex()
        self.audio_buffer = bytearray()
        self.new_data_available = False
        self.finalize_requested = False
        self.is_transcribing = False

    def add_chunk(self, chunk):
        """
        Appends new raw PCM bytes to the active sentence buffer.
        """
        with QMutexLocker(self.mutex):
            self.audio_buffer.extend(chunk)
            self.new_data_available = True

    def request_finalize(self):
        """
        Requests to immediately transcribe the remaining buffer and finalize the sentence.
        """
        with QMutexLocker(self.mutex):
            self.finalize_requested = True
            self.new_data_available = True

    def reset_buffer(self):
        """
        Clears the active sentence buffer.
        """
        with QMutexLocker(self.mutex):
            self.audio_buffer.clear()
            self.new_data_available = False
            self.finalize_requested = False

    def run(self):
        self.running = True
        last_transcribe_time = 0.0

        while self.running:
            should_transcribe = False
            is_final = False
            pcm_snapshot = b""
            
            with QMutexLocker(self.mutex):
                now = time.time()
                time_elapsed = now - last_transcribe_time
                
                if len(self.audio_buffer) > 0:
                    if self.finalize_requested:
                        # User paused or stopped; finalize the text
                        should_transcribe = True
                        is_final = True
                        pcm_snapshot = bytes(self.audio_buffer)
                        self.audio_buffer.clear()
                        self.finalize_requested = False
                        self.new_data_available = False
                    elif self.new_data_available and time_elapsed >= 0.7:
                        # Live typing updates (interim transcription)
                        should_transcribe = True
                        is_final = False
                        pcm_snapshot = bytes(self.audio_buffer)
                        self.new_data_available = False
            
            if should_transcribe and len(pcm_snapshot) > 0:
                last_transcribe_time = time.time()
                self.is_transcribing = True
                
                # Non-blocking transcription call
                text = self._transcribe(pcm_snapshot)
                
                if text is not None:
                    # Emit result (text can be empty if not recognized, which is fine)
                    self.transcription_chunk.emit(text, is_final)
                
                self.is_transcribing = False

            # Prevent busy-waiting
            QThread.msleep(50)

    def _transcribe(self, pcm_data):
        wav_io = pcm_to_wav(pcm_data)
        try:
            with sr.AudioFile(wav_io) as source:
                audio = self.recognizer.record(source)
            
            # Using Google's free speech recognition endpoint
            text = self.recognizer.recognize_google(audio, language=self.language)
            return text
        except sr.UnknownValueError:
            # Speech was not intelligible, return empty string
            return ""
        except sr.RequestError as e:
            self.error_occurred.emit(f"Connection Error: {str(e)}")
            return None
        except Exception as e:
            self.error_occurred.emit(f"Transcription Error: {str(e)}")
            return None

    def stop(self):
        self.running = False
        self.wait()
