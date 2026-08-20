import os
import time
import multiprocessing
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

# ==================== 독립된 연타 전용 프로세스 (CPS 100% 보장) ====================
def clicker_process(cps_value, active_flag):
    try:
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass
    
    next_click = time.perf_counter()
    while active_flag.value:
        if cps_value.value <= 0:
            time.sleep(0.01)
            continue

        now = time.perf_counter()
        interval = 1.0 / cps_value.value

        if now >= next_click:
            send_input_left_click()
            next_click += interval
            if next_click < now - interval:
                next_click = now + interval
        else:
            time.sleep(0.0001)

# ==================== 이미지 및 화면 함수 ====================
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

# ==================== 메인 매크로 루프 ====================
def macro_loop(is_running, is_terminated, current_cps, threshold_item, threshold_desc, threshold_ui, threshold_finish):
    print("[안내] 매크로 대기 중... (F8: 시작/정지)")

    while not is_terminated.value:
        if not is_running.value:
            time.sleep(0.1)
            continue

        # 1 & 2. 도마/싱크대 열기 (3회 재시도)
        ui_opened = False
        for retry in range(1, 4):
            if not is_running.value or is_terminated.value: break
            print(f"[동작] 도마/싱크대 열기 시도 ({retry}/3)...")
            human_right_click()
            
            start_t = time.time()
            while time.time() - start_t < 3.0:
                if not is_running.value or is_terminated.value: break
                if check_image_exists('cutting_board.png', threshold_ui.value) or check_image_exists('sink.png', threshold_ui.value):
                    ui_opened = True
                    break
                time.sleep(0.1)
            if ui_opened: break

        if not ui_opened:
            is_running.value = False
            continue

        # 3. 작물 탐색
        target_pos = None
        search_t = time.time()
        while is_running.value and not is_terminated.value:
            target_pos = find_image('target2.png', threshold_item.value) or find_image('t2.png', threshold_desc.value)
            if target_pos: break
            if time.time() - search_t > 5.0:
                is_running.value = False
                break
            time.sleep(0.1)

        if not is_running.value or not target_pos: continue

        # 4. 우클릭 및 1초 대기
        win32api.SetCursorPos(target_pos)
        time.sleep(0.05)
        human_right_click()
        print("[동작] 작물 우클릭 완료. 1.0초 대기 중...")
        time.sleep(1.0)

        # 5. 그릇 소멸 검증
        bowl_t = time.time()
        while check_image_exists('bowl.png', 0.80):
            if not is_running.value or is_terminated.value: break
            if time.time() - bowl_t > 2.0: break
            time.sleep(0.1)

        if not is_running.value: continue

        # 6. 조리 버튼 위치 확인 후 '연타 전용 프로세스' 별도 가동
        sw_pos = find_image('sw2.png', 0.80)
        if sw_pos:
            win32api.SetCursorPos(sw_pos)
        else:
            continue

        print("[진행] 연타 프로세스 가동 및 f.png 감시 시작...")
        
        click_active = multiprocessing.Value('i', 1)
        p = multiprocessing.Process(target=clicker_process, args=(current_cps, click_active))
        p.daemon = True
        p.start()

        # 메인 프로세스는 연타에 영향 주지 않고 f.png 감지만 수행
        is_finished = False
        while is_running.value and not is_terminated.value:
            if check_image_exists('f.png', threshold_finish.value):
                print("[완료] 조리 완료 이미지(f.png) 감지!")
                is_finished = True
                break
            time.sleep(0.05)

        # 연타 프로세스 즉시 종료
        click_active.value = 0
        p.join(timeout=0.2)
        if p.is_alive():
            p.terminate()

        if is_finished:
            time.sleep(0.2)
            continue

# ==================== 진입점 (멀티프로세싱 안전 가드) ====================
if __name__ == '__main__':
    multiprocessing.freeze_support()
    check_images()

    # 멀티프로세스 공유 변수 설정
    is_running = multiprocessing.Value('b', False)
    is_terminated = multiprocessing.Value('b', False)
    current_cps = multiprocessing.Value('i', 65)
    
    threshold_item = multiprocessing.Value('d', 0.80)
    threshold_desc = multiprocessing.Value('d', 0.80)
    threshold_ui = multiprocessing.Value('d', 0.65)
    threshold_finish = multiprocessing.Value('d', 0.80)

    # 단축키 콜백 함수 정의
    def toggle_macro():
        is_running.value = not is_running.value
        status = "시작되었습니다." if is_running.value else "일시 정지되었습니다."
        print(f"\n[상태] 매크로가 {status} (현재 CPS: {current_cps.value})")

    def terminate_program():
        is_running.value = False
        is_terminated.value = True
        print("\n[종료] 프로그램을 완전히 종료합니다.")
        os._exit(0)

    def decrease_cps():
        current_cps.value = max(10, current_cps.value - 1)
        print(f"[속도] CPS 낮춤: {current_cps.value}")

    def increase_cps():
        current_cps.value = min(100, current_cps.value + 1)
        print(f"[속도] CPS 높임: {current_cps.value}")

    def adjust_threshold_menu():
        print("\n" + "="*40)
        print(f" [정확도 설정] 본체: {int(threshold_item.value*100)}% | 설명탭: {int(threshold_desc.value*100)}% | UI: {int(threshold_ui.value*100)}%")
        print("="*40)
        choice = input("조절할 번호 입력 (1, 2, 3 / 취소는 엔터): ").strip()
        if choice in ['1', '2', '3']:
            print(" -> [Page Up]: +5% | [Page Down]: -5% | 그 외 키: 종료")
            while True:
                event = keyboard.read_event(suppress=True)
                if event.event_type == keyboard.KEY_DOWN:
                    if event.name == 'page up':
                        if choice == '1': threshold_item.value = min(1.0, threshold_item.value + 0.05)
                        elif choice == '2': threshold_desc.value = min(1.0, threshold_desc.value + 0.05)
                        else: threshold_ui.value = min(1.0, threshold_ui.value + 0.05)
                        print("정확도 5% 증가")
                    elif event.name == 'page down':
                        if choice == '1': threshold_item.value = max(0.1, threshold_item.value - 0.05)
                        elif choice == '2': threshold_desc.value = max(0.1, threshold_desc.value - 0.05)
                        else: threshold_ui.value = max(0.1, threshold_ui.value - 0.05)
                        print("정확도 5% 감소")
                    else:
                        break

    keyboard.add_hotkey('F8', toggle_macro)
    keyboard.add_hotkey('F9', terminate_program)
    keyboard.add_hotkey('F5', adjust_threshold_menu)
    keyboard.add_hotkey('F6', decrease_cps)
    keyboard.add_hotkey('F7', increase_cps)

    # 매크로 루프 구동
    macro_process = multiprocessing.Process(
        target=macro_loop, 
        args=(is_running, is_terminated, current_cps, threshold_item, threshold_desc, threshold_ui, threshold_finish)
    )
    macro_process.daemon = True
    macro_process.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        terminate_program()
