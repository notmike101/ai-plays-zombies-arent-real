"""Test fake focus + cursor on inst2."""
import sys, time
sys.path.insert(0, r'D:\zar-scratch\scripts')
from game_drive import *
import ctypes

hwnd = 464452
user32 = ctypes.windll.user32

WA_INACTIVE, WA_ACTIVE = 0, 1

def fake_focus():
    user32.PostMessageW(hwnd, 0x0018, WA_ACTIVE, 0)          # WM_ACTIVATE
    user32.PostMessageW(hwnd, 0x0007, 0, 0)                  # WM_SETFOCUS
    print('fake focus sent')

def fake_unfocus():
    user32.PostMessageW(hwnd, 0x0018, WA_INACTIVE, 0)        # WM_ACTIVATE
    user32.PostMessageW(hwnd, 0x0008, 0, 0)                  # WM_KILLFOCUS
    print('fake unfocus sent')

if __name__ == '__main__':
    # 1. fake focus
    fake_focus()
    time.sleep(0.3)
    # 2. move game cursor to client (200,200) via WM_MOUSEMOVE
    move(hwnd, 200, 200)
    time.sleep(0.5)
    grab(hwnd).save(r'D:\zar-scratch\analysis\fakefocus1.png')
    time.sleep(4)
    grab(hwnd).save(r'D:\zar-scratch\analysis\fakefocus2.png')
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(r'D:\zar-scratch\analysis\fakefocus1.png').convert('RGB'), dtype=int)
    b = np.array(Image.open(r'D:\zar-scratch\analysis\fakefocus2.png').convert('RGB'), dtype=int)
    d = np.abs(a - b).sum(axis=2)
    print('moving pixels after fake focus:', (d > 10).sum())
