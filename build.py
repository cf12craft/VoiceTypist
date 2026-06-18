import sys
import os
import shutil
import platform

def build():
    print("=== Voice Typist Compiler ===")
    print(f"Target OS: {platform.system()}")
    
    # Define compiler flags
    # main.py is the entry script
    # --onefile bundles everything into a single executable
    # --windowed/--noconsole hides the shell console window on launch
    # --name defines the output filename
    # --clean wipes build caches
    args = [
        'main.py',
        '--onefile',
        '--windowed',
        '--name=VoiceTypist',
        '--clean'
    ]

    # Add version info metadata on Windows to reduce antivirus false positives
    if platform.system() == "Windows":
        version_file = "file_version_info.txt"
        if os.path.exists(version_file):
            print(f"Adding Windows executable version info from {version_file}")
            args.append(f"--version-file={version_file}")

    # Locate speech_recognition package and bundle the correct flac binary
    try:
        import speech_recognition
        sr_dir = os.path.dirname(speech_recognition.__file__)
        flac_name = "flac-win32.exe" if platform.system() == "Windows" else "flac-linux-x86_64"
        flac_path = os.path.join(sr_dir, flac_name)
        if os.path.exists(flac_path):
            print(f"Bundling flac binary: {flac_path}")
            args.append(f"--add-binary={flac_path}{os.pathsep}speech_recognition")
        else:
            print(f"Warning: FLAC binary not found at {flac_path}")
    except Exception as e:
        print(f"Warning: Could not automatically detect and bundle flac binary: {str(e)}")

    try:
        import PyInstaller.__main__
        print("Invoking PyInstaller compiler...")
        PyInstaller.__main__.run(args)
        
        # Determine output executable name
        exe_name = "VoiceTypist.exe" if platform.system() == "Windows" else "VoiceTypist"
        dist_dir = os.path.join(os.getcwd(), "dist")
        exe_path = os.path.join(dist_dir, exe_name)
        
        print("\n=== Compile Report ===")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("Status: SUCCESS")
            print(f"Executable: {exe_path}")
            print(f"File Size: {size_mb:.2f} MB")
            print("Usage: You can now distribute this single file. No Python runtime is required.")
        else:
            print("Status: FAILED (Output binary not found in dist/)")
            sys.exit(1)
            
    except ImportError:
        print("Error: PyInstaller package is not installed. Please run: pip install pyinstaller")
        sys.exit(1)
    except Exception as e:
        print(f"Compilation encountered an error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    build()
