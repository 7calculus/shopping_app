# fancy_ui.py
import tkinter as tk
from tkinter import ttk
import shopping_app  # import the original app

def apply_fancy_ui(root, listbox):
    # Change window background
    root.configure(bg="#f2f2f2")
    
    # Style the listbox
    listbox.configure(bg="#ffffff", fg="#333333", font=("Helvetica", 12), bd=0, highlightthickness=0)
    
    # Add padding around the listbox
    for widget in root.winfo_children():
        widget.pack_configure(padx=20, pady=10)
    
    # Add a title label
    title = tk.Label(root, text="🛒 My Fancy Shopping List", font=("Helvetica", 16, "bold"), bg="#f2f2f2")
    title.pack(before=listbox)

    # Style all buttons (if any)
    style = ttk.Style()
    style.configure("TButton", font=("Helvetica", 12), padding=6, foreground="#ffffff", background="#007acc")
    style.map("TButton", background=[("active", "#005f99")])

if __name__ == "__main__":
    # Apply the changes to the original app
    apply_fancy_ui(shopping_app.root, shopping_app.listbox)
    shopping_app.root.mainloop()
