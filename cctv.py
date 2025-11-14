import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox
import webbrowser
import threading
import uuid
from datetime import datetime
import re

# ========== Helper Functions ==========

def generate_mount_name():
    """Generate a short unique mount name (no extension)."""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short = uuid.uuid4().hex[:6]
    name = f"stream_{ts}_{short}"
    # sanitize to allow only alnum and underscore
    name = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    return name


def check_ffmpeg():
    """Ensure bundled ffmpeg.exe exists (no system fallback).

    When PyInstaller bundles the exe, assets added with --add-data are
    extracted to sys._MEIPASS. During development (not frozen) the
    script will look for an `ffmpeg/ffmpeg.exe` relative to the script
    directory so you can test locally on Windows.
    """
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    ffmpeg_path = os.path.join(base_dir, "ffmpeg", "ffmpeg.exe")

    if not os.path.exists(ffmpeg_path):
        messagebox.showerror("Error", f"Bundled FFmpeg not found!\nExpected at:\n{ffmpeg_path}")
        sys.exit(1)

    print(f"Using bundled FFmpeg: {ffmpeg_path}")
    return ffmpeg_path


def detect_rtsp_url(ffmpeg_path, user, password, ip):
    """Try common RTSP paths until one works. Returns valid rtsp://... or None."""
    common_paths = [
        "/Streaming/Channels/101",
        "/Streaming/Channels/102",
        "/cam/realmonitor?channel=1&subtype=0",
        "/cam/realmonitor?channel=1&subtype=1",
        "/live/main",
        "/live/sub",
        "/axis-media/media.amp",
        "/h264Preview_01_main",
        "/h264Preview_01_sub",
        "/stream1",
        "/live.sdp",
        "/media/video1",
        "/videoMain",
        "/videoSub",
        "/rtsp_tunnel",
        "/defaultPrimary",
        "/MediaInput/h264",
        "/profile1/media.smp",
        "/channel1",
        "/live/ch00_0",
    ]

    for path in common_paths:
        rtsp_url = f"rtsp://{user}:{password}@{ip}:554{path}"
        print(f"Testing {rtsp_url} ...")

        cmd = [ffmpeg_path, "-rtsp_transport", "tcp", "-i", rtsp_url, "-t", "3", "-f", "null", "-"]

        # When developers test on Linux with wine, they often run the bundled ffmpeg.exe via wine
        if sys.platform.startswith("linux") and ffmpeg_path.endswith('.exe'):
            cmd.insert(0, "wine")

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
            stderr = result.stderr.lower()
            # look for common ffmpeg signs of a valid stream
            if b"stream #0" in result.stderr.lower() or b"video" in result.stderr.lower() or b"realrtsp" in result.stderr.lower():
                print(f"Valid RTSP URL found: {rtsp_url}")
                return rtsp_url
            # Some cameras report different messages but we can check exit code
            if result.returncode == 0:
                print(f"FFmpeg exited 0 for {rtsp_url}; assuming OK")
                return rtsp_url
        except subprocess.TimeoutExpired:
            print(f"Timeout on {path}")
        except Exception as e:
            print(f"Error testing {path}: {e}")

    messagebox.showerror("RTSP Error", "No valid RTSP URL found!\nPlease verify camera IP or credentials.")
    return None


def run_ffmpeg(ffmpeg_path, rtsp_url, stream_name):
    """Start streaming using local ffmpeg. stream_name must be URL-safe (no leading slash)."""
    # ensure no leading slash and remove extension if user provided one
    stream_name = os.path.basename(stream_name)
    stream_name = os.path.splitext(stream_name)[0]

    icecast_url = f"icecast://source:hackme@portal.thabir.ai:80/{stream_name}"
    viewer_url = f"http://portal.thabir.ai/{stream_name}"

    cmd = [
        ffmpeg_path,
        "-rtsp_transport", "tcp",
        "-thread_queue_size", "512",
        "-i", rtsp_url,
        "-c:v", "libvpx",
        "-deadline", "realtime",
        "-cpu-used", "5",
        "-g", "1",
        "-b:v", "1000k",
        "-ar", "44100",
        "-ac", "1",
        "-c:a", "libvorbis",
        "-b:a", "128k",
        "-content_type", "video/webm",
        "-f", "webm",
        icecast_url
    ]

    if sys.platform.startswith("linux") and ffmpeg_path.endswith('.exe'):
        cmd.insert(0, "wine")

    print("Starting FFmpeg stream...\n", " ".join(cmd))
    try:
        subprocess.Popen(cmd)
        webbrowser.open(viewer_url)
        messagebox.showinfo("Stream Started", f"Your stream is live!\n\n{viewer_url}")
        url_var.set(viewer_url)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start FFmpeg:\n{e}")


# ========== GUI ==========

def start_stream():
    ip = ip_entry.get().strip()
    user = username_entry.get().strip()
    password = password_entry.get().strip()
    stream_name = mount_entry.get().strip()

    if not all([ip, user, password]):
        messagebox.showwarning("Missing Info", "Please fill Camera IP, Username and Password.")
        return

    # If user left mount blank, generate a unique one automatically
    if not stream_name:
        stream_name = generate_mount_name()
        mount_entry.delete(0, tk.END)
        mount_entry.insert(0, stream_name)

    ffmpeg_path = check_ffmpeg()

    def task():
        rtsp_url = detect_rtsp_url(ffmpeg_path, user, password, ip)
        if rtsp_url:
            run_ffmpeg(ffmpeg_path, rtsp_url, stream_name)

    threading.Thread(target=task, daemon=True).start()


def copy_url():
    url = url_var.get()
    if not url:
        messagebox.showwarning("No URL", "No stream URL to copy yet.")
        return

    root.clipboard_clear()
    root.clipboard_append(url)
    root.update()
    messagebox.showinfo("Copied", "Stream URL copied to clipboard!")


# ========== GUI Setup ==========

root = tk.Tk()
root.title("CCTV Streamer")
root.geometry("460x420")
root.configure(bg="#0f0f0f")  # black background

font_title = ("Arial", 14, "bold")
font_label = ("Arial", 10)

tk.Label(root, text="CCTV Live Streamer", fg="#e8e0f5", bg="#0f0f0f", font=font_title).pack(pady=10)

tk.Label(root, text="Camera IP:", fg="white", bg="#0f0f0f", font=font_label).pack(pady=4)
ip_entry = tk.Entry(root, width=40)
ip_entry.pack()

tk.Label(root, text="Username:", fg="white", bg="#0f0f0f", font=font_label).pack(pady=4)
username_entry = tk.Entry(root, width=40)
username_entry.pack()

tk.Label(root, text="Password:", fg="white", bg="#0f0f0f", font=font_label).pack(pady=4)
password_entry = tk.Entry(root, width=40, show="*")
password_entry.pack()

tk.Label(root, text="Mount Name (leave empty to auto-generate):", fg="white", bg="#0f0f0f", font=font_label).pack(pady=4)
mount_entry = tk.Entry(root, width=40)
mount_entry.pack()

tk.Button(root, text="Start Stream", command=start_stream, bg="#e3d2ff", fg="grey", width=20, height=2).pack(pady=15)

url_var = tk.StringVar()
tk.Entry(root, textvariable=url_var, width=50, state="readonly", justify="center").pack(pady=5)
tk.Button(root, text="Copy URL", command=copy_url, bg="#e3d2ff", fg="grey").pack(pady=5)

root.mainloop()
