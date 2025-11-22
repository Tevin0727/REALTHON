import time
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

# ===========================
# 1. 사용자 설정 (User Configuration)
# ===========================
LOGIN_URL = "https://klue.kr/login"
YOUR_USERNAME = "YOUR_USERNAME"
YOUR_PASSWORD = "YOUR_PASSWORD"

BASE_URL = "https://klue.kr"
SEARCH_URL = f"{BASE_URL}/search?query=GELA&sort=year_term"

# 목표 학기
TARGET_YEAR = "2025"
TARGET_TERM = "1학기"
STOP_SCROLL_KEYWORD = "2024"

# 출력 폴더명
OUTPUT_FOLDER = "klue_reviews_2025"


# ===========================
# 2. 보조 함수: 파일 이름 정리
# ===========================
def sanitize_filename(name):
    """파일 이름에서 불가능한 문자 제거"""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


# ===========================
# 3. 드라이버 초기화
# ===========================
def initialize_driver():
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument('--headless') # 주석 해제 시 백그라운드 실행
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--log-level=3")

    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


# ===========================
# 4. 로그인 시뮬레이션
# ===========================
def simulate_login(driver):
    print(">>> Logging in...")
    try:
        driver.get(LOGIN_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='아이디']"))
        )
        driver.find_element(By.XPATH, "//input[@placeholder='아이디']").send_keys(YOUR_USERNAME)
        driver.find_element(By.XPATH, "//input[@placeholder='비밀번호']").send_keys(YOUR_PASSWORD)
        driver.find_element(By.XPATH, "//button[text()='로그인']").click()
        time.sleep(5)
        return True
    except Exception as e:
        print(f"Login failed: {e}")
        return False


# ===========================
# 5. 스크롤 및 검색 페이지 데이터 추출
# ===========================
def scrape_search_page(driver):
    print(">>> Accessing search page and scrolling...")
    driver.get(SEARCH_URL)

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//li[contains(@class, 'list-style_none')]"))
    )

    # --- 강제 무한 스크롤 ---
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        page_source = driver.page_source
        if STOP_SCROLL_KEYWORD in page_source:
            print(">>> 2024학기 발견 → 스크롤 중단")
            break

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print(">>> 페이지의 끝에 도달")
            break
        last_height = new_height
    # -----------------------

    course_list = []
    cards = driver.find_elements(By.XPATH, "//li[contains(@class, 'list-style_none')]")

    print(f">>> Found {len(cards)} items. Filtering for {TARGET_YEAR} {TARGET_TERM}...")

    for card in cards:
        try:
            text_content = card.text

            if TARGET_YEAR in text_content and TARGET_TERM in text_content:

                # 1. 링크 추출
                link = card.find_element(By.TAG_NAME, 'a').get_attribute('href')

                # 2. 강의명 (파일 이름용)
                try:
                    title_el = card.find_element(By.XPATH, ".//p[contains(@class, 'fs_20px')]")
                    title = title_el.text.strip()
                except:
                    title = "UnknownTitle"

                # 3. 과목 코드 정보 (내용용)
                try:
                    info_el = card.find_element(By.XPATH, ".//p[contains(@class, 'fs_14px')]")
                    info_text = info_el.text.strip()  # "2025년 1학기 COSE101(01)"
                except:
                    info_text = f"{TARGET_YEAR}년 {TARGET_TERM} UnknownCode"

                # 4. 교수명
                try:
                    prof_el = card.find_element(By.XPATH, ".//p[contains(@class, 'fs_16px')]")
                    prof_name = prof_el.text.strip()
                except:
                    prof_name = "UnknownProf"

                # 5. 평점
                try:
                    score_el = card.find_element(By.XPATH, ".//div[contains(@class, 'fs_28px')]")
                    score = score_el.text.split('/')[0].strip()
                except:
                    score = "0.0"

                course_list.append({
                    "title": title,
                    "code_info": info_text,
                    "prof": prof_name,
                    "score": score,
                    "link": link
                })
        except Exception:
            continue

    print(f">>> Collected {len(course_list)} target courses.")
    return course_list


# ===========================
# 6. 강의평 세부 페이지 리뷰 추출
# ===========================
def get_reviews(driver, url):
    driver.get(url)
    time.sleep(2)

    reviews_text = []
    try:
        review_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'white-space_pre-wrap')]")

        count = 0
        for el in review_elements:
            if count >= 10:  # 최대 10개까지만
                break
            text = el.text.strip()
            if text:
                reviews_text.append(text)
                count += 1
    except:
        pass

    return reviews_text


# ===========================
# 7. 메인 프로그램
# ===========================
def main():
    driver = initialize_driver()
    if not driver:
        return

    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir_path = os.path.join(current_dir, OUTPUT_FOLDER)

    if not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path)
        print(f">>> 폴더 생성됨: {output_dir_path}")
    else:
        print(f">>> 기존 폴더 사용: {output_dir_path}")

    try:
        if not simulate_login(driver):
            return

        courses = scrape_search_page(driver)

        for idx, course in enumerate(courses):
            print(f"Processing [{idx + 1}/{len(courses)}]: {course['title']} - {course['prof']}")

            reviews = get_reviews(driver, course['link'])

            # 1. 파일명 구성
            safe_title = sanitize_filename(course['title'])
            safe_prof = sanitize_filename(course['prof'])
            filename = f"{safe_title}_{safe_prof}_klue.txt"
            file_path = os.path.join(output_dir_path, filename)

            # 2. 첫 줄 코드에서 학기 정보 제거
            original_info = course['code_info']  # "2025년 1학기 COSE101(01)"
            prefix_to_remove = f"{TARGET_YEAR}년 {TARGET_TERM}"

            # 접두사 제거 및 공백 정리
            clean_code = original_info.replace(prefix_to_remove, "").strip()

            # 3. 파일 작성
            with open(file_path, "w", encoding="utf-8") as f:
                # Line 1: 순수 과목 코드
                f.write(f"{clean_code}\n")
                # Line 2: 교수명
                f.write(f"{course['prof']}\n")
                # Line 3: 평점
                f.write(f"평점:{course['score']}\n")
                # Line 4: 강의평 헤더
                f.write("강의평:\n")

                if not reviews:
                    f.write("No reviews available.\n")
                else:
                    for i, r in enumerate(reviews):
                        clean_review = r.replace('\n', ' ')
                        f.write(f"{i + 1}/10 {clean_review}\n")

            print(f"   -> Saved to: {filename}")

        print(f"\n>>> All Done! Files saved in folder: {OUTPUT_FOLDER}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
