# remote_host_server.py - FINAL CRASH-PROOF SERVER
# Fixes:
# 1. Socket closed while screen thread still runs → [WinError 10038]
# 2. Partial/merged TCP packets → "invalid literal for int()"

import socket
import threading
import struct
import pickle
import cv2
import numpy as np
from mss import mss
import pyautogui
import time

# Disable failsafe (optional, be careful!)
pyautogui.FAILSAFE = False

HOST = '0.0.0.0'
PORT = 65432

# Thread-safe flag to signal screen thread to stop
class Connection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.active = True  # shared flag

def safe_move(x, y):
    try:
        current_x, current_y = pyautogui.position()
        if abs(current_x - x) > 2 or abs(current_y - y) > 2:
            pyautogui.moveTo(x, y)
    except Exception as e:
        print(f"[Server] Mouse move error: {e}")

def safe_click(button, pressed):
    try:
        if pressed:
            pyautogui.mouseDown(button=button)
        else:
            pyautogui.mouseUp(button=button)
    except Exception as e:
        print(f"[Server] Click error: {e}")

def safe_scroll(dx, dy):
    try:
        pyautogui.scroll(dy)
    except Exception as e:
        print(f"[Server] Scroll error: {e}")

def safe_key(key, action):
    try:
        if action == 'press':
            pyautogui.keyDown(key)
        elif action == 'release':
            pyautogui.keyUp(key)
    except Exception as e:
        print(f"[Server] Key {action} error for '{key}': {e}")

def capture_screen(conn):
    """Continuously capture and send screen — respects conn.active flag"""
    with mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        while conn.active:
            try:
                img = sct.grab(monitor)
                img_np = np.array(img)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
                _, buffer = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                data = pickle.dumps(buffer, 0)
                size = len(data)
                # Check flag before sending
                if not conn.active:
                    break
                conn.sock.sendall(struct.pack(">L", size) + data)
            except Exception as e:
                print(f"[Server Screen] Error: {e}")
                break
    print("[Server Screen] Thread exited cleanly")

def handle_input(conn):
    """Receive and execute mouse/keyboard commands — handles TCP stream correctly"""
    buffer = ""
    while conn.active:
        try:
            data = conn.sock.recv(1024).decode('utf-8')
            if not data:
                print("[Server Input] Client disconnected (empty data)")
                break

            buffer += data

            # Process all complete messages in buffer
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
                        print(f"[Server Input] Invalid MOVE coords: {line} | {e}")

                elif cmd == 'CLICK' and len(parts) >= 3:
                    button = parts[1]
                    pressed = parts[2] == 'True'
                    safe_click(button, pressed)

                elif cmd == 'SCROLL' and len(parts) >= 3:
                    try:
                        dx, dy = int(parts[1]), int(parts[2])
                        safe_scroll(dx, dy)
                    except ValueError as e:
                        print(f"[Server Input] Invalid SCROLL values: {line} | {e}")

                elif cmd == 'KEY' and len(parts) >= 3:
                    key = parts[1]
                    action = parts[2]
                    safe_key(key, action)

                else:
                    print(f"[Server Input] Unknown or malformed command: {line}")

        except Exception as e:
            print(f"[Server Input] Error: {e}")
            break

    # Signal screen thread to stop
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

                # Start screen streaming thread
                screen_thread = threading.Thread(target=capture_screen, args=(conn,), daemon=True)
                screen_thread.start()

                # Handle input on main thread
                handle_input(conn)

                # Cleanup
                conn.active = False
                client_sock.close()
                print(f"🔚 Connection with {addr} closed")

            except Exception as e:
                print(f"[Server Main] Accept error: {e}")

if __name__ == "__main__":
    start_server()
