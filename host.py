# remote_host_server_enhanced.py — ULTRA LOW-LATENCY WITH MOUSE SYNC
# Enhanced with mouse position tracking and cursor state management

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
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

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

# Get cursor info
GetCursorInfo = user32.GetCursorInfo
class CURSORINFO(Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("hCursor", wintypes.HANDLE),
                ("ptScreenPos", POINT)]

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
        self.last_ping_time = time.time()

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

def get_cursor_info():
    """Get cursor visibility and position info"""
    try:
        cursor_info = CURSORINFO()
        cursor_info.cbSize = ctypes.sizeof(CURSORINFO)
        if GetCursorInfo(ctypes.byref(cursor_info)):
            return {
                'visible': cursor_info.flags != 0,
                'x': cursor_info.ptScreenPos.x,
                'y': cursor_info.ptScreenPos.y
            }
    except Exception:
        pass
    return {'visible': True, 'x': 0, 'y': 0}

def send_mouse_info(conn):
    """Send mouse position and visibility info to client"""
    while conn.active:
        try:
            cursor_info = get_cursor_info()
            mouse_data = {
                'type': 'MOUSE_INFO',
                'x': cursor_info['x'],
                'y': cursor_info['y'],
                'visible': cursor_info['visible'],
                'controlling': conn.remote_controlling,
                'timestamp': time.time()
            }
            
            # Only send if position changed or state changed
            current_pos = (cursor_info['x'], cursor_info['y'])
            if (current_pos != conn.last_mouse_pos or 
                cursor_info['visible'] != conn.mouse_visible):
                
                conn.last_mouse_pos = current_pos
                conn.mouse_visible = cursor_info['visible']
                
                data = pickle.dumps(mouse_data)
                size = len(data)
                try:
                    conn.sock.sendall(b'MOUSE' + struct.pack(">L", size) + data)
                except:
                    break
                    
            time.sleep(0.008)  # ~120 Hz mouse updates
            
        except Exception as e:
            print(f"[Server Mouse] Error: {e}")
            break

def capture_screen(conn):
    """Enhanced screen capture with better compression"""
    with mss() as sct:
        monitor = sct.monitors[1]
        frame_count = 0
        last_quality_adjust = time.time()
        current_quality = 60  # Start with medium quality
        
        while conn.active:
            try:
                start_time = time.time()
                
                img = sct.grab(monitor)
                img_np = np.array(img)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
                
                # Dynamic quality adjustment based on performance
                if time.time() - last_quality_adjust > 2.0:
                    encode_time = time.time()
                    _, buffer = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, current_quality])
                    encode_duration = time.time() - encode_time
                    
                    if encode_duration > 0.020:  # If encoding takes >20ms
                        current_quality = max(30, current_quality - 10)
                    elif encode_duration < 0.010:  # If encoding is fast
                        current_quality = min(80, current_quality + 5)
                    
                    last_quality_adjust = time.time()
                else:
                    _, buffer = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, current_quality])
                
                screen_data = {
                    'type': 'SCREEN_FRAME',
                    'frame': buffer,
                    'width': monitor['width'],
                    'height': monitor['height'],
                    'quality': current_quality,
                    'timestamp': time.time()
                }
                
                data = pickle.dumps(screen_data, 0)
                size = len(data)
                
                if not conn.active:
                    break
                    
                conn.sock.sendall(b'SCRN' + struct.pack(">L", size) + data)
                
                # Adaptive frame rate
                frame_time = time.time() - start_time
                target_fps = 60 if conn.remote_controlling else 30
                sleep_time = max(0, (1.0 / target_fps) - frame_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
                frame_count += 1
                
            except Exception as e:
                print(f"[Server Screen] Error: {e}")
                break
                
    print("[Server Screen] Thread exited cleanly")

def handle_input(conn):
    """Enhanced input handling with better parsing"""
    buffer = ""
    conn.remote_controlling = False
    last_activity = time.time()
    
    while conn.active:
        try:
            data = conn.sock.recv(4096).decode('utf-8')
            if not data:
                print("[Server Input] Client disconnected (empty data)")
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
                last_activity = current_time
                conn.remote_controlling = True

                if cmd == 'MOVE' and len(parts) >= 3:
                    try:
                        x, y = int(parts[1]), int(parts[2])
                        if safe_move(x, y):
                            conn.last_ping_time = current_time
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
                    # Respond to ping for latency measurement
                    try:
                        conn.sock.sendall(b'PONG\n')
                        conn.last_ping_time = current_time
                    except:
                        break

            # Check for inactivity (no input for 2 seconds = not controlling)
            if current_time - last_activity > 2.0:
                conn.remote_controlling = False

        except Exception as e:
            print(f"[Server Input] Error: {e}")
            break

    conn.active = False
    print("[Server Input] Thread exited cleanly")

def start_server():
    """Enhanced server with multiple service threads"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm
        s.bind((HOST, PORT))
        s.listen()
        print(f"✅ Enhanced Server listening on {HOST}:{PORT}...")

        while True:
            try:
                client_sock, addr = s.accept()
                client_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
                print(f"🔗 Connected by {addr}")
                conn = Connection(client_sock, addr)

                # Start multiple service threads
                screen_thread = threading.Thread(target=capture_screen, args=(conn,), daemon=True)
                mouse_thread = threading.Thread(target=send_mouse_info, args=(conn,), daemon=True)
                
                screen_thread.start()
                mouse_thread.start()

                # Handle input in main thread
                handle_input(conn)

                conn.active = False
                client_sock.close()
                print(f"🔚 Connection with {addr} closed")

            except Exception as e:
                print(f"[Server Main] Error: {e}")

if __name__ == "__main__":
    # Ensure cursor is visible at start
    ShowCursor(True)
    print("🎯 Enhanced Remote Desktop Server")
    print("Features: Mouse Sync, Dynamic Quality, Low Latency")
    start_server()
