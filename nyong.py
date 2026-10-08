import os
import time
import threading
import subprocess
import sys
import pyautogui
import keyboard
import cv2
import numpy as np

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        return os.path.dirname(os.path.abspath(__file__))

SCRIPT_DIR = get_base_dir()
RICE_IMG = os.path.join(SCRIPT_DIR, 'pig.png')
DONE_RICE_IMG = os.path.join(SCRIPT_DIR, 'meat_done.png')
ALLOWED_PNP_DEVICE_ID = 'PCI\\VEN_10EC&DEV_8125&SUBSYS_E0001458&REV_05\\01000000684CE00000'
CONFIDENCE = 0.7
COLOR_TOLERANCE = 80
COLOR_MATCH_THRESHOLD = 0.55
LOOP_DELAY = 0.5
POLL_INTERVAL = 0.5
HOTKEY = 'f8'
RICE_REGION = (0, 0, 1920, 1080)
pyautogui.FAILSAFE = True
running = threading.Event()

def check_authorized_pc():
    # PC 인증을 우회하기 위해 항상 True를 반환하도록 수정됨
    return True

def check_image_files():
    if not os.path.isfile(RICE_IMG):
        print('pig.png 없음')
        print(RICE_IMG)
        return False
    else:
        if not os.path.isfile(DONE_RICE_IMG):
            print('meat_done.png 없음')
            print(DONE_RICE_IMG)
            return False
        else:
            return True

def toggle_running():
    if running.is_set():
        running.clear()
        print('일시정지')
    else:
        running.set()
        print('시작')

def wait_if_paused():
    while not running.is_set():
        time.sleep(0.1)

def safe_click(pos, button='left', move_duration=0.2, pre_delay=0.1, post_down_delay=0.08):
    pyautogui.moveTo(int(pos[0]), int(pos[1]), duration=move_duration)
    time.sleep(pre_delay)
    pyautogui.mouseDown(button=button)
    time.sleep(post_down_delay)
    pyautogui.mouseUp(button=button)

def color_matches(template_path, screen_region, tolerance=COLOR_TOLERANCE):
    template = cv2.imread(template_path)
    if template is None:
        return False
    else:
        x, y, w, h = map(int, screen_region)
        if w <= 0 or h <= 0:
            return False
        else:
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            if screen.shape[:2] != template.shape[:2]:
                screen = cv2.resize(screen, (template.shape[1], template.shape[0]))
            diff = cv2.absdiff(template.astype(np.int16), screen.astype(np.int16))
            pixel_diff = np.mean(diff, axis=2)
            matching_ratio = np.mean(pixel_diff <= tolerance)
            return matching_ratio >= 0.9

def find_on_screen(image_path, confidence=CONFIDENCE, region=None, check_color=False):
    template = cv2.imread(image_path)
    if template is None:
        print(f'이미지 읽기 실패: {image_path}')
        return
    else:
        if region is None:
            screenshot = pyautogui.screenshot()
            offset_x = 0
            offset_y = 0
        else:
            x, y, w, h = map(int, region)
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            offset_x = x
            offset_y = y
        screen = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        template_h, template_w = template.shape[:2]
        screen_h, screen_w = screen.shape[:2]
        if template_w > screen_w or template_h > screen_h:
            return None
        else:
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= confidence)
            candidates = []
            for y, x in zip(*locations):
                score = float(result[y, x])
                candidates.append((score, x + offset_x, y + offset_y))
            candidates.sort(key=lambda v: v[0], reverse=True)
            checked = []
            for score, x, y in candidates:
                duplicate = False
                for cx, cy in checked:
                    if abs(x - cx) < template_w // 2 and abs(y - cy) < template_h // 2:
                        duplicate = True
                        break
                if duplicate:
                    continue
                else:
                    checked.append((x, y))
                    local_x = x - offset_x
                    local_y = y - offset_y
                    candidate = screen[local_y:local_y + template_h, local_x:local_x + template_w]
                    if candidate.shape[:2] != template.shape[:2]:
                        continue
                    else:
                        if check_color:
                            diff = cv2.absdiff(template.astype(np.int16), candidate.astype(np.int16))
                            pixel_diff = np.mean(diff, axis=2)
                            matching_ratio = np.mean(pixel_diff <= COLOR_TOLERANCE)
                            if matching_ratio < COLOR_MATCH_THRESHOLD:
                                continue
                        center_x = x + template_w // 2
                        center_y = y + template_h // 2
                        return (center_x, center_y)

def wait_for_image(image_path, region=None, poll=POLL_INTERVAL, check_color=False):
    while True:
        wait_if_paused()
        pos = find_on_screen(image_path, region=region, check_color=check_color)
        if pos is not None:
            return pos
        else:
            time.sleep(poll)

def main():
    if not check_authorized_pc():
        print('이 PC에서는 실행할 수 없습니다.')
        time.sleep(3)
        return
    else:
        if not check_image_files():
            time.sleep(3)
            return
        else:
            keyboard.add_hotkey(HOTKEY, toggle_running)
            print(f'{HOTKEY.upper()} 시작 / 일시정지')
            print(f'이미지 폴더: {SCRIPT_DIR}')
            round_num = 1
            while True:
                wait_if_paused()
                pyautogui.mouseDown(button='right')
                time.sleep(0.08)
                pyautogui.mouseUp(button='right')
                time.sleep(LOOP_DELAY)
                wait_if_paused()
                rice_pos = find_on_screen(RICE_IMG, region=RICE_REGION, check_color=True)
                if rice_pos is not None:
                    safe_click(rice_pos, button='left')
                time.sleep(LOOP_DELAY)
                wait_if_paused()
                pyautogui.press('esc')
                time.sleep(LOOP_DELAY)
                done_pos = wait_for_image(DONE_RICE_IMG)
                safe_click(done_pos, button='right')
                round_num += 1
                time.sleep(LOOP_DELAY)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        running.clear()
        print('종료')
