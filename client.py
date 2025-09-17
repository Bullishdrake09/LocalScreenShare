# remote_client_gui_enhanced.py — ENHANCED WITH MOUSE SYNC & VISIBILITY
# Advanced mouse synchronization, visual feedback, and performance optimizations

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socket
import struct
import pickle
import cv2
from PIL import Image, ImageTk, ImageDraw
import numpy as np
from pynput import mouse, keyboard
import time
import concurrent.futures
import queue

class RemoteClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎯 Enhanced Remote Desktop Client")
        self.root.geometry("1200x800")
        self.root.configure(bg="#0a0a0a")

        # Connection state
        self.connected = False
        self.target_ip = None
        self.sock = None
        self.running = False
        self.fullscreen = False
        
        # Remote desktop dimensions
        self.remote_width = 1920
        self.remote_height = 1080
        
        # Mouse synchronization
        self.remote_mouse_pos = (0, 0)
        self.remote_mouse_visible = True
        self.mouse_over_canvas = False
        self.client_cursor_hidden = False
        self.show_remote_cursor = True
        
        # Performance tracking
        self.frame_count = 0
        self.last_frame_time = 0
        self.fps = 0
        self.latency = 0
        self.last_ping_time = 0
        
        # Data queues
        self.screen_queue = queue.Queue(maxsize=2)
        self.mouse_queue = queue.Queue(maxsize=10)
        
        self.top_widgets = []
        self.setup_ui()
        
        # Input listeners
        self.mouse_listener = None
        self.keyboard_listener = None
        
        # Start performance monitoring
        threading.Thread(target=self.monitor_performance, daemon=True).start()

    def setup_ui(self):
        """Setup enhanced UI with better visual feedback"""
        # === Header Frame ===
        header_frame = tk.Frame(self.root, bg="#0a0a0a", height=120)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        header_frame.pack_propagate(False)
        self.top_widgets.append(header_frame)
        
        # Title
        title_label = tk.Label(header_frame, text="🎯 Enhanced Remote Desktop", 
                              font=("Segoe UI", 16, "bold"), bg="#0a0a0a", fg="#00ff88")
        title_label.pack(pady=5)
        
        # === Scanning UI ===
        scan_frame = tk.Frame(header_frame, bg="#0a0a0a")
        scan_frame.pack(pady=5)
        
        tk.Label(scan_frame, text="🔍 Scan Network:", bg="#0a0a0a", fg="white", 
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        
        self.scan_button = tk.Button(scan_frame, text="Scan LAN", command=self.start_scan, 
                                    bg="#2d5a2d", fg="white", relief="flat", 
                                    font=("Segoe UI", 9), padx=15)
        self.scan_button.pack(side=tk.LEFT, padx=10)
        
        self.status_label = tk.Label(scan_frame, text="Ready to scan", fg="#888", 
                                   bg="#0a0a0a", font=("Consolas", 9))
        self.status_label.pack(side=tk.LEFT, padx=10)

        # === Manual IP Entry ===
        manual_frame = tk.Frame(header_frame, bg="#0a0a0a")
        manual_frame.pack(pady=5)
        
        tk.Label(manual_frame, text="📡 Direct Connect:", bg="#0a0a0a", fg="white",
                font=("Segoe UI", 10)).pack(side=tk.LEFT)
        
        self.ip_entry = tk.Entry(manual_frame, width=15, bg="#1a1a1a", fg="white", 
                                insertbackground="white", font=("Consolas", 10),
                                relief="flat", bd=5)
        self.ip_entry.pack(side=tk.LEFT, padx=10)
        self.ip_entry.bind("<Return>", lambda e: self.connect_manual())
        
        tk.Button(manual_frame, text="Connect", command=self.connect_manual, 
                 bg="#2d5a2d", fg="white", relief="flat", font=("Segoe UI", 9),
                 padx=15).pack(side=tk.LEFT, padx=5)

        # === Host List ===
        list_frame = tk.Frame(self.root, bg="#0a0a0a")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.top_widgets.append(list_frame)
        
        tk.Label(list_frame, text="🖥️ Discovered Hosts:", bg="#0a0a0a", fg="white",
                font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.host_listbox = tk.Listbox(list_frame, height=6, font=("Consolas", 10), 
                                      bg="#1a1a1a", fg="white", selectbackground="#444",
                                      relief="flat", bd=0)
        self.host_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.host_listbox.bind('<Double-1>', self.on_host_select)

        # === Control Panel ===
        control_frame = tk.Frame(self.root, bg="#0a0a0a")
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        self.top_widgets.append(control_frame)

        # Connection controls
        conn_frame = tk.Frame(control_frame, bg="#0a0a0a")
        conn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.connect_button = tk.Button(conn_frame, text="🔗 Connect to Selected", 
                                       command=self.connect_to_host, state=tk.DISABLED,
                                       bg="#2d4d5a", fg="white", relief="flat",
                                       font=("Segoe UI", 10), padx=20)
        self.connect_button.pack(side=tk.LEFT, padx=5)

        self.fullscreen_button = tk.Button(conn_frame, text="🖥️ Fullscreen (F11)", 
                                          command=self.toggle_fullscreen,
                                          bg="#5a2d5a", fg="white", relief="flat",
                                          font=("Segoe UI", 10), padx=15)
        self.fullscreen_button.pack(side=tk.LEFT, padx=5)
        
        # Mouse settings
        mouse_frame = tk.Frame(control_frame, bg="#0a0a0a")
        mouse_frame.pack(side=tk.RIGHT)
        
        self.cursor_var = tk.BooleanVar(value=True)
        cursor_check = tk.Checkbutton(mouse_frame, text="Show Remote Cursor", 
                                     variable=self.cursor_var, bg="#0a0a0a", fg="white",
                                     selectcolor="#2d2d2d", font=("Segoe UI", 9))
        cursor_check.pack(side=tk.RIGHT, padx=5)

        # === Status Bar ===
        status_frame = tk.Frame(self.root, bg="#1a1a1a", height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        self.top_widgets.append(status_frame)
        
        self.perf_label = tk.Label(status_frame, text="FPS: -- | Latency: -- ms", 
                                  bg="#1a1a1a", fg="#888", font=("Consolas", 9))
        self.perf_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.connection_label = tk.Label(status_frame, text="Not Connected", 
                                        bg="#1a1a1a", fg="#ff6666", font=("Segoe UI", 9))
        self.connection_label.pack(side=tk.LEFT, padx=10, pady=5)

        # === Video Canvas ===
        self.canvas = tk.Canvas(self.root, bg='#000000', relief="flat", bd=0, 
                               highlightthickness=1, highlightbackground="#333")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Canvas mouse events for cursor management
        self.canvas.bind("<Enter>", self.on_canvas_enter)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
        self.canvas.bind("<Motion>", self.on_canvas_motion)

        # Keyboard shortcuts
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())
        self.root.bind("<Control-q>", lambda e: self.disconnect())

    def on_canvas_enter(self, event):
        """Mouse entered the canvas area"""
        self.mouse_over_canvas = True
        if self.connected and self.fullscreen:
            self.hide_client_cursor()
    
    def on_canvas_leave(self, event):
        """Mouse left the canvas area"""
        self.mouse_over_canvas = False
        self.show_client_cursor()
    
    def on_canvas_motion(self, event):
        """Track mouse motion over canvas"""
        if self.connected and self.fullscreen and not self.client_cursor_hidden:
            self.hide_client_cursor()

    def hide_client_cursor(self):
        """Hide the client's cursor"""
        if not self.client_cursor_hidden:
            self.root.config(cursor="none")
            self.client_cursor_hidden = True

    def show_client_cursor(self):
        """Show the client's cursor"""
        if self.client_cursor_hidden:
            self.root.config(cursor="")
            self.client_cursor_hidden = False

    def toggle_fullscreen(self):
        """Enhanced fullscreen toggle with cursor management"""
        self.fullscreen = not self.fullscreen
        self.apply_fullscreen_mode()

    def apply_fullscreen_mode(self):
        """Apply fullscreen mode with proper cursor handling"""
        self.root.attributes("-fullscreen", self.fullscreen)
        
        if self.fullscreen:
            # Hide UI elements
            for widget in self.top_widgets:
                widget.pack_forget()
            self.canvas.focus_set()
            
            # Hide cursor if connected and mouse is over canvas
            if self.connected and self.mouse_over_canvas:
                self.hide_client_cursor()
        else:
            # Show UI elements
            self.show_client_cursor()
            self.root.geometry("1200x800")
            
            # Re-pack widgets in correct order
            header_frame = self.top_widgets[0]
            list_frame = self.top_widgets[1] 
            control_frame = self.top_widgets[2]
            status_frame = self.top_widgets[3]
            
            header_frame.pack(fill=tk.X, padx=10, pady=5)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            control_frame.pack(fill=tk.X, padx=10, pady=5)
            status_frame.pack(fill=tk.X, side=tk.BOTTOM)

    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        if self.fullscreen:
            self.fullscreen = False
            self.apply_fullscreen_mode()

    def start_scan(self):
        """Start network scanning with better feedback"""
        self.status_label.config(text="🔍 Scanning network...", fg="#ffaa00")
        self.host_listbox.delete(0, tk.END)
        self.connect_button.config(state=tk.DISABLED)
        self.scan_button.config(state=tk.DISABLED, text="Scanning...")
        threading.Thread(target=self.scan_lan, daemon=True).start()

    def scan_host(self, ip, port=65432):
        """Enhanced host scanning with better timeout"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.8)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return ip
        except Exception:
            pass
        return None

    def scan_lan(self):
        """Enhanced LAN scanning with progress updates"""
        port = 65432
        found = []
        
        # Common IP ranges
        test_ips = ["127.0.0.1"]  # Localhost first
        
        # Add common private network ranges
        for i in range(1, 255):
            test_ips.append(f"192.168.1.{i}")
            test_ips.append(f"192.168.0.{i}")
            if i <= 20:  # Limit 10.x range
                test_ips.append(f"10.0.0.{i}")

        total_hosts = len(test_ips)
        self.root.after(0, self.update_scan_status, f"🔍 Scanning {total_hosts} addresses...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=150) as executor:
            future_to_ip = {executor.submit(self.scan_host, ip, port): ip for ip in test_ips}
            completed = 0
            
            for future in concurrent.futures.as_completed(future_to_ip.keys(), timeout=4.0):
                completed += 1
                try:
                    result = future.result()
                    if result:
                        found.append(result)
                        self.root.after(0, self.add_host_live, result)
                        
                    # Update progress
                    if completed % 50 == 0:
                        progress = int((completed / total_hosts) * 100)
                        self.root.after(0, self.update_scan_status, 
                                       f"🔍 Scanning... {progress}% ({len(found)} found)")
                        
                except Exception:
                    pass

        self.root.after(0, self.update_scan_results, found)

    def add_host_live(self, ip):
        """Add discovered host to list"""
        self.host_listbox.insert(tk.END, f"🖥️ {ip}")

    def update_scan_status(self, msg):
        """Update scan status"""
        self.status_label.config(text=msg, fg="#00aaff")

    def update_scan_results(self, hosts):
        """Update scan completion status"""
        if hosts:
            status = f"✅ Scan complete! Found {len(hosts)} host(s)"
            color = "#00ff88"
            self.connect_button.config(state=tk.NORMAL)
            if self.host_listbox.size() > 0:
                self.host_listbox.selection_set(0)
                selected = self.host_listbox.get(0)
                self.target_ip = selected.replace("🖥️ ", "")
        else:
            status = "❌ Scan complete - No hosts found"
            color = "#ff6666"
            
        self.status_label.config(text=status, fg=color)
        self.scan_button.config(state=tk.NORMAL, text="Scan LAN")

    def on_host_select(self, event):
        """Handle host selection"""
        selection = self.host_listbox.curselection()
        if selection:
            selected = self.host_listbox.get(selection[0])
            self.target_ip = selected.replace("🖥️ ", "")
            self.connect_to_host()

    def connect_manual(self):
        """Connect to manually entered IP"""
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Please enter an IP address")
            return
        self.target_ip = ip
        self.connect_to_host()

    def connect_to_host(self):
        """Enhanced connection with better feedback"""
        if not self.target_ip:
            messagebox.showerror("Error", "No host selected or entered!")
            return

        try:
            self.connection_label.config(text=f"🔄 Connecting to {self.target_ip}...", fg="#ffaa00")
            self.connect_button.config(state=tk.DISABLED, text="Connecting...")
            self.root.update_idletasks()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
            self.sock.settimeout(5)
            self.sock.connect((self.target_ip, 65432))
            self.sock.settimeout(None)

            self.connected = True
            self.connection_label.config(text=f"✅ Connected to {self.target_ip}", fg="#00ff88")
            self.connect_button.config(text="🔌 Disconnect", command=self.disconnect, state=tk.NORMAL)

            self.running = True
            
            # Start data receiving threads
            threading.Thread(target=self.receive_data, daemon=True).start()
            threading.Thread(target=self.process_screen_frames, daemon=True).start()
            threading.Thread(target=self.process_mouse_updates, daemon=True).start()
            threading.Thread(target=self.ping_server, daemon=True).start()
            
            self.start_input_capture()

            # Auto-enter fullscreen for better experience
            time.sleep(0.5)  # Brief delay for connection to stabilize
            self.fullscreen = True
            self.apply_fullscreen_mode()

        except Exception as e:
            messagebox.showerror("Connection Failed", f"Could not connect to {self.target_ip}:\n{str(e)}")
            self.connection_label.config(text="❌ Connection failed", fg="#ff6666")
            self.connect_button.config(text="🔗 Connect to Selected", command=self.connect_to_host, state=tk.NORMAL)

    def disconnect(self):
        """Enhanced disconnect with cleanup"""
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
            self.show_client_cursor()
            self.canvas.delete("all")

            # Clear queues
            while not self.screen_queue.empty():
                try:
                    self.screen_queue.get_nowait()
                except:
                    break
            
            while not self.mouse_queue.empty():
                try:
                    self.mouse_queue.get_nowait()
                except:
                    break

            self.fullscreen = False
            self.apply_fullscreen_mode()

            self.connection_label.config(text="❌ Disconnected", fg="#888")
            self.connect_button.config(text="🔗 Connect to Selected", command=self.connect_to_host, state=tk.NORMAL)
            self.perf_label.config(text="FPS: -- | Latency: -- ms")

        if threading.current_thread() is threading.main_thread():
            _disconnect()
        else:
            self.root.after(0, _disconnect)

    def receive_data(self):
        """Enhanced data receiver with protocol handling"""
        while self.running:
            try:
                # Read protocol header (4 bytes)
                header = b""
                while len(header) < 4:
                    chunk = self.sock.recv(4 - len(header))
                    if not chunk:
                        raise ConnectionError("Server closed connection")
                    header += chunk

                protocol = header
                
                # Read data size (4 bytes)
                size_data = b""
                while len(size_data) < 4:
                    chunk = self.sock.recv(4 - len(size_data))
                    if not chunk:
                        raise ConnectionError("Server closed connection")
                    size_data += chunk
                
                data_size = struct.unpack(">L", size_data)[0]
                
                # Read actual data
                data = b""
                while len(data) < data_size:
                    chunk = self.sock.recv(min(8192, data_size - len(data)))
                    if not chunk:
                        raise ConnectionError("Server closed connection")
                    data += chunk

                # Process based on protocol
                if protocol == b'SCRN':
                    try:
                        self.screen_queue.put_nowait(data)
                    except queue.Full:
                        # Drop old frame if queue is full
                        try:
                            self.screen_queue.get_nowait()
                            self.screen_queue.put_nowait(data)
                        except:
                            pass
                            
                elif protocol == b'MOUS':
                    try:
                        self.mouse_queue.put_nowait(data)
                    except queue.Full:
                        # Always process latest mouse data
                        while not self.mouse_queue.empty():
                            try:
                                self.mouse_queue.get_nowait()
                            except:
                                break
                        self.mouse_queue.put_nowait(data)
                        
                elif protocol == b'PONG':
                    # Handle pong response for latency calculation
                    if self.last_ping_time > 0:
                        self.latency = (time.time() - self.last_ping_time) * 1000

            except Exception as e:
                print(f"Data receive error: {e}")
                break

        self.root.after(0, self.disconnect)

    def process_screen_frames(self):
        """Process screen frames from queue"""
        while self.running:
            try:
                data = self.screen_queue.get(timeout=0.1)
                screen_data = pickle.loads(data)
                
                if screen_data['type'] == 'SCREEN_FRAME':
                    frame = cv2.imdecode(screen_data['frame'], cv2.IMREAD_COLOR)
                    if frame is None:
                        continue

                    self.remote_width = screen_data['width']
                    self.remote_height = screen_data['height']

                    # Resize frame for display
                    if self.fullscreen:
                        screen_width = self.root.winfo_screenwidth()
                        screen_height = self.root.winfo_screenheight()
                        frame = cv2.resize(frame, (screen_width, screen_height), 
                                         interpolation=cv2.INTER_LINEAR)
                    else:
                        canvas_width = self.canvas.winfo_width()
                        canvas_height = self.canvas.winfo_height()
                        if canvas_width > 1 and canvas_height > 1:
                            h, w = frame.shape[:2]
                            scale = min(canvas_width / w, canvas_height / h)
                            new_w, new_h = int(w * scale), int(h * scale)
                            if new_w > 0 and new_h > 0:
                                frame = cv2.resize(frame, (new_w, new_h), 
                                                 interpolation=cv2.INTER_AREA)

                    # Convert and create image
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame)
                    
                    # Add remote cursor overlay if enabled
                    if self.cursor_var.get() and self.show_remote_cursor:
                        img = self.add_cursor_overlay(img)
                    
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.root.after(0, self.update_canvas, imgtk)
                    
                    # Update FPS
                    current_time = time.time()
                    if self.last_frame_time > 0:
                        self.fps = 1.0 / (current_time - self.last_frame_time)
                    self.last_frame_time = current_time
                    self.frame_count += 1

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Frame processing error: {e}")
                break

    def process_mouse_updates(self):
        """Process mouse position updates from queue"""
        while self.running:
            try:
                data = self.mouse_queue.get(timeout=0.1)
                mouse_data = pickle.loads(data)
                
                if mouse_data['type'] == 'MOUSE_INFO':
                    self.remote_mouse_pos = (mouse_data['x'], mouse_data['y'])
                    self.remote_mouse_visible = mouse_data['visible']
                    
                    # Update cursor visibility based on remote state
                    if mouse_data['controlling'] and self.fullscreen and self.mouse_over_canvas:
                        self.hide_client_cursor()
                    elif not mouse_data['controlling']:
                        self.show_client_cursor()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Mouse processing error: {e}")
                break

    def add_cursor_overlay(self, img):
        """Add remote cursor overlay to the image"""
        if not self.remote_mouse_visible:
            return img
            
        # Calculate cursor position relative to display
        if self.fullscreen:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            cursor_x = int((self.remote_mouse_pos[0] / self.remote_width) * screen_width)
            cursor_y = int((self.remote_mouse_pos[1] / self.remote_height) * screen_height)
        else:
            img_width, img_height = img.size
            cursor_x = int((self.remote_mouse_pos[0] / self.remote_width) * img_width)
            cursor_y = int((self.remote_mouse_pos[1] / self.remote_height) * img_height)
        
        # Draw cursor
        draw = ImageDraw.Draw(img)
        cursor_size = 12
        
        # Draw cursor arrow shape
        points = [
            (cursor_x, cursor_y),
            (cursor_x, cursor_y + cursor_size),
            (cursor_x + cursor_size//3, cursor_y + cursor_size*2//3),
            (cursor_x + cursor_size//2, cursor_y + cursor_size//2),
            (cursor_x + cursor_size, cursor_y)
        ]
        
        # Draw cursor with outline for visibility
        draw.polygon(points, fill='white', outline='black', width=1)
        
        return img

    def update_canvas(self, imgtk):
        """Update canvas with new image"""
        self.canvas.delete("all")
        if self.fullscreen:
            self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
        else:
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            iw, ih = imgtk.width(), imgtk.height()
            x, y = (cw - iw) // 2, (ch - ih) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=imgtk)
        self.canvas.image = imgtk

    def ping_server(self):
        """Send periodic pings to measure latency"""
        while self.running:
            try:
                self.last_ping_time = time.time()
                self.sock.sendall(b'PING\n')
                time.sleep(1.0)
            except Exception:
                break

    def monitor_performance(self):
        """Monitor and display performance metrics"""
        while True:
            if self.connected:
                fps_text = f"FPS: {self.fps:.1f}"
                latency_text = f"Latency: {self.latency:.0f}ms"
                self.root.after(0, self.update_performance_display, f"{fps_text} | {latency_text}")
            time.sleep(1.0)

    def update_performance_display(self, text):
        """Update performance display"""
        self.perf_label.config(text=text)

    def start_input_capture(self):
        """Enhanced input capture with better responsiveness"""
        if self.mouse_listener or self.keyboard_listener:
            self.stop_input_capture()

        def safe_send(data):
            if not self.connected or not self.sock:
                return False
            try:
                self.sock.sendall((data + '\n').encode('utf-8'))
                return True
            except Exception as e:
                print(f"[Input] Send failed: {e}")
                self.root.after(0, self.disconnect)
                return False

        def on_move(x, y):
            if not self.fullscreen or not self.connected:
                return

            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            xr = x / screen_width
            yr = y / screen_height

            target_x = int(xr * self.remote_width)
            target_y = int(yr * self.remote_height)

            safe_send(f"MOVE|{target_x}|{target_y}")

        def on_click(x, y, button, pressed):
            if not self.fullscreen or not self.connected:
                return
            btn = 'left' if button == mouse.Button.left else 'right'
            safe_send(f"CLICK|{btn}|{pressed}")

        def on_scroll(x, y, dx, dy):
            if not self.fullscreen or not self.connected:
                return
            safe_send(f"SCROLL|{dx}|{dy}")

        def on_press(key):
            if not self.fullscreen or not self.connected:
                return
            try:
                k = str(key).replace("'", "")
                if k.startswith('Key.'):
                    k = k[4:]
                if k in ('f11', 'escape'):
                    return
                safe_send(f"KEY|{k}|press")
            except Exception as e:
                print(f"[Input] Key press error: {e}")

        def on_release(key):
            if not self.fullscreen or not self.connected:
                return
            try:
                k = str(key).replace("'", "")
                if k.startswith('Key.'):
                    k = k[4:]
                if k in ('f11', 'escape'):
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
            print("[Input] Enhanced listeners started")
        except Exception as e:
            print(f"[Input] Failed to start listeners: {e}")

    def stop_input_capture(self):
        """Stop input capture"""
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
    root.configure(bg="#0a0a0a")
    
    # Set window icon and styling
    try:
        root.iconbitmap()  # Use default icon
    except:
        pass
        
    app = RemoteClientApp(root)
    
    def on_closing():
        app.disconnect()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
