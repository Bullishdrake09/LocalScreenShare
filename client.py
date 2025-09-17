# remote_client_gui.py — TRUE FULLSCREEN REMOTE CONTROL MODE
# Host screen fills entire client display. Host mouse follows client mouse 1:1.

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socket
import struct
import pickle
import cv2
from PIL import Image, ImageTk
import numpy as np
from pynput import mouse, keyboard
import time
import concurrent.futures

class RemoteClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Local Remote Control")
        self.root.geometry("1000x750")
        self.root.configure(bg="#121212")

        self.connected = False
        self.target_ip = None
        self.sock = None
        self.running = False
        self.fullscreen = False

        # Store remote screen resolution (updated when first frame arrives)
        self.remote_width = 1920
        self.remote_height = 1080

        # UI Elements (will be hidden in fullscreen)
        self.top_widgets = []

        # === Scanning UI ===
        scan_frame = tk.Frame(root, bg="#121212")
        scan_frame.pack(pady=10)
        self.top_widgets.append(scan_frame)
        tk.Label(scan_frame, text="Scan LAN for Hosts:", bg="#121212", fg="white").pack(side=tk.LEFT)
        self.scan_button = tk.Button(scan_frame, text="Scan LAN", command=self.start_scan, bg="#333", fg="white", relief="flat")
        self.scan_button.pack(side=tk.LEFT, padx=5)
        self.status_label = tk.Label(scan_frame, text="Idle", fg="gray", bg="#121212", font=("Consolas", 9))
        self.status_label.pack(side=tk.LEFT, padx=5)

        # === Manual IP Entry ===
        manual_frame = tk.Frame(root, bg="#121212")
        manual_frame.pack(pady=5)
        self.top_widgets.append(manual_frame)
        tk.Label(manual_frame, text="Or enter IP manually:", bg="#121212", fg="white").pack(side=tk.LEFT)
        self.ip_entry = tk.Entry(manual_frame, width=15, bg="#333", fg="white", insertbackground="white")
        self.ip_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(manual_frame, text="Connect", command=self.connect_manual, bg="#333", fg="white", relief="flat").pack(side=tk.LEFT, padx=5)

        # === Host List ===
        list_frame = tk.Frame(root, bg="#121212")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.top_widgets.append(list_frame)
        tk.Label(list_frame, text="Discovered Hosts:", bg="#121212", fg="white").pack(anchor=tk.W)
        self.host_listbox = tk.Listbox(list_frame, height=6, font=("Consolas", 10), bg="#222", fg="white", selectbackground="#444")
        self.host_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.host_listbox.bind('<Double-1>', self.on_host_select)

        # === Control Buttons ===
        btn_frame = tk.Frame(root, bg="#121212")
        btn_frame.pack(pady=5)
        self.top_widgets.append(btn_frame)

        self.connect_button = tk.Button(btn_frame, text="Connect to Selected", command=self.connect_to_host, state=tk.DISABLED, bg="#333", fg="white", relief="flat")
        self.connect_button.pack(side=tk.LEFT, padx=5)

        self.fullscreen_button = tk.Button(btn_frame, text="Toggle Fullscreen (F11)", command=self.toggle_fullscreen, bg="#333", fg="white", relief="flat")
        self.fullscreen_button.pack(side=tk.LEFT, padx=5)

        # === Video Canvas ===
        self.canvas = tk.Canvas(root, bg='black', relief="sunken", bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bind keys
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())

        # Mouse/Keyboard hooks
        self.mouse_listener = None
        self.keyboard_listener = None

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.apply_fullscreen_mode()

    def apply_fullscreen_mode(self):
        self.root.attributes("-fullscreen", self.fullscreen)
        if self.fullscreen:
            self.root.config(cursor="none")
            # Hide all top widgets
            for widget in self.top_widgets:
                widget.pack_forget()
            self.canvas.focus_set()
        else:
            self.root.config(cursor="")
            self.root.geometry("1000x750")
            # Show all top widgets
            self.scan_button.pack(side=tk.LEFT, padx=5)  # repack scan_frame children
            self.status_label.pack(side=tk.LEFT, padx=5)
            self.ip_entry.pack(side=tk.LEFT, padx=5)     # repack manual_frame
            self.host_listbox.pack(fill=tk.BOTH, expand=True, pady=5)  # repack list_frame
            self.connect_button.pack(side=tk.LEFT, padx=5)  # repack btn_frame
            self.fullscreen_button.pack(side=tk.LEFT, padx=5)

    def exit_fullscreen(self):
        if self.fullscreen:
            self.fullscreen = False
            self.apply_fullscreen_mode()

    def start_scan(self):
        self.status_label.config(text="Scanning...", fg="orange")
        self.host_listbox.delete(0, tk.END)
        self.connect_button.config(state=tk.DISABLED)
        threading.Thread(target=self.scan_lan, daemon=True).start()

    def scan_host(self, ip, port=65432):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return ip
        except:
            pass
        return None

    def scan_lan(self):
        port = 65432
        found = []

        test_ips = ["127.0.0.1"]
        for i in range(1, 255):
            test_ips.append(f"192.168.1.{i}")

        self.root.after(0, self.update_scan_status, f"Scanning {len(test_ips)} hosts... (3s timeout)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            future_to_ip = {executor.submit(self.scan_host, ip, port): ip for ip in test_ips}
            done, not_done = concurrent.futures.wait(future_to_ip.keys(), timeout=3.0)

            for future in not_done:
                future.cancel()

            for future in done:
                try:
                    result = future.result()
                    if result:
                        found.append(result)
                        self.root.after(0, self.add_host_live, result)
                except Exception as e:
                    print(f"Scan error: {e}")

        self.root.after(0, self.update_scan_results, found)

    def add_host_live(self, ip):
        self.host_listbox.insert(tk.END, ip)

    def update_scan_status(self, msg):
        self.status_label.config(text=msg, fg="blue")

    def update_scan_results(self, hosts):
        status = f"Scan complete. Found {len(hosts)} host(s)." if hosts else "Scan complete. No hosts found."
        color = "green" if hosts else "red"
        self.status_label.config(text=status, fg=color)
        if hosts:
            self.connect_button.config(state=tk.NORMAL)
            if self.host_listbox.size() > 0:
                self.host_listbox.selection_set(0)
                self.target_ip = self.host_listbox.get(0)

    def on_host_select(self, event):
        selection = self.host_listbox.curselection()
        if selection:
            self.target_ip = self.host_listbox.get(selection[0])
            self.connect_to_host()

    def connect_manual(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter an IP address")
            return
        self.target_ip = ip
        self.connect_to_host()

    def connect_to_host(self):
        if not self.target_ip:
            messagebox.showerror("Error", "No host selected or entered!")
            return

        try:
            self.status_label.config(text=f"Connecting to {self.target_ip}...", fg="orange")
            self.root.update_idletasks()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.target_ip, 65432))
            self.sock.settimeout(None)

            self.connected = True
            self.status_label.config(text=f"Connected to {self.target_ip} ✅", fg="green")
            self.connect_button.config(text="Disconnect", command=self.disconnect)

            self.running = True
            threading.Thread(target=self.receive_screen, daemon=True).start()
            self.start_input_capture()

            # ➤ AUTO-ENTER FULLSCREEN ON CONNECT
            self.fullscreen = True
            self.apply_fullscreen_mode()

        except Exception as e:
            messagebox.showerror("Connection Failed", f"Could not connect to {self.target_ip}:\n{str(e)}")
            self.status_label.config(text="Connection failed ❌", fg="red")

    def disconnect(self):
        if not hasattr(self, 'root') or not self.root:
            return

        def _disconnect():
            self.running = False
            self.connected = False

            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None

            self.stop_input_capture()
            self.canvas.delete("all")

            # ➤ EXIT FULLSCREEN ON DISCONNECT
            self.fullscreen = False
            self.apply_fullscreen_mode()

            self.status_label.config(text="Disconnected", fg="gray")
            self.connect_button.config(text="Connect to Selected", command=self.connect_to_host)

        if threading.current_thread() is threading.main_thread():
            _disconnect()
        else:
            self.root.after(0, _disconnect)

    def receive_screen(self):
        data = b""
        payload_size = struct.calcsize(">L")

        while self.running:
            try:
                while len(data) < payload_size:
                    packet = self.sock.recv(4096)
                    if not packet:
                        raise ConnectionError("Server closed connection")
                    data += packet

                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack(">L", packed_msg_size)[0]

                while len(data) < msg_size:
                    packet = self.sock.recv(4096)
                    if not packet:
                        raise ConnectionError("Server closed connection")
                    data += packet

                frame_data = data[:msg_size]
                data = data[msg_size:]

                frame = pickle.loads(frame_data, fix_imports=True, encoding="bytes")
                frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                # ➤ Update remote resolution
                self.remote_height, self.remote_width = frame.shape[:2]

                # ➤ In fullscreen: stretch to fill entire screen (no black bars)
                if self.fullscreen:
                    canvas_width = self.root.winfo_screenwidth()
                    canvas_height = self.root.winfo_screenheight()
                    frame = cv2.resize(frame, (canvas_width, canvas_height), interpolation=cv2.INTER_LINEAR)
                else:
                    # Normal mode: fit in canvas
                    canvas_width = self.canvas.winfo_width()
                    canvas_height = self.canvas.winfo_height()
                    if canvas_width > 1 and canvas_height > 1:
                        h, w = frame.shape[:2]
                        scale_w = canvas_width / w
                        scale_h = canvas_height / h
                        scale = min(scale_w, scale_h)
                        new_w, new_h = int(w * scale), int(h * scale)
                        if new_w > 0 and new_h > 0:
                            frame = cv2.resize(frame, (new_w, new_h))

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)

                self.root.after(0, self.update_canvas, imgtk)

            except Exception as e:
                print("Screen receive error:", e)
                break

        self.root.after(0, self.disconnect)

    def update_canvas(self, imgtk):
        self.canvas.delete("all")
        if self.fullscreen:
            # Stretch to fill screen
            self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
        else:
            # Center in canvas
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            iw = imgtk.width()
            ih = imgtk.height()
            x = (cw - iw) // 2
            y = (ch - ih) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=imgtk)
        self.canvas.image = imgtk

    def start_input_capture(self):
        if self.mouse_listener or self.keyboard_listener:
            self.stop_input_capture()

        def safe_send(data):
            if not self.connected or not self.sock:
                return False
            try:
                self.sock.sendall((data + '\n').encode('utf-8'))
                return True
            except (OSError, ConnectionError, Exception) as e:
                print(f"[Input] Send failed: {e}")
                self.root.after(0, self.disconnect)
                return False

        def on_move(x, y):
            if not self.fullscreen:
                return  # Only control host when in fullscreen

            # ➤ Map client screen position → to host screen resolution
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            # Calculate ratio
            xr = x / screen_width
            yr = y / screen_height

            # Map to remote resolution
            target_x = int(xr * self.remote_width)
            target_y = int(yr * self.remote_height)

            safe_send(f"MOVE|{target_x}|{target_y}")

        def on_click(x, y, button, pressed):
            if not self.fullscreen:
                return
            btn = 'left' if button == mouse.Button.left else 'right'
            safe_send(f"CLICK|{btn}|{pressed}")

        def on_scroll(x, y, dx, dy):
            if not self.fullscreen:
                return
            safe_send(f"SCROLL|{dx}|{dy}")

        def on_press(key):
            if not self.fullscreen:
                return
            try:
                k = str(key).replace("'", "")
                if k.startswith('Key.'):
                    k = k[4:]
                if k == 'f11' or k == 'escape':
                    return  # Let local system handle
                safe_send(f"KEY|{k}|press")
            except Exception as e:
                print(f"[Input] Key press error: {e}")

        def on_release(key):
            if not self.fullscreen:
                return
            try:
                k = str(key).replace("'", "")
                if k.startswith('Key.'):
                    k = k[4:]
                if k == 'f11' or k == 'escape':
                    return
                safe_send(f"KEY|{k}|release")
            except Exception as e:
                print(f"[Input] Key release error: {e}")

        try:
            self.mouse_listener = mouse.Listener(
                on_move=on_move,
                on_click=on_click,
                on_scroll=on_scroll,
                daemon=True
            )
            self.keyboard_listener = keyboard.Listener(
                on_press=on_press,
                on_release=on_release,
                daemon=True
            )
            self.mouse_listener.start()
            self.keyboard_listener.start()
            print("[Input] Listeners started")
        except Exception as e:
            print(f"[Input] Failed to start listeners: {e}")

    def stop_input_capture(self):
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass
            self.mouse_listener = None
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except Exception:
                pass
            self.keyboard_listener = None

if __name__ == "__main__":
    root = tk.Tk()
    root.configure(bg="#121212")
    app = RemoteClientApp(root)
    root.mainloop()
