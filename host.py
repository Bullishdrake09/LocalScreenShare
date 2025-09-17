# remote_host_server.py — ULTRA LOW-LATENCY VERSION
# Uses WinAPI SetCursorPos for instant mouse movement

import socket
import threading
import struct
import pickle
import cv2
import numpy as np
from mss import mss
import time

# 👇 WINAPI for instant mouse movement (Windows only)
import ctypes
from ctypes import wintypes
user32 = ctypes.WinDLL('user32', use_last_error=True)
SetCursorPos = user32.SetCursorPos
SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]
SetCursorPos.restype = wintypes.BOOL

# Optional: Show cursor if hidden
ShowCursor = user32.ShowCursor
ShowCursor.argtypes = [wintypes.BOOL]

HOST = '0.0.0.0'
PORT = 65432

class Connection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.active = True

def safe_move(x, y):
    try:
        # ⚡ INSTANT cursor move via WinAPI
        SetCursorPos(int(x), int(y))
    except Exception as e:
        print(f"[Server] Mouse move error: {e}")

def safe_click(button, pressed):
    try:
        # Still use pyautogui for clicks (or replace with WinAPI mouse_event if needed)
        import pyautogui
        if pressed:
            pyautogui.mouseDown(button=button)
        else:
            pyautogui.mouseUp(button=button)
    except Exception as e:
        print(f"[Server] Click error: {e}")

def safe_scroll(dx, dy):
    try:
        import pyautogui
        pyautogui.scroll(dy)
    except Exception as e:
        print(f"[Server] Scroll error: {e}")

def safe_key(key, action):
    try:
        import pyautogui
        if action == 'press':
            pyautogui.keyDown(key)
        elif action == 'release':
            pyautogui.keyUp(key)
    except Exception as e:
        print(f"[Server] Key {action} error for '{key}': {e}")

def capture_screen(conn):
    with mss() as sct:
        monitor = sct.monitors[1]
        while conn.active:
            try:
                img = sct.grab(monitor)
                img_np = np.array(img)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
                # 🔥 Lower quality = faster encode + less bandwidth
                _, buffer = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 50])
                data = pickle.dumps(buffer, 0)
                size = len(data)
                if not conn.active:
                    break
                conn.sock.sendall(struct.pack(">L", size) + data)
            except Exception as e:
                print(f"[Server Screen] Error: {e}")
                break
    print("[Server Screen] Thread exited cleanly")

def handle_input(conn):
    buffer = ""
    while conn.active:
        try:
            data = conn.sock.recv(1024).decode('utf-8')
            if not 
                break

            buffer += data
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue

                parts = line.split('|')
                cmd = parts[0]

                if cmd == 'MOVE' and len(parts) >= 3:
                    try:
                        x, y = int(parts[1]), int(parts[2])
                        safe_move(x, y)
                    except ValueError as e:
                        print(f"[Server Input] Invalid MOVE: {line}")

                elif cmd == 'CLICK' and len(parts) >= 3:
                    button = parts[1]
                    pressed = parts[2] == 'True'
                    safe_click(button, pressed)

                elif cmd == 'SCROLL' and len(parts) >= 3:
                    try:
                        dx, dy = int(parts[1]), int(parts[2])
                        safe_scroll(dx, dy)
                    except ValueError as e:
                        print(f"[Server Input] Invalid SCROLL: {line}")

                elif cmd == 'KEY' and len(parts) >= 3:
                    key = parts[1]
                    action = parts[2]
                    safe_key(key, action)

        except Exception as e:
            print(f"[Server Input] Error: {e}")
            break

    conn.active = False
    print("[Server Input] Thread exited cleanly")

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"✅ Server listening on {HOST}:{PORT}...")

        while True:
            try:
                client_sock, addr = s.accept()
                print(f"🔗 Connected by {addr}")
                conn = Connection(client_sock, addr)

                screen_thread = threading.Thread(target=capture_screen, args=(conn,), daemon=True)
                screen_thread.start()

                handle_input(conn)

                conn.active = False
                client_sock.close()
                print(f"🔚 Connection with {addr} closed")

            except Exception as e:
                print(f"[Server Main] Error: {e}")

if __name__ == "__main__":
    # Show cursor in case it's hidden
    ShowCursor(True)
    start_server()
