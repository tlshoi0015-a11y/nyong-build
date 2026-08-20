import os
import time
import threading
import random
import cv2
import numpy as np
import mss
import keyboard
import win32api
import win32con
import ctypes

# ==================== 설정 및 전역 변수 ====================
is_running = False
is_terminated = False

# 인식 정확도 설정
threshold_item = 0.80   
threshold_desc = 0.80   
threshold_ui = 0.65     
threshold_finish = 0.80 

# 연타 속도 (CPS) 설정
current_cps = 65

# 필수 이미지 파일 목록
REQUIRED_IMAGES = [
    'target2.png', 't2.png', 'bowl.png', 'sw2.png', 
    'f.png', 'sink.png', 'cutting_board.png', 'lobby.png'
]

# ==================== 고성능 타이머 및 SendInput 설정 ====================
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

# ==================== 이미지 및 화면 함수 ====================
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

# ==================== 마우스 조작 함수 ====================
def human_right_click():
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.1, 0.2))
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

# ==================== 단축키 메뉴 ====================
def adjust_threshold_menu():
    global threshold_item, threshold_desc, threshold_ui
    print("\n" + "="*40)
    print(f" [정확도 설정] 본체: {int(threshold_item*100)}% | 설명탭: {int(threshold_desc*100)}% | UI: {int(threshold_ui*100)}%")
    print("="*40)
    choice = input("조절할 번호 입력 (1, 2, 3 / 취소는 엔터): ").strip()
    if choice in ['1', '2', '3']:
        print(" -> [Page Up]: +5% | [Page Down]: -5% | 그 외 키: 종료")
        while True:
            event = keyboard.read_event(suppress=True)
            if event.event_type == keyboard.KEY_DOWN:
                if event.name == 'page up':
                    if choice == '1': threshold_item = min(1.0, threshold_item + 0.05)
                    elif choice == '2': threshold_desc = min(1.0, threshold_desc + 0.05)
                    else: threshold_ui = min(1.0, threshold_ui + 0.05)
                    print(f"현재 값 변경됨")
                elif event.name == 'page down':
                    if choice == '1': threshold_item = max(0.1, threshold_item - 0.05)
                    elif choice == '2': threshold_desc = max(0.1, threshold_desc - 0.05)
                    else: threshold_ui = max(0.1, threshold_ui - 0.05)
                    print(f"현재 값 변경됨")
                else:
                    break

def decrease_cps():
    global current_cps
    current_cps = max(10, current_cps - 1)
    print(f"[속도] CPS 낮춤: {current_cps}")

def increase_cps():
    global current_cps
    current_cps = min(100, current_cps + 1)
    print(f"[속도] CPS 높임: {current_cps}")

# ==================== 메인 매크로 루프 ====================
def macro_loop():
    global is_running, threshold_item, threshold_desc, threshold_ui, threshold_finish, current_cps
    print("[안내] 매크로 대기 중... (F8: 시작/정지)")

    while not is_terminated:
        if not is_running:
            time.sleep(0.1)
            continue

        # 1 & 2. 도마/싱크대 열기
        ui_opened = False
        for retry in range(1, 4):
            if not is_running or is_terminated: break
            print(f"[동작] 도마/싱크대 열기 시도 ({retry}/3)...")
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

        # 3. 작물 탐색
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

        # 4. 우클릭 및 1초 대기
        win32api.SetCursorPos(target_pos)
        time.sleep(0.05)
        human_right_click()
        print("[동작] 1.0초 대기 중...")
        time.sleep(1.0)

        # 5. 그릇 소멸 검증
        bowl_t = time.time()
        while check_image_exists('bowl.png', 0.80):
            if not is_running or is_terminated: break
            if time.time() - bowl_t > 2.0: break
            time.sleep(0.1)

        if not is_running: continue

        # 6. 조리 연타 및 완료 감지 (속도 저하 없는 고성능 동기 루프)
        sw_pos = find_image('sw2.png', 0.80)
        if sw_pos:
            win32api.SetCursorPos(sw_pos)
        else:
            continue

        print("[진행] 초고속 연타 시작...")
        next_click = time.perf_counter()
        check_counter = 0

        while is_running and not is_terminated:
            # 연타 속도를 방해하지 않도록 15클릭마다 한 번씩 가볍게 f.png 체크
            check_counter += 1
            if check_counter >= 15:
                check_counter = 0
                if check_image_exists('f.png', threshold_finish):
                    print("[완료] 조리 완료 감지!")
                    time.sleep(0.2)
                    break

            now = time.perf_counter()
            interval = 1.0 / current_cps if current_cps > 0 else 0.015

            if now >= next_click:
                send_input_left_click()
                next_click += interval
                if next_click < now - interval:
                    next_click = now + interval
            else:
                time.sleep(0.0005)

# ==================== 단축키 등록 ====================
if __name__ == '__main__':
    check_images()
    keyboard.add_hotkey('F8', lambda: globals().update(is_running=not is_running))
    keyboard.add_hotkey('F9', lambda: os._exit(0))
    keyboard.add_hotkey('F5', adjust_threshold_menu)
    keyboard.add_hotkey('F6', decrease_cps)
    keyboard.add_hotkey('F7', increase_cps)

    threading.Thread(target=macro_loop, daemon=True).start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        os._exit(0)
