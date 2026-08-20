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
threshold_item = 0.80   # 1번: 작물 본체 (target2.png)
threshold_desc = 0.80   # 2번: 작물 설명탭 (t2.png)
threshold_ui = 0.65     # 3번: 도마/싱크대 UI (cutting_board.png / sink.png) - 기본값 65%
threshold_finish = 0.80 # 완성 멘트 (f.png)

# 연타 속도 (CPS) 설정 (최소 10, 최대 100, 초기값 65)
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
        print("스크립트 실행 전 동일 폴더에 이미지들을 준비해주세요.")

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
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        return (center_x, center_y)
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
    sleep_time = random.uniform(0.1, 0.2)
    time.sleep(sleep_time)
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

# ==================== 실시간 조절 단축키 기능 ====================
def adjust_threshold_menu():
    global threshold_item, threshold_desc, threshold_ui
    print("\n" + "="*40)
    print(" [정확도 설정 메뉴]")
    print(f" 1. 작물 본체 (target2.png) 현재 정확도: {int(threshold_item * 100)}%")
    print(f" 2. 작물 설명탭 (t2.png) 현재 정확도: {int(threshold_desc * 100)}%")
    print(f" 3. 도마/싱크대 UI (cutting_board/sink.png) 현재 정확도: {int(threshold_ui * 100)}%")
    print("="*40)
    
    choice = input("조절할 항목의 번호를 입력하세요 (1, 2, 3 / 취소는 엔터): ").strip()
    
    if choice in ['1', '2', '3']:
        if choice == '1':
            target_name = "작물 본체"
        elif choice == '2':
            target_name = "작물 설명탭"
        else:
            target_name = "도마/싱크대 UI"

        print(f"\n[{target_name}] 조절 모드 활성화됨")
        print(" -> [Page Up]: 5% 올리기 (+)")
        print(" -> [Page Down]: 5% 내리기 (-)")
        print(" -> [그 외 아무 키나 엔터]: 설정 종료")
        
        while True:
            event = keyboard.read_event(suppress=True)
            if event.event_type == keyboard.KEY_DOWN:
                if event.name == 'page up':
                    if choice == '1':
                        threshold_item = min(1.0, threshold_item + 0.05)
                        print(f" -> 작물 본체 정확도: {int(threshold_item * 100)}%")
                    elif choice == '2':
                        threshold_desc = min(1.0, threshold_desc + 0.05)
                        print(f" -> 작물 설명탭 정확도: {int(threshold_desc * 100)}%")
                    else:
                        threshold_ui = min(1.0, threshold_ui + 0.05)
                        print(f" -> 도마/싱크대 UI 정확도: {int(threshold_ui * 100)}%")
                elif event.name == 'page down':
                    if choice == '1':
                        threshold_item = max(0.1, threshold_item - 0.05)
                        print(f" -> 작물 본체 정확도: {int(threshold_item * 100)}%")
                    elif choice == '2':
                        threshold_desc = max(0.1, threshold_desc - 0.05)
                        print(f" -> 작물 설명탭 정확도: {int(threshold_desc * 100)}%")
                    else:
                        threshold_ui = max(0.1, threshold_ui - 0.05)
                        print(f" -> 도마/싱크대 UI 정확도: {int(threshold_ui * 100)}%")
                else:
                    print("[설정 완료] 메뉴를 나갑니다.\n")
                    break
    else:
        print("[취소] 설정 메뉴를 종료합니다.\n")

def decrease_cps():
    global current_cps
    current_cps = max(10, current_cps - 1)
    print(f"[속도 조절] 연타 CPS 낮춤: {current_cps} CPS")

def increase_cps():
    global current_cps
    current_cps = min(100, current_cps + 1)
    print(f"[속도 조절] 연타 CPS 높임: {current_cps} CPS")

# ==================== 메인 매크로 루프 ====================
def macro_loop():
    global is_running, threshold_item, threshold_desc, threshold_ui, threshold_finish, current_cps
    print("[안내] 매크로 대기 중...")
    print("[단축키 안내]")
    print(" - F8: 시작 / 정지")
    print(" - F9: 완전 종료")
    print(" - F5: 정확도 조절 메뉴 (터미널 제어)")
    print(f" - F6 / F7: 연타 속도 1씩 낮추기 / 높이기 (현재: {current_cps} CPS / 범위: 10 ~ 100)\n")

    while not is_terminated:
        if not is_running:
            time.sleep(0.1)
            continue

        # [단계 1 & 2] 도마/싱크대 열기 및 감지
        ui_opened = False
        retry_count = 0
        max_retries = 3

        while is_running and not is_terminated and retry_count < max_retries:
            retry_count += 1
            print(f"[동작] 도마/싱크대 열기 시도 ({retry_count}/{max_retries}회)...")
            human_right_click()
            
            ui_check_start = time.time()
            while time.time() - ui_check_start < 3.0:
                if not is_running or is_terminated:
                    break
                if check_image_exists('cutting_board.png', threshold=threshold_ui) or check_image_exists('sink.png', threshold=threshold_ui):
                    print("[진행] 도마/싱크대 UI 열림 확인됨.")
                    ui_opened = True
                    break
                time.sleep(0.1)

            if ui_opened:
                break
            else:
                print(f"[경고] {retry_count}회 시도 실패: UI가 열리지 않았습니다.")

        if not ui_opened:
            print("[알림] 도마/싱크대 UI를 열지 못해 매크로를 일시 정지합니다.")
            is_running = False
            continue

        # [단계 3] 작물 우선순위 탐색
        print("[진행] 재료 탐색 시작...")
        search_start_time = time.time()
        target_pos = None

        while is_running and not is_terminated:
            target_pos = find_image('target2.png', threshold=threshold_item)
            if target_pos:
                break
            
            target_pos = find_image('t2.png', threshold=threshold_desc)
            if target_pos:
                break

            if time.time() - search_start_time > 5.0:
                print("[알림] 5초 동안 재료나 설명탭을 찾지 못해 매크로를 중지합니다.")
                is_running = False
                break
            
            time.sleep(0.1)

        if not is_running or target_pos is None:
            continue

        # [단계 4] 작물 우클릭 안착
        win32api.SetCursorPos(target_pos)
        time.sleep(0.05)
        human_right_click()
        print("[동작] 작물 우클릭 완료. 1.0초 대기 및 그릇 소멸 검증 중...")
        time.sleep(1.0) # 요청하신 1초 대기

        # [단계 5] 그릇 소멸 검증 (bowl.png)
        bowl_check_start = time.time()
        while check_image_exists('bowl.png', threshold=0.80):
            if not is_running or is_terminated:
                break
            if time.time() - bowl_check_start > 2.0:
                print("[경고] 그릇이 사라지지 않았습니다. 재시도합니다.")
                break
            time.sleep(0.1)
        
        if not is_running:
            continue

        # [단계 6] 조리 버튼 위치 확인 및 독립된 초고속 연타 쓰레드 실행
        print("[진행] 재료 안착 확인. 조리 버튼 초고속 연타 시작...")
        
        sw_pos = find_image('sw2.png', threshold=0.80)
        if sw_pos:
            win32api.SetCursorPos(sw_pos)
        else:
            print("[경고] 조리 버튼(sw2.png)을 찾지 못했습니다.")
            continue

        # 연타 전용 순수 백그라운드 스레드 (이미지 검사 일체 없음, 100% 순수 CPS 보장)
        clicking_active = threading.Event()
        clicking_active.set()

        def pure_clicker():
            next_click_time = time.perf_counter()
            while clicking_active.is_set() and is_running and not is_terminated:
                now = time.perf_counter()
                click_interval = 1.0 / current_cps if current_cps > 0 else 0.015

                if now >= next_click_time:
                    send_input_left_click()
                    next_click_time += click_interval
                    if next_click_time < now - click_interval:
                        next_click_time = now + click_interval
                else:
                    time.sleep(0.0002)

        click_thread = threading.Thread(target=pure_clicker, daemon=True)
        click_thread.start()

        # 메인 루프에서는 오직 f.png 감지만 전담 (연타 속도에 0.001초의 영향도 주지 않음)
        is_finished = False
        while is_running and not is_terminated:
            if check_image_exists('f.png', threshold=threshold_finish):
                print("[완료] 조리 완료 이미지 감지! 다음 요리를 위해 처음으로 돌아갑니다.")
                is_finished = True
                break
            time.sleep(0.05) # 감지 주기를 살짝 주어 CPU 과부하 방지 및 안정성 확보

        # 연타 스레드 종료 신호 전송
        clicking_active.clear()
        click_thread.join(timeout=0.5)

        if is_finished:
            time.sleep(0.2)
            continue

# ==================== 단축키 콜백 함수 ====================
def toggle_macro():
    global is_running
    is_running = not is_running
    if is_running:
        print(f"\n[상태] 매크로가 시작되었습니다. (현재 CPS: {current_cps})")
    else:
        print("\n[상태] 매크로가 일시 정지되었습니다.")

def terminate_program():
    global is_terminated, is_running
    is_running = False
    is_terminated = True
    try:
        ctypes.windll.winmm.timeEndPeriod(1)
    except Exception:
        pass
    print("\n[종료] 매크로 프로그램을 완전히 종료합니다.")
    os._exit(0)

# ==================== 진입점 (Main) ====================
if __name__ == '__main__':
    check_images()
    
    keyboard.add_hotkey('F8', toggle_macro)
    keyboard.add_hotkey('F9', terminate_program)
    keyboard.add_hotkey('F5', adjust_threshold_menu)
    keyboard.add_hotkey('F6', decrease_cps)
    keyboard.add_hotkey('F7', increase_cps)

    t = threading.Thread(target=macro_loop)
    t.daemon = True
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        terminate_program()
