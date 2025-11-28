import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import time
from pathlib import Path
import sys
import datetime

# ============================================================
# CORRECT PATH — main.py lives in Exportify/src/
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


# ============================================================
# Helpers
# ============================================================

def timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S")

def is_progress_line(s: str):
    return ("\r" in s) or ("[" in s and "]" in s and "/" in s)


class ConsoleWriter:
    def __init__(self, widget):
        self.widget = widget
        self.last_was_progress = False

    def write(self, msg):
        self.widget.configure(state="normal")

        if is_progress_line(msg):
            clean = msg.replace("\r", "").rstrip()

            if self.last_was_progress:
                # delete previous progress line
                self.widget.delete("end-2l", "end-1l")

            self.widget.insert("end", clean + "\n")
            self.widget.see("end")
            self.last_was_progress = True

        else:
            self.widget.insert("end", f"[{timestamp()}] {msg}")
            self.widget.see("end")
            self.last_was_progress = False

        self.widget.configure(state="disabled")

    def flush(self):
        pass


# ============================================================
# Run scripts in background thread
# ============================================================

def run_script(script_name, console_obj):
    script_path = BASE_DIR / script_name

    def task():
        console_obj.write(f"\n=== Running {script_name} ===\n")

        process = subprocess.Popen(
            [PYTHON, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=str(BASE_DIR)
        )

        for line in process.stdout:
            console_obj.write(line)

        process.wait()
        console_obj.write(f"=== Finished {script_name} ===\n\n")

    threading.Thread(target=task, daemon=True).start()


# ============================================================
# UI Setup (Default Tkinter Colors)
# ============================================================

root = tk.Tk()
root.title("Exportify Control Panel")
root.geometry("900x650")

frame = ttk.Frame(root)
frame.pack(padx=20, pady=20, fill="x")


# ============================================================
# Button Commands
# ============================================================

def run_pull():
    run_script("data_pull.py", console)

def run_build_library():
    run_script("build_complete_library_playlist.py", console)

def run_csv_to_tracks():
    run_script("csv_to_tracks.py", console)

def run_analysis():
    run_script("analysis.py", console)

def run_recommend():
    run_script("liked_songs_recommend.py", console)


# ============================================================
# Buttons
# ============================================================

ttk.Label(frame, text="Exportify Tasks", font=("Segoe UI", 16, "bold")).pack(pady=10)

btn_frame = ttk.Frame(frame)
btn_frame.pack(fill="x")

ttk.Button(btn_frame, text="1. Pull Spotify Data", command=run_pull)\
    .grid(row=0, column=0, padx=5, pady=5, sticky="ew")

ttk.Button(btn_frame, text="2. Build Complete Library", command=run_build_library)\
    .grid(row=0, column=1, padx=5, pady=5, sticky="ew")

ttk.Button(btn_frame, text="3. Convert CSV → Tracks", command=run_csv_to_tracks)\
    .grid(row=1, column=0, padx=5, pady=5, sticky="ew")

ttk.Button(btn_frame, text="4. Run Analysis", command=run_analysis)\
    .grid(row=1, column=1, padx=5, pady=5, sticky="ew")

ttk.Button(btn_frame, text="5. Recommend Liked Songs", command=run_recommend)\
    .grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

btn_frame.grid_columnconfigure(0, weight=1)
btn_frame.grid_columnconfigure(1, weight=1)


# ============================================================
# Console Output Box (Light Mode)
# ============================================================

ttk.Label(root, text="Console Output:", font=("Segoe UI", 12, "bold"))\
    .pack(anchor="w", padx=20)

console_widget = scrolledtext.ScrolledText(
    root, wrap="word", font=("Consolas", 10),
    width=90, height=20
)
console_widget.pack(fill="both", expand=True, padx=20, pady=10)
console_widget.configure(state="disabled")

console = ConsoleWriter(console_widget)
console.write("Exportify Control Panel Ready.\n")

root.mainloop()
