# nyong.py - Minecraft Auto Cooking Macro
global fast_clicking
global running
global stop_program

import time
import threading
import ctypes
import pyautogui
import keyboard
import numpy as np
import mss
import cv2
import os
import sys

try:
    import win32api
    import win32con
    USE_WIN32 = True
except ImportError:
    USE_WIN32 = False

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def check_authorized_pc():
    print('[인증 성공] 기기 제한 해제됨')
    return True

# 이미지 파일명 정의
TARGET_IMAGE = 'target2.png'          # 재료 이미지
BOWL_IMAGE = 'bowl.png'               # 도마 위 그릇 이미지
SINK_IMAGE = 'sink.png'               # 싱크대 UI 이미지
CUTTING_BOARD_IMAGE = 'cutting_board.png' # 도마 UI 이미지
SW_IMAGE = 'sw2.png'                 # 조리 시작 버튼 이미지
LOBBY_IMAGE = 'lobby.png'             # 로비 감지 이미지

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
REGION = (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

# 💡 툴팁(설명창) 방지용 마우스 임시 피신 좌표 (화면 좌상단 빈 공간)
SAFE_X, SAFE_Y = 100, 100

# [정밀도 설정]
CONFIDENCE = 0.9           # 완료/버튼 기본 인식 정확도
CONFIDENCE_TARGET = 0.80   # 작물 이미지 인식 정확도
CONFIDENCE_BOWL = 0.80     # 그릇 이미지 인식 정확도
CONFIDENCE_UI = 0.30       # UI 인식 정확도 (30%)

# ⏱️ 기본 딜레이 설정
FAST_DELAY = 0.2
CHECK_DELAY = 0.35         # 우클릭 후 서버 갱신 대기시간 (0.35초)

SEARCH_TIMEOUT = 10
SEARCH_POLL_INTERVAL = 0.02
LOOP_INTERVAL = 0.2

BASE_DIR = get_base_dir()
F_IMAGE = os.path.join(BASE_DIR, 'f.png')
F_IMAGE_CONFIDENCE = 0.5
F_IMAGE_CHECK_INTERVAL = 0.05

SW_CLICK_CPS = 60
TOGGLE_KEY = 'f8'
EXIT_KEY = 'f9'
FAST_CLICK_KEY = 'f6'
CLICKS_PER_SECOND = 20

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

running = False
fast_clicking = False
stop_program = False

try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

_thread_local = threading.local()

def get_sct():
    if not hasattr(_thread_local, 'sct'):
        _thread_local.sct = mss.mss()
    return _thread_local.sct

def imread_unicode(path, flags=cv2.IMREAD_GRAYSCALE):
    try:
        img_array = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(img_array, flags)
        return img
    except Exception as e:
        print(f'[에러] 이미지 읽기 실패: {e}')
        return None

_f_template = imread_unicode(F_IMAGE, cv2.IMREAD_GRAYSCALE)

PUL = ctypes.POINTER(ctypes.c_ulong)

class MouseInput(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong), ('time', ctypes.c_ulong), ('dwExtraInfo', PUL)]

class Input_I(ctypes.Union):
    _fields_ = [('mi', MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('ii', Input_I)]

MOUSEEVENTF_LEFTDOWN = 2
MOUSEEVENTF_LEFTUP = 4
INPUT_MOUSE = 0

def send_input_click():
    extra = ctypes.c_ulong(0)
    ii_down = Input_I()
    ii_down.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    x_down = Input(INPUT_MOUSE, ii_down)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x_down), ctypes.sizeof(x_down))
    ii_up = Input_I()
    ii_up.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    x_up = Input(INPUT_MOUSE, ii_up)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(x_up), ctypes.sizeof(x_up))

def fast_mouse_click(x, y):
    if USE_WIN32:
        win32api.SetCursorPos((int(x), int(y)))
        send_input_click()
    else:
        pyautogui.click(x, y)

def move_mouse(x, y):
    if USE_WIN32:
        win32api.SetCursorPos((int(x), int(y)))
    else:
        pyautogui.moveTo(x, y)

def is_image_present_fullscreen_fast(template, confidence=0.8):
    if template is None:
        return False
    try:
        sct = get_sct()
        monitor = sct.monitors[0]
        screenshot = sct.grab(monitor)
        img_arr = np.array(screenshot)
        screen_gray = cv2.cvtColor(img_arr, cv2.COLOR_BGRA2GRAY)
        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= confidence
    except Exception as e:
        return False

def check_lobby_and_stop():
    global running
    lobby_path = os.path.join(BASE_DIR, LOBBY_IMAGE)
    if os.path.exists(lobby_path):
        try:
            loc = pyautogui.locateCenterOnScreen(lobby_path, confidence=0.8, grayscale=True)
            if loc:
                print('\n[경고] 로비 화면 감지됨! 매크로 정지.')
                running = False
                return True
        except pyautogui.ImageNotFoundException:
            pass
    return False

_detection_flag = threading.Event()

def image_watcher_thread(f_template, f_confidence, check_interval=0.05):
    _detection_flag.clear()
    while running and (not stop_program) and (not _detection_flag.is_set()):
        if is_image_present_fullscreen_fast(f_template, confidence=f_confidence):
            _detection_flag.set()
            return
        time.sleep(check_interval)

# [1단계] UI 열기 검증 (기존 정상 작동 방식 유지)
def open_gui_with_right_click(timeout=10):
    start = time.perf_counter()
    print('\n[진행] 조리대/싱크대 열기 시도')
    sink_path = os.path.join(BASE_DIR, SINK_IMAGE)
    board_path = os.path.join(BASE_DIR, CUTTING_BOARD_IMAGE)
    target_path = os.path.join(BASE_DIR, TARGET_IMAGE)

    while time.perf_counter() - start < timeout:
        if not running or check_lobby_and_stop():
            return False

        if os.path.exists(target_path):
            try:
                if pyautogui.locateCenterOnScreen(target_path, confidence=CONFIDENCE_TARGET, grayscale=True):
                    print('[성공] 작물 감지됨 - UI 이미 열림 확인')
                    return True
            except pyautogui.ImageNotFoundException:
                pass

        is_sink_open = False
        is_board_open = False

        if os.path.exists(sink_path):
            try:
                if pyautogui.locateCenterOnScreen(sink_path, confidence=CONFIDENCE_UI, grayscale=True):
                    is_sink_open = True
            except pyautogui.ImageNotFoundException:
                pass

        if os.path.exists(board_path):
            try:
                if pyautogui.locateCenterOnScreen(board_path, confidence=CONFIDENCE_UI, grayscale=True):
                    is_board_open = True
            except pyautogui.ImageNotFoundException:
                pass

        if is_sink_open or is_board_open:
            print('[성공] UI(도마 또는 싱크대) 열림 확인됨')
            return True

        pyautogui.click(button='right')
        time.sleep(FAST_DELAY)
        print('[렉 감지] UI 감지 재시도 중...')
    
    print('[실패] UI 열기 타임아웃')
    return False

# [2단계] 작물 우클릭 ➔ 💡 마우스 안전지대 피신 ➔ 0.35초 대기 ➔ 그릇 검증 ➔ 연타 버튼 이동
def click_crop_and_verify_upload(target_img_path, bowl_img_path, sw_img_path, timeout=10):
    start = time.perf_counter()
    print('[진행] 재료 찾기 시도')
    target_full_path = os.path.join(BASE_DIR, target_img_path)
    bowl_full_path = os.path.join(BASE_DIR, bowl_img_path)
    sw_full_path = os.path.join(BASE_DIR, sw_img_path)

    while time.perf_counter() - start < timeout:
        if not running or check_lobby_and_stop():
            return None
        
        try:
            target_loc = pyautogui.locateCenterOnScreen(target_full_path, confidence=CONFIDENCE_TARGET, grayscale=True)
        except pyautogui.ImageNotFoundException:
            target_loc = None
            
        if target_loc:
            print(f'[동작] 작물 발견({target_loc.x}, {target_loc.y}) -> 우클릭 후 피신')
            
            # 1. 작물 우클릭
            pyautogui.click(target_loc.x, target_loc.y, button='right')
            
            # 2. 💡 우클릭 직후 툴팁 가림 방지를 위해 마우스를 안전지대(SAFE_X, SAFE_Y)로 즉시 이동
            move_mouse(SAFE_X, SAFE_Y)
            
            # 3. 우클릭 후 서버 반응 및 화면 갱신 대기
            time.sleep(CHECK_DELAY)

            # 4. 그릇 사라짐 확인
            bowl_exists = False
            if os.path.exists(bowl_full_path):
                try:
                    if pyautogui.locateCenterOnScreen(bowl_full_path, confidence=CONFIDENCE_BOWL, grayscale=True):
                        bowl_exists = True
                except pyautogui.ImageNotFoundException:
                    bowl_exists = False

            if not bowl_exists:
                print('[성공] 그릇 이미지 사라짐 확인! (재료 올라감)')
                
                # 조리 시작 버튼 위치 찾기
                try:
                    sw_loc = pyautogui.locateCenterOnScreen(sw_full_path, confidence=CONFIDENCE, grayscale=True)
                    if sw_loc:
                        # 5. 조리 버튼 위치로 마우스 커서 이동
                        move_mouse(sw_loc.x, sw_loc.y)
                        time.sleep(FAST_DELAY)
                        return sw_loc
                    else:
                        print('[경고] 조리 버튼(sw2.png)을 찾을 수 없음')
                except pyautogui.ImageNotFoundException:
                    print('[경고] 조리 버튼(sw2.png) 이미지 검색 실패')
            else:
                print('[경고/렉 감지] 그릇이 그대로 있음 (우클릭 씹힘). 재시도...')
                time.sleep(FAST_DELAY)
                continue
        
        time.sleep(SEARCH_POLL_INTERVAL)
        
    print('[실패] 재료 올려두기 타임아웃')
    return None

def hold_until_image_detected(sw_location, f_template, timeout=10, cps=60, f_confidence=0.8, check_interval=0.05):
    if not sw_location:
        return False
        
    click_interval = 1.0 / cps
    print(f'[진행] 연타 시작 (CPS: {cps})')
    
    watcher = threading.Thread(target=image_watcher_thread, args=(f_template, f_confidence, check_interval), daemon=True)
    watcher.start()
    
    click_count = 0
    measure_start = time.perf_counter()
    next_click_time = time.perf_counter()
    
    while running and (not stop_program):
        if check_lobby_and_stop():
            return False
            
        if _detection_flag.is_set():
            print(f'[감지 완료] 화면에 {F_IMAGE} 감지됨')
            return True
            
        now = time.perf_counter()
        if now >= next_click_time:
            if USE_WIN32:
                send_input_click()
            else:
                pyautogui.click(sw_location.x, sw_location.y)
            click_count += 1
            next_click_time += click_interval
            if next_click_time < now - click_interval:
                next_click_time = now + click_interval
                
        if now - measure_start >= 1.0:
            actual_cps = click_count / (now - measure_start)
            print(f'[측정] 실제 CPS: {actual_cps:.1f}')
            click_count = 0
            measure_start = now
            
        time.sleep(0.0005)
        
    _detection_flag.set()
    return False

def do_cycle():
    if check_lobby_and_stop():
        return

    # 1단계: UI 열림 검증
    if not open_gui_with_right_click(timeout=SEARCH_TIMEOUT):
        return

    time.sleep(FAST_DELAY)

    # 2단계: 작물 우클릭 -> 피신 -> 딜레이 후 그릇 검증 -> 연타 버튼 이동
    sw_location = click_crop_and_verify_upload(TARGET_IMAGE, BOWL_IMAGE, SW_IMAGE, timeout=SEARCH_TIMEOUT)
    if not sw_location or not running:
        return

    # 3단계: 조리 연타 및 완료 감지
    hold_until_image_detected(sw_location, f_template=_f_template, timeout=SEARCH_TIMEOUT, cps=SW_CLICK_CPS, f_confidence=F_IMAGE_CONFIDENCE, check_interval=F_IMAGE_CHECK_INTERVAL)

def worker_loop():
    while not stop_program:
        if running:
            do_cycle()
            time.sleep(LOOP_INTERVAL)
        else:
            time.sleep(0.05)

def toggle_running():
    global running
    running = not running
    print(f"\n===== {('시작' if running else '정지')} (F8) =====\n")

def toggle_fast_click():
    global fast_clicking
    fast_clicking = not fast_clicking

def fast_click_loop():
    interval = 1.0 / CLICKS_PER_SECOND
    while not stop_program:
        if fast_clicking:
            x, y = pyautogui.position()
            fast_mouse_click(x, y)
            time.sleep(interval)
        else:
            time.sleep(0.05)

def exit_program():
    global stop_program
    global running
    print('\n===== 종료 =====')
    running = False
    stop_program = True
    _detection_flag.set()

def main():
    check_authorized_pc()
    print('========================================')
    print('nyong.exe 매크로 실행됨 (툴팁 방지 피신 적용)')
    print('F8: 시작 / 정지, F9: 종료')
    print('========================================\n')
    
    keyboard.add_hotkey(TOGGLE_KEY, toggle_running)
    keyboard.add_hotkey(FAST_CLICK_KEY, toggle_fast_click)
    keyboard.add_hotkey(EXIT_KEY, exit_program)
    
    threading.Thread(target=worker_loop, daemon=True).start()
    threading.Thread(target=fast_click_loop, daemon=True).start()
    
    while not stop_program:
        time.sleep(0.2)

if __name__ == '__main__':
    main()
