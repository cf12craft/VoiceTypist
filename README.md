# Voice Typist

Voice Typist is a high-performance, cross-platform, real-time speech-to-text dictation application designed for Windows and Linux (X11 only). Built with PyQt6 and Python, it features a premium dark-themed interface, a custom 60 FPS animated audio visualizer, a draggable focus-free floating overlay, and global auto-paste (Direct Dictation) capabilities that let you type with your voice into any application.

## Key Features

- **Real-Time Speech-to-Text**: High-accuracy, low-latency transcription using Google Speech Recognition API with non-blocking worker threads.
- **Smart Punctuation & Formatting**: Translates spoken punctuation (like "comma", "question mark", "exclamation point", "colon", "semicolon", "new line", "new paragraph") into symbols and formatting. Features positional intelligence for "period" and "full stop" (converting them to "." only at the end of a sentence, keeping the literal noun word in between phrases). Automatically capitalizes the very first letter of a transcription segment and the first word after sentence-ending punctuation.
- **Auto Punctuation (Phrasing Detection)**: Automatically infers and inserts periods or question marks based on sentence structure and phrasing (e.g. Wh-questions or auxiliary verb starters) when you stop speaking, without needing explicit punctuation commands.
- **Audio File Transcription**: Supports uploading and transcribing audio files (MP3, WAV, M4A, AAC, FLAC, OGG, CAF, etc.) directly into the editor.
- **Direct Dictation**: Automatically inserts finalized transcriptions into the active editor or input field (e.g., Notepad, VS Code, web browsers) by simulating copy-paste shortcuts (using native Windows APIs via ctypes and Linux Xlib).
- **Focus-Free Floating Overlay**: A compact, draggable pill widget that stays on top of other windows but does not steal focus, keeping your cursor active in the target editor.
- **Custom Audio Visualizer**: A 60 FPS animated waveform widget that renders voice amplitude changes using smooth mathematical sine waves.
- **Dual-Backend Audio Recorder**: Spawns a dedicated thread that processes audio levels and voice activity:
  - **Windows (Primary)**: Captures audio natively using the Sounddevice library.
  - **Linux (Fallback)**: Streams audio from the ALSA arecord CLI if PortAudio system headers are missing.
- **No Heavy/Unsafe Dependencies**: Bypasses heavy automated libraries (like PyAutoGUI or MouseInfo), resulting in clean imports and no Tkinter/system package warnings.

## Download

Pre-compiled, standalone executables for Windows and Linux are available for download on the [Latest Releases](https://github.com/cf12craft/VoiceTypist/releases/latest) page. You can run these binaries directly on your machine without installing Python or any dependencies.

## Getting Started

### Option A: Standalone Executables (No Installation Required)

Pre-compiled, standalone binaries are available for both Windows and Linux:
- **Windows**: Copy `dist/VoiceTypist.exe` to your Windows machine and run it directly.
- **Linux**: Run `dist/VoiceTypist` directly from your terminal.

These binaries are fully self-contained and do not require Python or any external packages to be installed.

### Option B: Running from Source

To run the application from source, you need Python 3.10+ installed.

1. Clone the repository and navigate to the project root:
   ```bash
   git clone https://github.com/cf12craft/VoiceTypist.git
   cd VoiceTypist
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
   ```

3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

To run a fast dependency diagnostics check and exit:
```bash
python main.py --dry-run
```

## Compilation

The application can be compiled into a standalone executable using PyInstaller.

1. Install PyInstaller in your environment:
   ```bash
   pip install pyinstaller
   ```

2. Run the build script:
   ```bash
   python build.py
   ```

The script will automatically detect your OS, compile the entry point, bundle all assets and dependencies (including required PyQt6 ICU DLLs on Windows), and output the final binary to the `dist/` directory.

## Troubleshooting

### Voice Activity Detection (VAD) Tuning

If the application does not stop transcribing and send your text when you stop speaking, or if it triggers too easily on background noise:
1. **Remove DC Offset**: The engine automatically centers the microphone signal to eliminate static hum or hardware-level DC bias.
2. **Adjust VAD Threshold**: 
   - Move the **Mic Sensitivity (VAD Threshold)** slider to the right (higher value, e.g. 50-100) if the app keeps recording continuously in a noisy room or because of microphone static.
   - Move the slider to the left (lower value, e.g. 10-20) if the app does not detect your voice at all.
3. **Adjust Commit Delay**: Set the **Auto-Commit Silence Delay** slider to a lower value (e.g. 0.5s - 1.0s) to reduce the pause time needed for the app to finalize and type your sentence.

## License

This project is licensed under the MIT License.
