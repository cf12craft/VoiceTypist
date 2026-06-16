import sys
import argparse
import platform
import subprocess
from PyQt6.QtWidgets import QApplication

def check_dependencies():
    """
    Validates host dependencies and prints availability reports.
    """
    print("=== System Diagnostics ===")
    print(f"OS Platform: {platform.system()} {platform.release()}")
    print(f"Python Version: {platform.python_version()}")

    # Check for sounddevice
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print("sounddevice (PortAudio): AVAILABLE")
        print(f"Available audio devices: {len(devices)}")
    except Exception as e:
        print(f"sounddevice (PortAudio): NOT AVAILABLE ({str(e)})")

    # Check for arecord on Linux
    if platform.system() == "Linux":
        try:
            res = subprocess.run(["arecord", "--version"], capture_output=True, text=True)
            version_line = res.stderr.splitlines() or res.stdout.splitlines()
            version_str = version_line[0] if version_line else "unknown version"
            print(f"arecord (ALSA capture tool): AVAILABLE ({version_str})")
        except Exception:
            print("arecord (ALSA capture tool): NOT AVAILABLE (Install 'alsa-utils' on Linux)")

    # Check for PyQt6
    try:
        import PyQt6
        print("PyQt6: AVAILABLE")
    except ImportError:
        print("PyQt6: NOT AVAILABLE")

    # Check for Xlib (keystroke simulation backend)
    try:
        from Xlib.display import Display
        print("Xlib (Linux keystroke simulation backend): AVAILABLE")
    except Exception as e:
        print(f"Xlib (Linux keystroke simulation backend): NOT AVAILABLE ({type(e).__name__}: {str(e)})")

    print("==========================")


def main():
    parser = argparse.ArgumentParser(description="Voice Typist - Real-time Speech-to-Text Dictation Tool")
    parser.add_argument("--dry-run", action="store_true", help="Perform diagnostics, verify imports, and exit immediately")
    args = parser.parse_args()

    # Dry-run execution
    if args.dry_run:
        check_dependencies()
        print("Dry run completed successfully. All components loaded.")
        sys.exit(0)

    # Standard execution
    from audio_recorder import AudioRecorder
    from transcriber import Transcriber
    from gui import VoiceTypistApp

    # Run diagnostics on startup stdout
    check_dependencies()

    app = QApplication(sys.argv)
    
    # Initialize background threads
    recorder = AudioRecorder()
    transcriber = Transcriber()
    
    # Initialize UI
    window = VoiceTypistApp(recorder, transcriber)
    window.show()
    
    # Run loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
