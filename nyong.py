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

# ==================== 설정 및 전역 변수 ====================
is_running = False
is_terminated = False

# 인식 정확도 설정 (초기값 80%)
threshold_item = 0.80   # 1번: 작물 본체 (target2.png)
threshold_desc = 0.80   # 2번: 작물 설명탭 (t2.png)
threshold_finish = 0.80 # 완성 멘트 (f.png)

# 연타 속도 (CPS) 설정 (최소 10, 최대 100, 초기값 65)
current_cps = 65

# 필수 이미지 파일 목록
REQUIRED_IMAGES = [
    'target2.png', 't2.png', 'bowl.png', 'sw2.png', 
    'f.png', 'sink.png', 'cutting_board.png', 'lobby.png'
]

# ==================== 이미지 및 화면 함수 ====================
def check_images():
    missing = [img for img in REQUIRED_IMAGES if not os.path.exists(img)]
    if missing:
        print(f"[경고] 다음 이미지 파일이 누락되었습니다: {missing}")
        print("스크립트 실행 전 동일 폴더에 이미지들을 준비해주세요.")

def capture_screen():
    with mss.mss() as sct:
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
    """ 0.1초 ~ 0.2초 사이의 랜덤한 유지 시간을 가진 우클릭 """
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    sleep_time = random.uniform(0.1, 0.2)
    time.sleep(sleep_time)
    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

# ==================== 실시간 조절 단축키 기능 ====================
def adjust_threshold_menu():
    global threshold_item, threshold_desc
    print("\n" + "="*40)
    print(" [정확도 설정 메뉴]")
    print(f" 1. 작물 본체 (target2.png) 현재 정확도: {int(threshold_item * 100)}%")
    print(f" 2. 작물 설명탭 (t2.png) 현재 정확도: {int(threshold_desc * 100)}%")
    print("="*40)
    
    choice = input("조절할 항목의 번호를 입력하세요 (1 또는 2, 취소는 다른 아무 키나 엔터): ").strip()
    
    if choice in ['1', '2']:
        target_name = "작물 본체" if choice == '1' else "작물 설명탭"
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
                    else:
                        threshold_desc = min(1.0, threshold_desc + 0.05)
                        print(f" -> 작물 설명탭 정확도: {int(threshold_desc * 100)}%")
                elif event.name == 'page down':
                    if choice == '1':
                        threshold_item = max(0.1, threshold_item - 0.05)
                        print(f" -> 작물 본체 정확도: {int(threshold_item * 100)}%")
                    else:
                        threshold_desc = max(0.1, threshold_desc - 0.05)
                        print(f" -> 작물 설명탭 정확도: {int(threshold_desc * 100)}%")
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
    global is_running, threshold_item, threshold_desc, threshold_finish, current_cps
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

        print("[진행] 재료 탐색 시작...")
        start_time = time.time()
        target_pos = None

        # 5초 타임아웃 루프 (재료 탐색)
        while is_running and not is_terminated:
            # 1순위: 작물 본체 이미지
            target_pos = find_image('target2.png', threshold=threshold_item)
            if target_pos:
                break
            
            # 2순위: 설명탭 이미지
            target_pos = find_image('t2.png', threshold=threshold_desc)
            if target_pos:
                break

            # 5초 초과 시 재료 소진으로 판단 후 중지
            if time.time() - start_time > 5.0:
                print("[알림] 5초 동안 재료나 설명탭을 찾지 못해 매크로를 중지합니다. (재료 소진)")
                is_running = False
                break
            
            time.sleep(0.1)

        if not is_running or target_pos is None:
            continue

        # 제자리 우클릭 수행 (랜덤 타이밍 반영)
        win32api.SetCursorPos(target_pos)
        time.sleep(0.05)
        human_right_click()
        print("[동작] 우클릭 완료 (랜덤 0.1~0.2초). 0.5초 대기 및 그릇 소멸 검증 중...")
        time.sleep(0.5)

        # 그릇 소멸 검증 (bowl.png가 사라져야 정상 안착)
        bowl_check_start = time.time()
        while check_image_exists('bowl.png'):
            if not is_running or is_terminated:
                break
            if time.time() - bowl_check_start > 2.0:
                print("[경고] 그릇이 사라지지 않았습니다. 재시도합니다.")
                break
            time.sleep(0.1)
        
        if not is_running:
            continue

        print("[진행] 재료 안착 확인. 조리 버튼 연타 시작...")

        # 조리 버튼 연타 및 UI 이탈(튕김) 감지 루프
        while is_running and not is_terminated:
            # 완료 이미지(f.png) 검증
            if check_image_exists('f.png', threshold=threshold_finish):
                print("[완료] 조리 완료 이미지 감지! 다음 루프 파트로 넘어갑니다.")
                time.sleep(0.2)
                break

            # 튕김 방어: 도마/싱크대 UI가 사라졌거나 로비 화면이 감지되면 즉시 정지
            ui_exists = check_image_exists('cutting_board.png') or check_image_exists('sink.png')
            lobby_exists = check_image_exists('lobby.png')

            if not ui_exists or lobby_exists:
                print("[위험] 서버 튕김 또는 UI 이탈 감지! 매크로를 긴급 중지합니다.")
                is_running = False
                break

            # 조리 버튼(sw2.png) 연타 (실시간 조절된 CPS 반영)
            sw_pos = find_image('sw2.png', threshold=0.75)
            if sw_pos:
                win32api.SetCursorPos(sw_pos)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            
            # CPS 기반 대기 시간 계산 (1초 / CPS)
            sleep_duration = 1.0 / current_cps if current_cps > 0 else 0.03
            time.sleep(sleep_duration)

        time.sleep(0.2)

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
    print("\n[종료] 매크로 프로그램을 완전히 종료합니다.")
    os._exit(0)

# ==================== 진입점 (Main) ====================
if __name__ == '__main__':
    check_images()
    
    # 핫키 등록
    keyboard.add_hotkey('F8', toggle_macro)
    keyboard.add_hotkey('F9', terminate_program)
    keyboard.add_hotkey('F5', adjust_threshold_menu)
    keyboard.add_hotkey('F6', decrease_cps)
    keyboard.add_hotkey('F7', increase_cps)

    # 백그라운드 스레드로 메인 루프 실행
    t = threading.Thread(target=macro_loop)
    t.daemon = True
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        terminate_program()
