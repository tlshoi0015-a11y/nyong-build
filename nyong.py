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

# ==================== 전역 변수 및 설정 ====================
is_running = False
is_terminated = False
current_cps = 65

threshold_item = 0.80
threshold_desc = 0.80
threshold_ui = 0.65
threshold_finish = 0.50  # f.png 기본 감지 정확도 50%

REQUIRED_IMAGES = [
    'target2.png', 't2.png', 'bowl.png', 'sw2.png', 
    'f.png', 'sink.png', 'cutting_board.png', 'lobby.png'
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

# 전역 연타 스레드 구동
clicker = ClickerThread()
clicker.start()

# ==================== 메인 매크로 루프 ====================
def macro_loop():
    global is_running, is_terminated, current_cps
    print("[안내] 매크로 대기 중... (F8: 시작/정지)")

    while not is_terminated:
        if not is_running:
            time.sleep(0.1)
            continue

        # 1 & 2. 도마/싱크대 열기 (5회 재시도)
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

        # 4. 우클릭 및 0.7초 대기
        win32api.SetCursorPos(target_pos)
        time.sleep(0.05)
        human_right_click()
        print("[동작] 작물 우클릭 완료. 0.7초 대기 중...")
        time.sleep(0.7)

        # 5. 곧바로 그릇 소멸 검증 (타임아웃 0.7초)
        bowl_t = time.time()
        while check_image_exists('bowl.png', 0.80):
            if not is_running or is_terminated: break
            if time.time() - bowl_t > 0.7: break
            time.sleep(0.05)

        if not is_running: continue

        # 6. 조리 버튼 위치 확인 후 '연타 스레드' 폭격 시작
        sw_pos = find_image('sw2.png', 0.80)
        if sw_pos:
            win32api.SetCursorPos(sw_pos)
        else:
            continue

        print("[진행] 고속 연타 및 f.png 감시 시작...")
        clicker.active.set() # 연타 스레드 ON

        # 메인 루프에서는 오직 f.png 감지만 빠르게 수행
        is_finished = False
        while is_running and not is_terminated:
            if check_image_exists('f.png', threshold_finish):
                print(f"[완료] 조리 완료 이미지(f.png) 감지! (정확도: {int(threshold_finish*100)}%)")
                is_finished = True
                break
            time.sleep(0.05)

        clicker.active.clear() # 연타 스레드 OFF

        if is_finished:
            # f 감지 후 안정적인 인식을 위해 0.5초 대기 후 다음 루프(도마/싱크대 열기)로 이동
            print("[대기] f 감지 완료 후 0.5초 안정화 대기...")
            time.sleep(0.5)
            continue

# ==================== 단축키 및 진입점 ====================
if __name__ == '__main__':
    check_images()

    def toggle_macro():
        global is_running
        is_running = not is_running
        status = "시작되었습니다." if is_running else "일시 정지되었습니다."
        print(f"\n[상태] 매크로가 {status} (현재 CPS: {current_cps})")

    def terminate_program():
        global is_running, is_terminated
        is_running = False
        is_terminated = True
        clicker.active.set()
        print("\n[종료] 프로그램을 완전히 종료합니다.")
        os._exit(0)

    def decrease_cps():
        global current_cps
        current_cps = max(10, current_cps - 1)
        print(f"[속도] CPS 낮춤: {current_cps}")

    def increase_cps():
        global current_cps
        current_cps = min(100, current_cps + 1)
        print(f"[속도] CPS 높임: {current_cps}")

    def adjust_threshold_menu():
        global threshold_item, threshold_desc, threshold_ui, threshold_finish
        print("\n" + "="*50)
        print(f" [정확도 설정]")
        print(f" 1. 본체(target2): {int(threshold_item*100)}% | 2. 설명탭(t2): {int(threshold_desc*100)}%")
        print(f" 3. UI(싱크/도마): {int(threshold_ui*100)}%   | 4. 완료(f.png): {int(threshold_finish*100)}%")
        print("="*50)
        choice = input("조절할 번호 입력 (1, 2, 3, 4 / 취소는 엔터): ").strip()
        if choice in ['1', '2', '3', '4']:
            target_name = {"1": "본체", "2": "설명탭", "3": "UI", "4": "완료(f.png)"}[choice]
            print(f" -> [{target_name} 조절 중] [Page Up]: +5% | [Page Down]: -5% | 그 외 키: 종료")
            while True:
                event = keyboard.read_event(suppress=True)
                if event.event_type == keyboard.KEY_DOWN:
                    if event.name == 'page up':
                        if choice == '1': threshold_item = min(1.0, threshold_item + 0.05)
                        elif choice == '2': threshold_desc = min(1.0, threshold_desc + 0.05)
                        elif choice == '3': threshold_ui = min(1.0, threshold_ui + 0.05)
                        else: threshold_finish = min(1.0, threshold_finish + 0.05)
                        print("정확도 5% 증가")
                    elif event.name == 'page down':
                        if choice == '1': threshold_item = max(0.1, threshold_item - 0.05)
                        elif choice == '2': threshold_desc = max(0.1, threshold_desc - 0.05)
                        elif choice == '3': threshold_ui = max(0.1, threshold_ui - 0.05)
                        else: threshold_finish = max(0.1, threshold_finish - 0.05)
                        print("정확도 5% 감소")
                    else:
                        break

    keyboard.add_hotkey('F8', toggle_macro)
    keyboard.add_hotkey('F9', terminate_program)
    keyboard.add_hotkey('F5', adjust_threshold_menu)
    keyboard.add_hotkey('F6', decrease_cps)
    keyboard.add_hotkey('F7', increase_cps)

    # 메인 루프 실행
    threading.Thread(target=macro_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        terminate_program()
