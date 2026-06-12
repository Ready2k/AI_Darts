#!/usr/bin/env python3
"""
Darts launcher — CustomTkinter Modern GUI.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import customtkinter as ctk

SCRIPT_DIR = Path(__file__).parent

# Set appearance and theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DartTrack AI")
        self.geometry("1100x700")
        
        # Grid layout 1x2 (Sidebar, Main Content)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # -- Colors --
        self.bg_color = "#181A1B"
        self.sidebar_color = "#202325"
        self.accent_cyan = "#00E5FF"
        self.accent_green = "#00E676"
        
        self.configure(fg_color=self.bg_color)

        # -- Sidebar --
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=self.sidebar_color)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="DartTrack AI", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.accent_cyan)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        # Navigation Buttons
        self.btn_dashboard = self.create_nav_button("Dashboard", 1, self.show_dashboard)
        self.btn_calibration = self.create_nav_button("Calibration", 2, self.show_calibration)
        self.btn_livetrack = self.create_nav_button("Live Track", 3, self.show_livetrack)
        self.btn_analytics = self.create_nav_button("Analytics", 4, self.show_analytics)
        self.btn_setup = self.create_nav_button("Setup", 5, self.show_setup)
        self.btn_profile = self.create_nav_button("Profile", 6, self.show_profile)

        # -- Main Content Area --
        self.main_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self.main_frame, height=60, corner_radius=10, fg_color=self.sidebar_color)
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.header_label = ctk.CTkLabel(self.header_frame, text="DARTTRACK DASHBOARD", font=ctk.CTkFont(size=18, weight="bold"))
        self.header_label.pack(side="left", padx=20, pady=15)
        
        self.btn_start_match = ctk.CTkButton(
            self.header_frame, text="START MATCH", fg_color=self.accent_cyan, text_color="black", 
            font=ctk.CTkFont(weight="bold"), hover_color=self.accent_green, command=self.launch_detect
        )
        self.btn_start_match.pack(side="right", padx=20, pady=15)

        # Frames Dictionary
        self.frames = {}
        
        self.setup_dashboard_frame()
        self.setup_calibration_frame()
        self.setup_livetrack_frame()
        self.setup_analytics_frame()
        self.setup_setup_frame()
        self.setup_profile_frame()

        # Start on Dashboard
        self.show_dashboard()

    def create_nav_button(self, text, row, command):
        btn = ctk.CTkButton(
            self.sidebar_frame, corner_radius=5, height=40, border_spacing=10, text=text,
            fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
            anchor="w", command=command, font=ctk.CTkFont(size=15)
        )
        btn.grid(row=row, column=0, sticky="ew", padx=10, pady=5)
        return btn

    def select_button(self, active_btn):
        # Reset all buttons
        buttons = [self.btn_dashboard, self.btn_calibration, self.btn_livetrack, self.btn_analytics, self.btn_setup, self.btn_profile]
        for btn in buttons:
            btn.configure(fg_color="transparent")
        # Highlight active
        active_btn.configure(fg_color=self.accent_cyan, text_color="black", hover_color=self.accent_green)

    def hide_all_frames(self):
        for frame in self.frames.values():
            frame.grid_forget()

    def show_frame(self, name, title):
        self.hide_all_frames()
        self.frames[name].grid(row=1, column=0, sticky="nsew")
        self.header_label.configure(text=title.upper())

    def show_dashboard(self):
        self.select_button(self.btn_dashboard)
        self.show_frame("dashboard", "DartTrack Dashboard")
        self.update_status()

    def show_calibration(self):
        self.select_button(self.btn_calibration)
        self.show_frame("calibration", "System Calibration & Alignment")

    def show_livetrack(self):
        self.select_button(self.btn_livetrack)
        self.show_frame("livetrack", "Live Match Tracking")

    def show_analytics(self):
        self.select_button(self.btn_analytics)
        self.show_frame("analytics", "Analytics Overview")
        
    def show_setup(self):
        self.select_button(self.btn_setup)
        self.show_frame("setup", "System Configuration")

    def show_profile(self):
        self.select_button(self.btn_profile)
        self.show_frame("profile", "User Profile")

    # --- View Setup Methods ---
    def setup_dashboard_frame(self):
        frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.frames["dashboard"] = frame
        
        status_card = ctk.CTkFrame(frame, corner_radius=10, fg_color=self.sidebar_color)
        status_card.pack(fill="x", pady=10)
        
        self.lbl_status = ctk.CTkLabel(status_card, text="Checking status...", font=ctk.CTkFont(size=16))
        self.lbl_status.pack(pady=20, padx=20)
        
        welcome_lbl = ctk.CTkLabel(
            frame, 
            text="Welcome to DartTrack AI.\nSelect an option from the sidebar to begin.\n\nTo play a game, click START MATCH in the top right.", 
            font=ctk.CTkFont(size=14), text_color="gray"
        )
        welcome_lbl.pack(pady=40)

    def setup_calibration_frame(self):
        frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.frames["calibration"] = frame
        
        info = ctk.CTkLabel(frame, text="Align the camera feeds with the dartboard grid.", font=ctk.CTkFont(size=16))
        info.pack(pady=20)
        
        btn_align = ctk.CTkButton(
            frame, text="ALIGN CAMERAS", fg_color=self.accent_cyan, text_color="black", 
            font=ctk.CTkFont(weight="bold", size=18), height=50, command=self.launch_align
        )
        btn_align.pack(pady=20)
        
        btn_check = ctk.CTkButton(
            frame, text="CHECK CAMERAS (Live Feed)", fg_color=self.sidebar_color, border_width=1, 
            border_color=self.accent_cyan, font=ctk.CTkFont(weight="bold", size=14), height=40, command=self.launch_check
        )
        btn_check.pack(pady=10)

    def setup_livetrack_frame(self):
        frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.frames["livetrack"] = frame
        lbl = ctk.CTkLabel(frame, text="Live Tracking UI elements will be displayed here.", font=ctk.CTkFont(size=16))
        lbl.pack(pady=20)

    def setup_analytics_frame(self):
        frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.frames["analytics"] = frame
        lbl = ctk.CTkLabel(frame, text="Analytics and Heatmaps will be displayed here.", font=ctk.CTkFont(size=16))
        lbl.pack(pady=20)

    def setup_setup_frame(self):
        frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.frames["setup"] = frame
        lbl = ctk.CTkLabel(frame, text="System Setup & Configuration.", font=ctk.CTkFont(size=16))
        lbl.pack(pady=20)

    def setup_profile_frame(self):
        frame = ctk.CTkFrame(self.main_frame, corner_radius=10, fg_color="transparent")
        self.frames["profile"] = frame
        lbl = ctk.CTkLabel(frame, text="Player Profile & Stats.", font=ctk.CTkFont(size=16))
        lbl.pack(pady=20)

    # --- Logic ---
    def update_status(self):
        p = SCRIPT_DIR / "alignment.json"
        if not p.exists():
            self.lbl_status.configure(text="Status: No alignment — run Align Cameras first", text_color=self.accent_cyan)
        else:
            try:
                data = json.loads(p.read_text())
                cams = sorted(int(k) for k in data.keys())
                self.lbl_status.configure(text=f"Status: Alignment ready (cameras {cams})", text_color=self.accent_green)
            except Exception:
                self.lbl_status.configure(text="Status: Alignment file unreadable", text_color="red")

    def launch_script(self, script_name):
        script_path = str(SCRIPT_DIR / script_name)
        # Using subprocess.Popen so the UI continues to run concurrently
        subprocess.Popen([sys.executable, script_path])

    def launch_detect(self):
        self.launch_script("detect.py")

    def launch_align(self):
        self.launch_script("align.py")
        
    def launch_check(self):
        self.launch_script("check_cameras.py")


if __name__ == "__main__":
    app = App()
    app.mainloop()
