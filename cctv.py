import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog

# -------------------------
# Resolve runtime base path
# -------------------------
def resource_path(relative_path):
    """Get absolute path to resource inside onefile EXE."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# -------------------------
# FFmpeg Path Detection
# -------------------------
def get_ffmpeg_paths():
    base = resource_path("ffmpeg")

    ffmpeg = os.path.join(base, "ffmpeg.exe")
    ffprobe = os.path.join(base, "ffprobe.exe")

    if not os.path.isfile(ffmpeg):
        messagebox.showerror("Error", "Missing ffmpeg.exe inside bundled EXE!")
        sys.exit(1)

    return ffmpeg, ffprobe


# -------------------------
# Validate RTSP Stream
# -------------------------
def validate_rtsp(ffprobe, url):
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-rtsp_transport", "tcp", "-i", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


# -------------------------
# Start FFmpeg Streaming
# -------------------------
def start_stream(ffmpeg, url):
    output_url = "rtmp://live.example.com/live/stream"  # CHANGE THIS TO YOUR OUTPUT

    cmd = [
        ffmpeg,
        "-rtsp_transport", "tcp",
        "-i", url,
        "-c:v", "copy",
        "-c:a", "aac",
        output_url
    ]

    try:
        subprocess.Popen(cmd)
        messagebox.showinfo("Success", "Stream started successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start streaming:\n{e}")


# -------------------------
# GUI Code
# -------------------------
def main_gui():
    root = tk.Tk()
    root.withdraw()  # hide root window

    ffmpeg, ffprobe = get_ffmpeg_paths()

    ip = simpledialog.askstring("Camera IP", "Enter Camera IP:")
    username = simpledialog.askstring("Username", "Enter Camera Username:")
    password = simpledialog.askstring("Password", "Enter Camera Password:")

    if not ip or not username or not password:
        messagebox.showerror("Error", "All fields are required!")
        return

    rtsp_url = f"rtsp://{username}:{password}@{ip}/"

    # validate
    if not validate_rtsp(ffprobe, rtsp_url):
        messagebox.showerror("Invalid RTSP", "RTSP URL is incorrect or camera unreachable.")
        return

    start_stream(ffmpeg, rtsp_url)


if __name__ == "__main__":
    main_gui()
