import os
import sys
import time
import threading
import random
import cv2
import numpy as np
import mss
import pyautogui
import keyboard
import win32api
import win32con
import ctypes

# ==================== 고성능 타이머 및 SendInput 설정 (다지기용) ====================
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

PUL = ctypes.POINTER(ctypes.c_ulong)
class MouseInput(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', PUL)]

class Input_I(ctypes.Union):
    _fields_ = [('mi', MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('ii', Input_I)]

def send_input_left_click():
    extra = ctypes.c_ulong(0)
    ii_down = Input_I()
    ii_down.mi = MouseInput(0, 0, 0, win32con.MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    x_down = Input(win32con.INPUT_MOUSE, ii_down)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x_down), ctypes.sizeof(x_down))
    
    ii_up = Input_I()
    ii_up.mi = MouseInput(0, 0, 0, win32con.MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    x_up = Input(win32con.INPUT_MOUSE, ii_up)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x_up), ctypes.sizeof(x_up))

# ==================== 전역 변수 및 설정 ====================
is_running = False
is_terminated = False
current_cps = 65

threshold_item = 0.80
threshold_desc = 0.80
threshold_ui = 0.65
threshold_finish = 0.50

REQUIRED_IMAGES = [
    'target2.png', 't2.png', 'bowl.png', 'sw2.png', 
    'f.png', 'sink.png', 'cutting_board.png', 'lobby.png',
    'pig.png', 'meat_done.png'
]

def check_images():
    missing = [img for img in REQUIRED_IMAGES if not os.path.exists(img)]
    if missing:
        print(f"[경고] 다음 이미지 파일이 누락되었습니다: {missing}")

def capture_screen():
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def find_image(template_name, threshold=0.8):
    if not os.path.exists(template_name):
        return None
    screen = capture_screen()
    template = cv2.imread(template_name, cv2.IMREAD_COLOR)
    if template is None:
        return None
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        h, w, _ = template.shape
        return (max_loc[0] + w // 2, max_loc[1] + h // 2)
    return None

def check_image_exists(template_name, threshold=0.8):
    if not os.path.exists(template_name):
        return False
    screen = capture_screen()
    template = cv2.imread(template_name, cv2.IMREAD_COLOR)
    if template is None:
        return False
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val >= threshold

def human_right_click():
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.1, 0.2))
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

# ==================== 고기(pig) 관련 원본 코드 (코드 수정 없음) ====================
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
        return False
    if not os.path.isfile(os.path.join(SCRIPT_DIR, DONE_RICE_IMG)):
        return False
    return True

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
        return None
        
    template = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if template is None:
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

def meat_macro_loop():
    while not is_terminated:
        if not is_running:
            time.sleep(0.1)
            continue
            
        rice_pos = find_on_screen(os.path.join(SCRIPT_DIR, RICE_IMG), confidence=0.8)
        if rice_pos:
            safe_click(rice_pos, button='right')
            time.sleep(0.7)
            
        done_pos = find_on_screen(os.path.join(SCRIPT_DIR, DONE_RICE_IMG), confidence=0.5)
        if done_pos:
            safe_click(done_pos, button='left')
            time.sleep(0.5)
            
        time.sleep(0.1)

# ==================== 연타 전용 백그라운드 스레드 클래스 ====================
class ClickerThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.active = threading.Event()

    def run(self):
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass
        
        while not is_terminated:
            self.active.wait() 
            next_click = time.perf_counter()
            
            while self.active.is_set() and not is_terminated:
                if current_cps <= 0:
                    time.sleep(0.01)
                    continue

                now = time.perf_counter()
                interval = 1.0 / current_cps

                if now >= next_click:
                    send_input_left_click()
                    next_click += interval
                    if next_click < now - interval:
                        next_click = now + interval
                else:
                    time.sleep(0.0001)

clicker = ClickerThread()
clicker.start()

# ==================== 메인 다지기 매크로 루프 ====================
def macro_loop():
    global is_running, is_terminated, current_cps
    print("[안내] 매크로 대기 중... (F1: 시작, F2: 종료)")

    while not is_terminated:
        if not is_running:
            time.sleep(0.1)
            continue

        ui_opened = False
        for retry in range(1, 6):
            if not is_running or is_terminated: break
            print(f"[동작] 도마/싱크대 열기 시도 ({retry}/5)...")
            human_right_click()
            
            start_t = time.time()
            while time.time() - start_t < 3.0:
                if not is_running or is_terminated: break
                if check_image_exists('cutting_board.png', threshold_ui) or check_image_exists('sink.png', threshold_ui):
                    ui_opened = True
                    break
                time.sleep(0.1)
            if ui_opened: break

        if not ui_opened:
            is_running = False
            continue

        target_pos = None
        search_t = time.time()
        while is_running and not is_terminated:
            target_pos = find_image('target2.png', threshold_item) or find_image('t2.png', threshold_desc)
            if target_pos: break
            if time.time() - search_t > 5.0:
                is_running = False
                break
            time.sleep(0.1)

        if not is_running or not target_pos: continue

        win32api.SetCursorPos(target_pos)
        time.sleep(0.05)
        human_right_click()
        print("[동작] 작물 우클릭 완료. 0.7초 대기 중...")
        time.sleep(0.7)

        bowl_t = time.time()
        while check_image_exists('bowl.png', 0.80):
            if not is_running or is_terminated: break
            if time.time() - bowl_t > 0.7: break
            time.sleep(0.05)

        if not is_running: continue

        sw_pos = find_image('sw2.png', 0.80)
        if sw_pos:
            win32api.SetCursorPos(sw_pos)
        else:
            continue

        print("[진행] 고속 연타 및 f.png 감시 시작...")
        clicker.active.set()

        is_finished = False
        while is_running and not is_terminated:
            if check_image_exists('f.png', threshold_finish):
                print(f"[완료] 조리 완료 이미지(f.png) 감지! (정확도: {int(threshold_finish*100)}%)")
                is_finished = True
                break
            time.sleep(0.05)

        clicker.active.clear()

        if is_finished:
            print("[대기] f 감지 완료 후 0.5초 안정화 대기...")
            time.sleep(0.5)
            continue

# ==================== 단축키 및 진입점 ====================
if __name__ == '__main__':
    check_images()

    def start_macro():
        global is_running
        if not is_running:
            is_running = True
            print("\n[상태] 매크로가 시작되었습니다. (F1: 시작 / F2: 종료)")

    def terminate_program():
        global is_running, is_terminated
        is_running = False
        is_terminated = True
        clicker.active.set()
        print("\n[종료] 프로그램을 완전히 종료합니다.")
        os._exit(0)

    keyboard.add_hotkey('F1', start_macro)
    keyboard.add_hotkey('F2', terminate_program)

    # 두 가지 매크로 루프를 각각 백그라운드 스레드로 동시 구동
    threading.Thread(target=macro_loop, daemon=True).start()
    threading.Thread(target=meat_macro_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        terminate_program()
