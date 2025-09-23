"""
shopping_app.py
Requires: credentials.json (OAuth 2.0 Client ID - Desktop), firebase_key.json
Python packages: google-auth, google-auth-oauthlib, google-api-python-client, pillow, firebase-admin
"""

import os
import io
import sys
import threading
import tkinter as tk
from tkinter import messagebox, PhotoImage
from PIL import Image, ImageDraw, ImageFont
import base64


# Google OAuth/Gmail
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

# Firebase
import firebase_admin
from firebase_admin import credentials as fb_credentials
from firebase_admin import db

# ---- CONFIG ----
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send"
]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
FIREBASE_KEY = "firebase_key.json"
FIREBASE_DB_URL = "https://shopping-app-f5c0b-default-rtdb.asia-southeast1.firebasedatabase.app/"  # e.g., https://your-project.firebaseio.com

# --------- PyInstaller resource helper ---------
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ---------------- Shopping App ----------------
class ShoppingApp:
    def __init__(self, root):
        self.root = root
        root.title("Shopping List")
        root.geometry("700x600")
        root.minsize(520, 420)

        # theme dicts
        self.light = {"bg": "#ffffff", "card": "#f5f5f5", "fg": "#000000", "btn_bg": "#e0e0e0"}
        self.dark  = {"bg": "#1e1e1e", "card": "#2b2b2b", "fg": "#f1f1f1", "btn_bg": "#333333"}
        self.theme = self.light

        # Google credentials & services
        self.creds = None
        self.gmail_service = None
        self.user_email = None

        # Initialize Firebase
        self.init_firebase()

        # Build UI
        self.build_ui()
        self.apply_theme()

        # Try auto-login
        self.firebase_auto_login_threaded()

    # ---------------- Firebase ----------------
    def init_firebase(self):
        try:
            if not firebase_admin._apps:
                cred = fb_credentials.Certificate(resource_path(FIREBASE_KEY))
                firebase_admin.initialize_app(cred, {
                    "databaseURL": FIREBASE_DB_URL
                })
            self.fb_ref = db.reference("/users/credentials")
        except Exception as e:
            messagebox.showerror("Firebase init failed", str(e))

    def save_creds_to_firebase(self, creds):
        try:
            creds_dict = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }
            self.fb_ref.set(creds_dict)
        except Exception as e:
            print("Failed to save creds to Firebase:", e)

    def load_creds_from_firebase(self):
        try:
            creds_dict = self.fb_ref.get()
            if not creds_dict:
                return None
            creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
            return creds
        except Exception as e:
            print("Failed to load creds from Firebase:", e)
            return None

    def firebase_auto_login_threaded(self):
        t = threading.Thread(target=self.firebase_auto_login)
        t.daemon = True
        t.start()

    def firebase_auto_login(self):
        creds = self.load_creds_from_firebase()
        if creds:
            try:
                self.creds = creds
                self.gmail_service = build("gmail", "v1", credentials=self.creds)
                oauth2_service = build('oauth2', 'v2', credentials=self.creds)
                userinfo = oauth2_service.userinfo().get().execute()
                self.user_email = userinfo.get("email")
                self.email_lbl.config(text=self.user_email)
                messagebox.showinfo("Auto-login", f"Signed in as {self.user_email}")
            except Exception as e:
                print("Auto-login failed:", e)

    # ---------------- Build UI ----------------
    def build_ui(self):
        

        root = self.root

        # Top bar
        topbar = tk.Frame(root, height=60, bg=self.theme["bg"])
        topbar.pack(fill="x", side="top", padx=8, pady=6)

        title = tk.Label(topbar, text="Shopping List", font=("Segoe UI", 20, "bold"),
                         bg=self.theme["bg"], fg=self.theme["fg"])
        title.pack(side="left")

        # Load theme icons
        self.light_icon = PhotoImage(file=resource_path("light_mode.png"))
        self.dark_icon  = PhotoImage(file=resource_path("dark_mode.png"))

        # Theme toggle button
        self.theme_btn = tk.Button(topbar, image=self.light_icon, bd=0, bg=self.theme["bg"],
                                   activebackground=self.theme["bg"], command=self.toggle_theme)
        self.theme_btn.image = self.light_icon
        self.theme_btn.pack(side="right", padx=(8,0))
       

        # Log Out button below Sign In
        logout_btn = tk.Button(topbar, text="Log Out", command=self.log_out,
                            bg="#9e9e9e", fg="white", font=("Segoe UI", 10, "bold"), bd=0,
                            padx=10, pady=4, activebackground="#757575")
        logout_btn.pack(side="right", padx=(0,8), pady=(0,0))  # pushes it below



        # Sign-in button and email label
        self.email_lbl = tk.Label(topbar, text="Not signed in", anchor="e",
                                  bg=self.theme["bg"], fg=self.theme["fg"])
        self.email_lbl.pack(side="right", padx=(0,8))
        signin_btn = tk.Button(topbar, text="Sign in with Google", command=self.sign_in_threaded,
                               bg="#ff9800", fg="white", font=("Segoe UI", 10, "bold"), bd=0,
                               padx=10, pady=4, activebackground="#fb8c00")
        signin_btn.pack(side="right", padx=(0,8))

        # Center frame with scrollable cards
        body = tk.Frame(root, bg=self.theme["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(0,12))

        self.canvas = tk.Canvas(body, highlightthickness=0, bg=self.theme["bg"])
        vsb = tk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.cards_frame = tk.Frame(self.canvas, bg=self.theme["bg"])

        self.cards_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0,0), window=self.cards_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Bottom controls
        bottom = tk.Frame(root, height=56, bg=self.theme["bg"])
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0,12))

        add_btn = tk.Button(bottom, text="+ Add item", command=self.add_card,
                            bg="#4CAF50", fg="white", font=("Segoe UI", 12, "bold"),
                            bd=0, padx=12, pady=6, activebackground="#45a049")
        add_btn.pack(side="left", padx=8)

        send_btn = tk.Button(bottom, text="Send shopping list", command=self.send_threaded,
                             bg="#2196F3", fg="white", font=("Segoe UI", 12, "bold"),
                             bd=0, padx=12, pady=6, activebackground="#1976D2")
        send_btn.pack(side="right", padx=8)

        # Track card entry widgets
        self.card_entries = []
        self.add_card()

    # ---------------- Theme ----------------
    def log_out(self):
        # Clear credentials
        self.creds = None
        self.gmail_service = None
        self.user_email = None

        # Remove from Firebase
        try:
            self.fb_ref.delete()
        except Exception as e:
            print("Failed to delete Firebase credentials:", e)

        # Update UI
        self.email_lbl.config(text="Not signed in")
        messagebox.showinfo("Logged out", "You have been logged out successfully.")

    def apply_theme(self):
        t = self.theme
        self.root.configure(bg=t["bg"])

        for widget in self.root.winfo_children():
            try:
                if isinstance(widget, tk.Frame):
                    widget.configure(bg=t["bg"])
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=t["bg"], fg=t["fg"])
                elif isinstance(widget, tk.Button):
                    if widget != self.theme_btn:
                        widget.configure(bg=t["btn_bg"], fg=t["fg"], activebackground=t["btn_bg"])
            except Exception:
                pass

        self.canvas.configure(bg=t["bg"])
        for card in self.cards_frame.winfo_children():
            card.configure(bg=t["card"])
            for sub in card.winfo_children():
                if isinstance(sub, tk.Entry):
                    sub.configure(bg=t["card"], fg=t["fg"], insertbackground=t["fg"])
                elif isinstance(sub, tk.Button):
                    sub.configure(bg="#f44336" if t == self.light else "#e57373")

    def toggle_theme(self):
        self.theme = self.dark if self.theme == self.light else self.light
        self.apply_theme()
        icon_img = self.dark_icon if self.theme == self.dark else self.light_icon
        self.theme_btn.config(image=icon_img)
        self.theme_btn.image = icon_img

    # ---------------- Cards ----------------
    def add_card(self, initial_text=""):
        frame = tk.Frame(self.cards_frame, bd=0, relief="ridge", padx=12, pady=8, bg=self.theme["card"])
        frame.pack(fill="x", pady=6, padx=6)

        entry = tk.Entry(frame, font=("Segoe UI", 12), bg=self.theme["card"], fg=self.theme["fg"],
                         relief="flat", highlightthickness=0, bd=0)
        entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        entry.insert(0, initial_text)

        delete = tk.Button(frame, text="Delete", width=8,
                           command=lambda f=frame, e=entry: self.remove_card(f,e),
                           bg="#f44336", fg="white", bd=0, activebackground="#d32f2f")
        delete.pack(side="right")
        delete.bind("<Enter>", lambda e: delete.config(bg="#e57373"))
        delete.bind("<Leave>", lambda e: delete.config(bg="#f44336"))

        self.card_entries.append(entry)
        self.apply_theme()

    def remove_card(self, frame, entry):
        try:
            self.card_entries.remove(entry)
        except ValueError:
            pass
        frame.destroy()

    # ---------------- Google Sign-In ----------------
    def sign_in_threaded(self):
        t = threading.Thread(target=self.sign_in)
        t.daemon = True
        t.start()

    def sign_in(self):
        try:
            flow = InstalledAppFlow.from_client_secrets_file(resource_path(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
            self.creds = creds
            self.gmail_service = build("gmail", "v1", credentials=self.creds)
            oauth2_service = build('oauth2', 'v2', credentials=self.creds)
            userinfo = oauth2_service.userinfo().get().execute()
            self.user_email = userinfo.get("email")
            self.email_lbl.config(text=self.user_email)
            messagebox.showinfo("Signed in", f"Signed in as {self.user_email}")

            # Save credentials to Firebase
            self.save_creds_to_firebase(self.creds)
        except FileNotFoundError:
            messagebox.showerror("Missing credentials.json", f"Put your OAuth client credentials file named '{CREDENTIALS_FILE}' in the app folder.")
        except Exception as e:
            messagebox.showerror("Sign in failed", str(e))

    # ---------------- Generate in-memory shopping list image ----------------
    def take_screenshot(self):
        items = [e.get().strip() for e in self.card_entries if e.get().strip()]
        if not items:
            items = ["Your shopping list is empty."]

        padding = 20
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()

        bbox = font.getbbox("Ay")
        line_height = (bbox[3] - bbox[1]) + 10

        width = 600
        height = padding * 2 + line_height * len(items) + 40

        bg_color = (255, 255, 255) if self.theme == self.light else (30, 30, 30)
        fg_color = (0, 0, 0) if self.theme == self.light else (241, 241, 241)
        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        title = "Shopping List"
        bbox_title = draw.textbbox((0, 0), title, font=font)
        title_width = bbox_title[2] - bbox_title[0]
        draw.text(((width - title_width)//2, padding), title, fill=fg_color, font=font)

        y = padding + line_height + 10
        for item in items:
            draw.text((padding, y), f"- {item}", fill=fg_color, font=font)
            y += line_height

        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img_bytes

    # ---------------- Send email via Gmail API ----------------
    def create_message_with_attachment(self, sender, to, subject, message_text, img_bytes, filename="shopping_list.png"):
        message = MIMEMultipart()
        message["to"] = to
        message["from"] = sender
        message["subject"] = subject

        message.attach(MIMEText(message_text))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(img_bytes.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        message.attach(part)

        raw_bytes = base64.urlsafe_b64encode(message.as_bytes())
        raw_str = raw_bytes.decode()
        return {"raw": raw_str}

    def send_email(self):
        if not self.creds or not self.gmail_service or not self.user_email:
            messagebox.showwarning("Not signed in", "Please sign in with Google before sending.")
            return

        screenshot_bytes = self.take_screenshot()
        items = [e.get().strip() for e in self.card_entries if e.get().strip()]
        body_text = "Your shopping list:\n\n" + "\n".join(f"- {i}" for i in items) if items else "Your shopping list is empty."

        try:
            raw_msg = self.create_message_with_attachment(self.user_email, self.user_email,
                                                          "Your Shopping List", body_text, screenshot_bytes)
            self.gmail_service.users().messages().send(userId="me", body=raw_msg).execute()
            messagebox.showinfo("Sent", "Shopping list sent to your email!")
        except Exception as e:
            messagebox.showerror("Send failed", f"Error sending email: {e}")

    def send_threaded(self):
        t = threading.Thread(target=self.send_email)
        t.daemon = True
        t.start()

if __name__ == "__main__":
    root = tk.Tk()
    icon = PhotoImage(file=resource_path("shopping_icon.png"))
    root.iconphoto(True, icon)
    app = ShoppingApp(root)
    root.mainloop()
