# remote_host_server_enhanced.py — FIXED VERSION WITH MOUSE SYNC
# Simplified protocol with working screen transmission and mouse synchronization

import socket
import threading
import struct
import pickle
import cv2
import numpy as np
from mss import mss
import time

# WinAPI for instant mouse movement and cursor management
import ctypes
from ctypes import wintypes, Structure
user32 = ctypes.WinDLL('user32', use_last_error=True)

# Mouse position and cursor functions
SetCursorPos = user32.SetCursorPos
SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]
SetCursorPos.restype = wintypes.BOOL

GetCursorPos = user32.GetCursorPos
ShowCursor = user32.ShowCursor
ShowCursor.argtypes = [wintypes.BOOL]

# Cursor position structure
class POINT(Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

HOST = '0.0.0.0'
PORT = 65432

class Connection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.active = True
        self.last_mouse_pos = (0, 0)
        self.mouse_visible = True
        self.remote_controlling = False

def safe_move(x, y):
    try:
        SetCursorPos(int(x), int(y))
        return True
    except Exception as e:
        print(f"[Server] Mouse move error: {e}")
        return False

def safe_click(button, pressed):
    try:
        import pyautogui
        if pressed:
            pyautogui.mouseDown(button=button)
        else:
            pyautogui.mouseUp(button=button)
        return True
    except Exception as e:
        print(f"[Server] Click error: {e}")
        return False

def safe_scroll(dx, dy):
    try:
        import pyautogui
        pyautogui.scroll(dy)
        return True
    except Exception as e:
        print(f"[Server] Scroll error: {e}")
        return False

def safe_key(key, action):
    try:
        import pyautogui
        if action == 'press':
            pyautogui.keyDown(key)
        elif action == 'release':
            pyautogui.keyUp(key)
        return True
    except Exception as e:
        print(f"[Server] Key {action} error for '{key}': {e}")
        return False

def get_cursor_position():
    """Get current cursor position"""
    try:
        point = POINT()
        if GetCursorPos(ctypes.byref(point)):
            return (point.x, point.y)
    except Exception:
        pass
    return (0, 0)

def capture_screen_and_mouse(conn):
    """Combined screen capture and mouse info sender"""
    with mss() as sct:
        monitor = sct.monitors[1]
        frame_count = 0
        last_mouse_send = 0
        
        while conn.active:
            try:
                current_time = time.time()
                
                # Capture screen
                img = sct.grab(monitor)
                img_np = np.array(img)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
                
                # Compress image
                quality = 55 if conn.remote_controlling else 45
                _, buffer = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
                
                # Get mouse position
                mouse_pos = get_cursor_position()
                
                # Create combined data packet
                packet_data = {
                    'screen': buffer,
                    'mouse_x': mouse_pos[0],
                    'mouse_y': mouse_pos[1],
                    'mouse_visible': True,  # Simplified - always visible for now
                    'controlling': conn.remote_controlling,
                    'screen_width': monitor['width'],
                    'screen_height': monitor['height'],
                    'timestamp': current_time
                }
                
                # Send data
                data = pickle.dumps(packet_data, 0)
                size = len(data)
                
                if not conn.active:
                    break
                    
                conn.sock.sendall(struct.pack(">L", size) + data)
                
                # Frame rate control
                frame_time = time.time() - current_time
                target_fps = 45 if conn.remote_controlling else 25
                sleep_time = max(0, (1.0 / target_fps) - frame_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
                frame_count += 1
                
            except Exception as e:
                print(f"[Server Screen] Error: {e}")
                break
                
    print("[Server Screen] Thread exited cleanly")

def handle_input(conn):
    """Enhanced input handling"""
    buffer = ""
    conn.remote_controlling = False
    last_activity = time.time()
    
    while conn.active:
        try:
            data = conn.sock.recv(4096).decode('utf-8')
            if not data:
                print("[Server Input] Client disconnected")
                break

            buffer += data
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                if not line:
                    continue

                parts = line.split('|')
                cmd = parts[0]
                current_time = time.time()
                
                # Update activity tracking
                if cmd in ['MOVE', 'CLICK', 'SCROLL', 'KEY']:
                    last_activity = current_time
                    conn.remote_controlling = True

                if cmd == 'MOVE' and len(parts) >= 3:
                    try:
                        x, y = int(parts[1]), int(parts[2])
                        safe_move(x, y)
                    except ValueError:
                        print(f"[Server Input] Invalid MOVE: {line}")

                elif cmd == 'CLICK' and len(parts) >= 3:
                    button = parts[1]
                    pressed = parts[2] == 'True'
                    safe_click(button, pressed)

                elif cmd == 'SCROLL' and len(parts) >= 3:
                    try:
                        dx, dy = int(parts[1]), int(parts[2])
                        safe_scroll(dx, dy)
                    except ValueError:
                        print(f"[Server Input] Invalid SCROLL: {line}")

                elif cmd == 'KEY' and len(parts) >= 3:
                    key = parts[1]
                    action = parts[2]
                    safe_key(key, action)
                    
                elif cmd == 'PING':
                    # Respond to ping
                    try:
                        conn.sock.sendall(b'PONG\n')
                    except:
                        break

            # Check for inactivity
            if current_time - last_activity > 2.0:
                conn.remote_controlling = False

        except Exception as e:
            print(f"[Server Input] Error: {e}")
            break

    conn.active = False
    print("[Server Input] Thread exited cleanly")

def start_server():
    """Start the enhanced server"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"✅ Enhanced Server listening on {HOST}:{PORT}...")
        print("Features: Mouse Sync, Dynamic Quality, Auto Cursor Management")

        while True:
            try:
                client_sock, addr = s.accept()
                client_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
                print(f"🔗 Connected by {addr}")
                conn = Connection(client_sock, addr)

                # Start service threads
                screen_thread = threading.Thread(target=capture_screen_and_mouse, args=(conn,), daemon=True)
                screen_thread.start()

                # Handle input in main connection thread
                handle_input(conn)

                conn.active = False
                client_sock.close()
                print(f"🔚 Connection with {addr} closed")

            except Exception as e:
                print(f"[Server Main] Error: {e}")

if __name__ == "__main__":
    # Ensure cursor is visible at start
    ShowCursor(True)
    print("🎯 Enhanced Remote Desktop Server - FIXED VERSION")
    start_server()
