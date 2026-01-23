#!/usr/bin/env python3
"""
ev.or.kr 전기차 보조금 데이터 크롤러
페이지에서 테이블의 모든 행/열 데이터를 추출하여 CSV로 저장
숫자 데이터는 분리된 컬럼으로 저장
"""

from playwright.sync_api import sync_playwright
import csv
import re
import random
import urllib.robotparser
import urllib.request
import urllib.error
import os

URL = "https://ev.or.kr/nportal/buySupprt/initSubsidyPaymentCheckAction.do"

# 스크립트 위치 기준 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCREENSHOT_PATH = os.path.join(DATA_DIR, "ev_page.png")
CSV_PATH = os.path.join(DATA_DIR, "ev_subsidy_data.csv")

# 수집할 차종 목록
VEHICLE_TYPES = ['전기승용', '전기화물']

# 출처 정보
DATA_SOURCE = "데이터 출처: 환경부 무공해차 통합누리집(ev.or.kr)"


def check_robots_txt():
    """
    robots.txt를 확인하여 크롤링 허용 여부를 체크합니다.
    - robots.txt가 없거나 접근 불가 시 경고 출력 후 계속 진행
    - 명시적으로 Disallow된 경우 경고 출력

    Returns:
        bool: 크롤링 허용 여부 (True: 허용, False: 비허용)
    """
    robots_url = "https://ev.or.kr/robots.txt"
    target_path = "/nportal/buySupprt/initSubsidyPaymentCheckAction.do"

    print(f"robots.txt 확인 중: {robots_url}")

    try:
        # robots.txt 접근 시도
        req = urllib.request.Request(
            robots_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; EVCrawler/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            robots_content = response.read().decode('utf-8')

        # robotparser로 파싱
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(robots_content.splitlines())

        # 크롤링 대상 경로 확인
        is_allowed = rp.can_fetch('*', target_path)

        if is_allowed:
            print(f"  → robots.txt 확인 완료: 크롤링 허용됨")
        else:
            print(f"  → 경고: robots.txt에서 해당 경로가 Disallow되어 있습니다.")
            print(f"     경로: {target_path}")

        return is_allowed

    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  → robots.txt 없음 (404): 크롤링 제한 없음으로 간주")
        else:
            print(f"  → robots.txt 접근 오류 (HTTP {e.code}): 크롤링 계속 진행")
        return True

    except urllib.error.URLError as e:
        print(f"  → robots.txt 접근 불가 ({e.reason}): 크롤링 계속 진행")
        return True

    except Exception as e:
        print(f"  → robots.txt 확인 중 오류 ({type(e).__name__}): 크롤링 계속 진행")
        return True


def parse_numbers(text):
    """
    '10500 (1600) (0) (0) (8900)' 형태의 텍스트를 파싱하여 숫자 리스트 반환
    [전체, 우선순위, 법인기관, 택시, 일반]
    """
    if not text or text.strip() == '':
        return ['', '', '', '', '']

    # 숫자 추출 (괄호 포함)
    numbers = re.findall(r'[\d,]+', text)

    if not numbers:
        return ['', '', '', '', '']

    # 숫자에서 콤마 제거
    numbers = [n.replace(',', '') for n in numbers]

    # 5개 값으로 패딩
    while len(numbers) < 5:
        numbers.append('')

    return numbers[:5]


def extract_table_data(page):
    """
    현재 페이지의 테이블에서 데이터를 추출하여 리스트로 반환
    """
    # 메인 데이터 테이블 선택 (테이블 인덱스 1)
    tables = page.locator('table')
    main_table = tables.nth(1)

    # 데이터 행 추출
    data_rows = main_table.locator('tbody tr')
    row_count = data_rows.count()
    print(f"  테이블 행 수: {row_count}")

    data = []
    for i in range(row_count):
        row = data_rows.nth(i)
        cells = row.locator('td')
        cell_count = cells.count()

        if cell_count == 0:
            continue

        raw_data = []
        for j in range(cell_count):
            text = cells.nth(j).inner_text().strip()
            text = re.sub(r'\s+', ' ', text)
            raw_data.append(text)

        # 데이터가 있는 행만 처리 (최소 10개 컬럼 필요)
        if len(raw_data) >= 10:
            # 원본 구조: [시도, 지역, 차종, 공고파일, 접수방법, 민간공고대수, 접수대수, 출고대수, 출고잔여대수, 비고]
            parsed_row = raw_data[:5]  # 시도, 지역, 차종, 공고파일, 접수방법

            # 민간공고대수 파싱
            parsed_row.extend(parse_numbers(raw_data[5]))
            # 접수대수 파싱
            parsed_row.extend(parse_numbers(raw_data[6]))
            # 출고대수 파싱
            parsed_row.extend(parse_numbers(raw_data[7]))
            # 출고잔여대수 파싱
            parsed_row.extend(parse_numbers(raw_data[8]))

            # 비고
            parsed_row.append(raw_data[9] if len(raw_data) > 9 else '')

            # 민간공고대수_전체에 숫자가 있는 행만 저장
            if parsed_row[5] and parsed_row[5].strip():
                data.append(parsed_row)

    return data


def crawl_ev_subsidy():
    # robots.txt 확인
    check_robots_txt()
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"페이지 접속 중: {URL}")
        page.goto(URL, timeout=60000)
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(int(random.uniform(1.5, 3.0) * 1000))

        # 스크린샷 저장
        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        print(f"스크린샷 저장: {SCREENSHOT_PATH}")
        print(f"페이지 타이틀: {page.title()}")

        # 확장된 헤더 (숫자 데이터 분리)
        final_headers = [
            '시도', '지역구분', '차종구분', '공고파일', '접수방법',
            '민간공고대수_전체', '민간공고대수_우선순위', '민간공고대수_법인기관', '민간공고대수_택시', '민간공고대수_일반',
            '접수대수_전체', '접수대수_우선순위', '접수대수_법인기관', '접수대수_택시', '접수대수_일반',
            '출고대수_전체', '출고대수_우선순위', '출고대수_법인기관', '출고대수_택시', '출고대수_일반',
            '출고잔여대수_전체', '출고잔여대수_우선순위', '출고잔여대수_법인기관', '출고잔여대수_택시', '출고잔여대수_일반',
            '비고'
        ]

        # 전체 데이터 저장 리스트
        all_data = []

        # 차종별 데이터 수집
        for vtype in VEHICLE_TYPES:
            print(f"\n[{vtype}] 버튼 클릭 중...")

            # 차종 버튼 클릭 (링크 버튼으로 특정)
            button = page.get_by_role("link", name=vtype, exact=True)
            button.click()

            # 테이블 데이터 로딩 완료 대기
            # 버튼 클릭 후 테이블이 일시적으로 비워졌다가 새 데이터가 로드됨
            page.wait_for_load_state('networkidle')

            # 테이블이 비워지는 것을 감지 (최대 5초)
            # 이전 데이터가 남아있을 수 있으므로 테이블이 비워질 때까지 대기
            main_table = page.locator('table').nth(1)
            for _ in range(10):
                row_count = main_table.locator('tbody tr').count()
                if row_count == 0:
                    break
                page.wait_for_timeout(500)

            # 테이블에 새 데이터가 나타날 때까지 대기 (최대 10초)
            for _ in range(20):
                row_count = main_table.locator('tbody tr').count()
                if row_count > 0:
                    break
                page.wait_for_timeout(500)

            page.wait_for_timeout(int(random.uniform(0.5, 1.0) * 1000))

            print(f"[{vtype}] 데이터 추출 중...")
            data = extract_table_data(page)
            print(f"[{vtype}] 추출된 행: {len(data)}개")

            all_data.extend(data)

        print(f"\n전체 데이터: {len(all_data)}행")

        # 데이터 미리보기
        if all_data:
            print("\n데이터 미리보기 (처음 5행):")
            for idx, row in enumerate(all_data[:5]):
                print(f"  행 {idx+1}: 시도={row[0]}, 지역={row[1]}, 차종={row[2]}")
                print(f"         민간공고대수: 전체={row[5]}, 우선={row[6]}, 법인={row[7]}, 택시={row[8]}, 일반={row[9]}")
                print(f"         출고잔여대수: 전체={row[20]}, 우선={row[21]}, 법인={row[22]}, 택시={row[23]}, 일반={row[24]}")

        # data 폴더 자동 생성
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

        # CSV 저장 (출처 정보 포함, BOM 포함 UTF-8로 엑셀 호환)
        with open(CSV_PATH, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            # 출처 정보를 첫 번째 행에 추가
            writer.writerow([f"# {DATA_SOURCE}"])
            writer.writerow(final_headers)
            writer.writerows(all_data)

        print(f"\nCSV 저장 완료: {CSV_PATH}")
        print(f"총 {len(all_data)}행 x {len(final_headers)}열")

        # 차종별 집계
        print("\n차종별 데이터 행 수:")
        vehicle_counts = {}
        for row in all_data:
            vtype = row[2]
            vehicle_counts[vtype] = vehicle_counts.get(vtype, 0) + 1
        for v, c in sorted(vehicle_counts.items()):
            print(f"  {v}: {c}행")

        # 시도별 집계
        print("\n시도별 데이터 행 수:")
        province_counts = {}
        for row in all_data:
            province = row[0]
            province_counts[province] = province_counts.get(province, 0) + 1
        for p, c in sorted(province_counts.items()):
            print(f"  {p}: {c}행")

        browser.close()
        return final_headers, all_data


if __name__ == "__main__":
    crawl_ev_subsidy()
