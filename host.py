# remote_host_server.py - Run this on the target machine you want to control

import socket
import threading
import struct
import pickle
import cv2
import numpy as np
from mss import mss
from pynput import mouse, keyboard
import pyautogui

# Disable failsafe (optional, be careful!)
pyautogui.FAILSAFE = False

HOST = '0.0.0.0'
PORT = 65432

def capture_screen(conn):
    """Continuously capture and send screen"""
    with mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        while True:
            try:
                # Capture screen
                img = sct.grab(monitor)
                # Convert to numpy (BGR for OpenCV)
                img_np = np.array(img)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
                data = pickle.dumps(buffer, 0)
                size = len(data)
                # Send size first, then data
                conn.sendall(struct.pack(">L", size) + data)
            except Exception as e:
                print(f"[Screen] Connection closed: {e}")
                break

def handle_input(conn):
    """Receive and execute mouse/keyboard commands"""
    while True:
        try:
            # Expect command format: "TYPE|ARGS"
            data = conn.recv(1024).decode('utf-8')
            if not data:
                break
            parts = data.split('|')
            cmd = parts[0]

            if cmd == 'MOVE':
                x, y = int(parts[1]), int(parts[2])
                pyautogui.moveTo(x, y)

            elif cmd == 'CLICK':
                button = parts[1]
                pressed = parts[2] == 'True'
                btn = mouse.Button.left if button == 'left' else mouse.Button.right
                if pressed:
                    pyautogui.mouseDown(button=button)
                else:
                    pyautogui.mouseUp(button=button)

            elif cmd == 'SCROLL':
                dx, dy = int(parts[1]), int(parts[2])
                pyautogui.scroll(dy)

            elif cmd == 'KEY':
                key = parts[1]
                action = parts[2]
                if action == 'press':
                    pyautogui.keyDown(key)
                elif action == 'release':
                    pyautogui.keyUp(key)

        except Exception as e:
            print(f"[Input] Error: {e}")
            break

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}...")

        while True:
            conn, addr = s.accept()
            print(f"Connected by {addr}")
            # Start screen streaming thread
            screen_thread = threading.Thread(target=capture_screen, args=(conn,), daemon=True)
            screen_thread.start()
            # Handle input on main thread
            handle_input(conn)
            conn.close()

if __name__ == "__main__":
    start_server()
