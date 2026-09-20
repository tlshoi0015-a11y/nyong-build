import os
import sys
import subprocess
import time
import threading
import random
import cv2
import numpy as np
import pyautogui
import keyboard

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

RICE_IMG = 'pig.png'
DONE_RICE_IMG = 'meat_done.png'
COLOR_TOLERANCE = 30
COLOR_MATCH_THRESHOLD = 0.8
FAILSAFE = False
POLL_INTERVAL = 0.1
LOOP_DELAY = 0.5
SCRIPT_DIR = get_base_dir()

def check_image_files():
    if not os.path.isfile(os.path.join(SCRIPT_DIR, RICE_IMG)):
        print(f"이미지 파일 없음: {RICE_IMG}")
        return False
    if not os.path.isfile(os.path.join(SCRIPT_DIR, DONE_RICE_IMG)):
        print(f"이미지 파일 없음: {DONE_RICE_IMG}")
        return False
    return True

running = threading.Event()

def toggle_running():
    if running.is_set():
        running.clear()
        print("일시정지")
    else:
        running.set()
        print("시작")

def wait_if_paused():
    while not running.is_set():
        time.sleep(0.1)

def safe_click(pos, duration=0.1, button='left', pre_delay=0.05, post_down_delay=0.05):
    pyautogui.moveTo(pos[0], pos[1], duration=duration)
    time.sleep(pre_delay)
    pyautogui.mouseDown(button=button)
    time.sleep(post_down_delay)
    pyautogui.mouseUp(button=button)

def color_matches(template_path, screen_region, tolerance=30):
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if template is None:
        return False
    
    x, y, w, h = screen_region
    screen = pyautogui.screenshot(region=(x, y, w, h))
    screen = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
    
    if screen.shape != template.shape:
        template = cv2.resize(template, (w, h))
        
    diff = cv2.absdiff(screen, template)
    diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    mean_diff = np.mean(diff)
    
    return mean_diff <= tolerance

def find_on_screen(image_path, confidence=0.8, check_color=False, tolerance=30):
    if not os.path.exists(image_path):
        print(f"이미지 파일 읽기 실패: {image_path}")
        return None
        
    template = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if template is None:
        print(f"이미지 로드 실패: {image_path}")
        return None
        
    screen = pyautogui.screenshot()
    screen = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
    
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= confidence)
    
    template_h, template_w, _ = template.shape
    candidates = []
    
    for pt in zip(*locations[::-1]):
        score = result[pt[1], pt[0]]
        candidates.append((pt[0], pt[1], score))
        
    candidates.sort(key=lambda x: x[2], reverse=True)
    checked = set()
    
    for cx, cy, score in candidates:
        duplicate = False
        for ccx, ccy in checked:
            if abs(cx - ccx) < template_w and abs(cy - ccy) < template_h:
                duplicate = True
                break
        if duplicate:
            continue
            
        checked.add((cx, cy))
        center_x = cx + template_w // 2
        center_y = cy + template_h // 2
        
        if check_color:
            region = (cx, cy, template_w, template_h)
            if not color_matches(image_path, region, tolerance):
                continue
                
        return (center_x, center_y)
    return None

def wait_for_image(image_path, confidence=0.8):
    while True:
        wait_if_paused()
        pos = find_on_screen(image_path, confidence)
        if pos:
            return pos
        time.sleep(0.5)

def main():
    if not check_image_files():
        print("필수 이미지 폴더: 현재 디렉토리 확인 필요")
        return
        
    keyboard.add_hotkey('F8', toggle_running)
    print("시작 / 일시정지: F8, 종료: ESC")
    
    running.clear()
    
    while True:
        wait_if_paused()
        
        rice_pos = find_on_screen(os.path.join(SCRIPT_DIR, RICE_IMG), confidence=0.8)
        if rice_pos:
            safe_click(rice_pos, button='right')
            time.sleep(0.7)
            
        done_pos = find_on_screen(os.path.join(SCRIPT_DIR, DONE_RICE_IMG), confidence=0.5)
        if done_pos:
            safe_click(done_pos, button='left')
            time.sleep(0.5)
            
        time.sleep(0.1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
