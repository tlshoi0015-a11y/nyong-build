# nyong.py - Minecraft Auto Cooking Macro (External Images)
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

# EXE 파일이 있는 폴더 경로 가져오기 (외부 이미지 로드용)
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def check_authorized_pc():
    print('[인증 성공] 기기 제한 해제됨')
    return True

# 이미지 파일명 정의 (.exe 파일과 같은 폴더에 위치해야 함)
TARGET_IMAGE = 'target2.png'          # 재료 이미지
SINK_IMAGE = 'sink.png'               # 싱크대 UI 이미지
CUTTING_BOARD_IMAGE = 'cutting_board.png' # 도마 UI 이미지 (추가됨)
SW_IMAGE = 'sw2.png'                 # 조리 시작 버튼 이미지
EMPTY_SLOT_IMAGE = 'empty_slot.png'   # 클릭 후 빈 슬롯 이미지
LOBBY_IMAGE = 'lobby.png'             # 로비 감지 이미지

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
REGION = (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

# [정밀도 및 딜레이 설정]
CONFIDENCE = 0.5           # 완료/버튼 기본 인식 정확도 (90% 유지)
CONFIDENCE_TARGET = 0.80   # 작물 이미지 인식 정확도 (80% 적용)
CONFIDENCE_UI = 0.50       # UI 및 빈 슬롯 인식 정확도

DELAY_EMPTY_TO_ACTION = 0.5  # 빈 슬롯 확인 후 연타/다지기 시작전 대기 (0.5초)
DELAY_DEFAULT = 0.3          # 기본 대기시간 (0.3초)

SEARCH_TIMEOUT = 10
SEARCH_POLL_INTERVAL = 0.02
STEP_DELAY = 0.3           # 단계별 대기시간 0.3초로 조율
LOOP_INTERVAL = 1.0        # 사이클 완료 후 대기시간 1.0초

BASE_DIR = get_base_dir()
F_IMAGE = os.path.join(BASE_DIR, 'f.png')
F_IMAGE_CONFIDENCE = 0.5
F_IMAGE_CHECK_INTERVAL = 0.1

SW_CLICK_CPS = 60          # 초당 클릭수 60회
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

def image_watcher_thread(f_template, f_confidence, check_interval=0.1):
    _detection_flag.clear()
    while running and (not stop_program) and (not _detection_flag.is_set()):
        if is_image_present_fullscreen_fast(f_template, confidence=f_confidence):
            _detection_flag.set()
            return
        time.sleep(check_interval)

# [1단계] 우클릭 후 조리대/싱크대 UI(cutting_board.png 또는 sink.png) 열림 확인
def open_gui_with_right_click(timeout=10):
    start = time.perf_counter()
    print('\n[진행] 조리대/싱크대 열기 시도 (우클릭)')
    sink_path = os.path.join(BASE_DIR, SINK_IMAGE)
    board_path = os.path.join(BASE_DIR, CUTTING_BOARD_IMAGE)

    while time.perf_counter() - start < timeout:
        if not running or check_lobby_and_stop():
            return False
        
        pyautogui.click(button='right')
        time.sleep(DELAY_DEFAULT)

        # 도마 또는 싱크대 이미지 둘 중 하나라도 탐지되면 성공
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

        # 두 파일이 전부 폴더에 없을 경우 바로 넘어가기 예외처리
        if not os.path.exists(sink_path) and not os.path.exists(board_path):
            print('[안내] UI 이미지 파일 없음 - 검수 없이 진행')
            return True
        
        print('[렉 감지] UI가 열리지 않음. 우클릭 재시도...')
    
    print('[실패] UI 열기 타임아웃')
    return False

# [2단계] 재료(target2.png) 클릭 후, 그 클릭 지점이 빈 슬롯(empty_slot.png)으로 변했는지 집중 검증
def click_and_verify_upload(target_img_path, sw_img_path, timeout=10):
    start = time.perf_counter()
    print('[진행] 재료 찾기 및 빈 슬롯 검증 시도')
    target_full_path = os.path.join(BASE_DIR, target_img_path)
    empty_path = os.path.join(BASE_DIR, EMPTY_SLOT_IMAGE)

    while time.perf_counter() - start < timeout:
        if not running or check_lobby_and_stop():
            return None
        
        try:
            # 작물 인식은 정밀도 0.80(CONFIDENCE_TARGET) 적용
            target_loc = pyautogui.locateCenterOnScreen(target_full_path, confidence=CONFIDENCE_TARGET, grayscale=True)
        except pyautogui.ImageNotFoundException:
            target_loc = None
            
        if target_loc:
            print('[동작] 작물 발견 -> 우클릭 시도')
            pyautogui.click(target_loc.x, target_loc.y, button='right')
            time.sleep(DELAY_DEFAULT)  # 우클릭 반응 대기 0.3초
            
            # 클릭했던 마우스 위치(target_loc) 기준 60x60 영역 검사 (빈 칸 검증 필수)
            is_empty = False
            if os.path.exists(empty_path):
                try:
                    search_box = (int(target_loc.x - 15), int(target_loc.y - 15), 30, 30)
                    if pyautogui.locateOnScreen(empty_path, region=search_box, confidence=CONFIDENCE_UI, grayscale=True):
                        print('[성공] 클릭 위치 빈 슬롯 확인됨')
                        is_empty = True
                except pyautogui.ImageNotFoundException:
                    pass
            else:
                is_empty = True

            # 빈 슬롯이 확인되지 않았다면 (우클릭 씹힘) 절대 다지기 연타로 진입하지 않고 우클릭 재시도
            if not is_empty:
                print('[경고/렉 감지] 우클릭이 씹혀 빈 슬롯이 되지 않음! 다지기 취소 및 재시도...')
                time.sleep(DELAY_DEFAULT)
                continue

            # 빈 슬롯 확인 성공시에만 조리(sw2.png) 버튼 감지
            try:
                sw_loc = pyautogui.locateCenterOnScreen(os.path.join(BASE_DIR, sw_img_path), confidence=CONFIDENCE, grayscale=True)
                if sw_loc:
                    print(f'[성공] 조리 버튼 감지 완료! 연타 시작 전 {DELAY_EMPTY_TO_ACTION}초 대기')
                    time.sleep(DELAY_EMPTY_TO_ACTION)  # 요청하신 빈 슬롯 확인 후 연타 시작 전 0.5초 대기
                    return sw_loc
            except pyautogui.ImageNotFoundException:
                print('[경고] 조리 버튼(sw2.png)을 찾을 수 없음. 재시도...')
        
        time.sleep(SEARCH_POLL_INTERVAL)
        
    print('[실패] 재료 올려두기 타임아웃')
    return None

def hold_until_image_detected(sw_location, f_template, timeout=10, cps=60, f_confidence=0.8, check_interval=0.1):
    if not sw_location:
        return False
        
    if USE_WIN32:
        win32api.SetCursorPos((int(sw_location.x), int(sw_location.y)))
        
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

    # 1단계: UI 열림 검증 (cutting_board.png 또는 sink.png)
    if not open_gui_with_right_click(timeout=SEARCH_TIMEOUT):
        return

    time.sleep(DELAY_DEFAULT)

    # 2단계: 재료 클릭 및 빈 슬롯(empty_slot.png) 검증
    sw_location = click_and_verify_upload(TARGET_IMAGE, SW_IMAGE, timeout=SEARCH_TIMEOUT)
    if not sw_location or not running:
        return

    # 3단계: 조리 연타 (sw2.png) 및 완료 감지 (f.png)
    hold_until_image_detected(sw_location, f_template=_f_template, timeout=SEARCH_TIMEOUT, cps=SW_CLICK_CPS, f_confidence=F_IMAGE_CONFIDENCE, check_interval=F_IMAGE_CHECK_INTERVAL)

def worker_loop():
    while not stop_program:
        if running:
            do_cycle()
            for _ in range(int(LOOP_INTERVAL * 10)):
                if not running or stop_program:
                    break
                time.sleep(0.1)
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
    print('nyong.exe 매크로 실행됨')
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
