#!/usr/bin/env python3
"""
ev.or.kr 케이지모빌리티 보조금 데이터 크롤링 스크립트
전기승용 + 전기화물 차량의 전체 지역 보조금 데이터를 CSV로 저장
"""

import asyncio
import csv
import random
import os
import traceback
from playwright.async_api import async_playwright, Page, BrowserContext

# 스크립트 위치 기준 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 재시도 설정
MAX_RETRIES = 3
RETRY_DELAY_SEC = 5
TABLE_LOAD_TIMEOUT_MS = 15000


async def wait_for_table_content(page: Page, description: str = "") -> bool:
    """테이블 콘텐츠 로드 대기 - 지역 링크가 있는 행이 나타날 때까지"""
    try:
        print(f"[{description}] 테이블 로드 대기 중...")
        await page.wait_for_function(
            """
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                if (rows.length === 0) return false;
                const linksFound = document.querySelectorAll("a[onclick*='psPopupLocalCarModelPrice']");
                return linksFound.length > 0;
            }
            """,
            timeout=TABLE_LOAD_TIMEOUT_MS
        )
        row_count = await page.eval_on_selector_all("table tbody tr", "rows => rows.length")
        print(f"[{description}] 테이블 로드 완료 ({row_count}행 발견)")
        return True
    except Exception as e:
        print(f"[{description}] 테이블 로드 대기 실패: {e}")
        return False


async def extract_kg_mobility_data(popup: Page, sido: str, district: str, vehicle_category: str) -> list[dict]:
    """팝업 테이블에서 케이지모빌리티 데이터 추출"""
    results = []

    await popup.wait_for_load_state("load")
    await asyncio.sleep(random.uniform(0.8, 1.5))

    rows = await popup.query_selector_all("table tbody tr")

    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) < 6:
            continue

        vehicle_type = await cells[0].inner_text()
        manufacturer = await cells[1].inner_text()
        manufacturer = manufacturer.strip()

        # 케이지모빌리티 필터링
        if "케이지모빌리티" not in manufacturer and "KG모빌리티" not in manufacturer:
            continue

        model = await cells[2].inner_text()
        national_subsidy = await cells[3].inner_text()
        local_subsidy = await cells[4].inner_text()
        total_subsidy = await cells[5].inner_text()

        results.append({
            "시도": sido,
            "지역구분": district,
            "세부차종": vehicle_category,
            "제조사": manufacturer.strip(),
            "모델명": model.strip(),
            "국비(만원)": national_subsidy.strip().replace(",", ""),
            "지방비(만원)": local_subsidy.strip().replace(",", ""),
            "보조금(만원)": total_subsidy.strip().replace(",", ""),
        })

    return results


async def get_region_links(page: Page, vehicle_category: str = "") -> list[tuple[str, str, str]]:
    """지역 링크 정보 수집 (지역코드, 시도, 지역구분) - 재시도 로직 포함"""

    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            print(f"[{vehicle_category}] 재시도 {attempt}/{MAX_RETRIES-1} ({RETRY_DELAY_SEC}초 대기 후)...")
            await asyncio.sleep(RETRY_DELAY_SEC)

        content_loaded = await wait_for_table_content(page, vehicle_category)
        if not content_loaded:
            print(f"[{vehicle_category}] 테이블 로드 실패 - 재시도 예정")
            continue

        rows = await page.query_selector_all("table tbody tr")
        region_info = []

        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) >= 3:
                sido = await cells[0].inner_text()
                district = await cells[1].inner_text()

                link = await row.query_selector("a[onclick*='psPopupLocalCarModelPrice']")
                if link:
                    onclick = await link.get_attribute("onclick")
                    if onclick:
                        parts = onclick.split("'")
                        region_code = parts[3] if len(parts) >= 4 else ""
                        region_info.append((region_code, sido.strip(), district.strip()))

        print(f"[{vehicle_category}] 시도 {attempt+1}: {len(region_info)}개 지역 발견")

        if len(region_info) > 0:
            return region_info

        print(f"[{vehicle_category}] 지역 없음 - 재시도 예정")

    raise RuntimeError(f"[{vehicle_category}] {MAX_RETRIES}회 시도 후에도 지역을 찾지 못함 - 크롤링 중단")


async def crawl_vehicle_type(page: Page, context: BrowserContext, vehicle_category: str, tab_text: str) -> list[dict]:
    """특정 차종(전기승용/전기화물)의 전체 지역 데이터 크롤링"""
    all_data = []

    # 해당 탭 클릭
    print(f"\n[{vehicle_category}] 탭 선택 중...")
    await page.click(f"text={tab_text}")
    await asyncio.sleep(random.uniform(1.5, 2.5))

    region_links = await get_region_links(page, vehicle_category)
    region_count = len(region_links)
    print(f"[{vehicle_category}] 총 {region_count}개 지역 크롤링 시작")

    for i, (region_code, sido, district) in enumerate(region_links):
        print(f"  [{i+1}/{region_count}] {sido} {district} 조회 중...", end=" ", flush=True)

        try:
            # 팝업 대기 설정
            async with context.expect_page(timeout=15000) as popup_info:
                # 해당 지역 조회 버튼 클릭
                await page.click(f"a[onclick*=\"psPopupLocalCarModelPrice('{page.url.split('year1=')[-1][:4] if 'year1=' in page.url else '2026'}','{region_code}'\"]")

            popup = await popup_info.value
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # 데이터 추출
            data = await extract_kg_mobility_data(popup, sido, district, vehicle_category)

            # 차종 검증
            validated_data = [d for d in data if vehicle_category in d.get("세부차종", "")]
            if len(validated_data) != len(data):
                print(f"  경고: {len(data) - len(validated_data)}건 차종 불일치로 제외")

            all_data.extend(validated_data)
            print(f"케이지모빌리티 {len(validated_data)}건")

            # 팝업 닫기
            await popup.close()

        except Exception as e:
            print(f"오류 발생: {sido} {district}")
            print(f"  에러 타입: {type(e).__name__}")
            print(f"  에러 메시지: {str(e)}")
            print(f"  스택 트레이스:")
            print(traceback.format_exc())
            # 열린 팝업이 있으면 닫기
            try:
                pages = context.pages
                for p in pages[1:]:
                    await p.close()
            except Exception:
                pass
            continue

    return all_data


async def crawl_all_regions(page: Page, context: BrowserContext, vehicle_category: str) -> list[dict]:
    """전체 지역 크롤링 (개선된 버전)"""
    all_data = []

    region_links = await get_region_links(page, vehicle_category)
    region_count = len(region_links)
    print(f"[{vehicle_category}] 총 {region_count}개 지역 크롤링 시작")

    for i, (region_code, sido, district) in enumerate(region_links):
        print(f"  [{i+1}/{region_count}] {sido} {district} 조회 중...", end=" ", flush=True)

        try:
            # 팝업 대기 설정
            async with context.expect_page(timeout=15000) as popup_info:
                # 해당 지역 조회 버튼 클릭 (JavaScript evaluate 사용)
                await page.evaluate(f"psPopupLocalCarModelPrice('2026','{region_code}','{district}')")

            popup = await popup_info.value
            await asyncio.sleep(random.uniform(0.8, 1.5))

            # 데이터 추출
            data = await extract_kg_mobility_data(popup, sido, district, vehicle_category)

            # 차종 검증
            validated_data = [d for d in data if vehicle_category in d.get("세부차종", "")]
            if len(validated_data) != len(data):
                print(f"  경고: {len(data) - len(validated_data)}건 차종 불일치로 제외")

            all_data.extend(validated_data)
            print(f"케이지모빌리티 {len(validated_data)}건")

            # 팝업 닫기
            await popup.close()

        except Exception as e:
            print(f"오류 발생: {sido} {district}")
            print(f"  에러 타입: {type(e).__name__}")
            print(f"  에러 메시지: {str(e)}")
            print(f"  스택 트레이스:")
            print(traceback.format_exc())
            # 열린 팝업이 있으면 닫기
            try:
                pages = context.pages
                for p in pages[1:]:
                    await p.close()
            except Exception:
                pass
            continue

        await asyncio.sleep(random.uniform(0.2, 0.5))

    return all_data


async def main():
    print("=" * 60)
    print("ev.or.kr 케이지모빌리티 보조금 데이터 크롤링")
    print("=" * 60)

    all_results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 메인 페이지 접속
        print("\n메인 페이지 접속 중...")
        await page.goto("https://ev.or.kr/nportal/buySupprt/initPsLocalCarPirceAction.do")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # 2026년 선택
        print("기준년도: 2026년 선택")
        await page.select_option("select#year1", "2026")
        await asyncio.sleep(random.uniform(1.5, 2.5))

        print("\n[전기승용] 탭 선택 중...")
        await page.click("text=전기승용")
        content_loaded = await wait_for_table_content(page, "전기승용")
        if not content_loaded:
            print("[전기승용] 콘텐츠 대기 실패 - 폴백 대기 사용")
            await asyncio.sleep(5)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        passenger_data = await crawl_all_regions(page, context, "전기승용")
        all_results.extend(passenger_data)

        print("\n[전기화물] 탭 선택 중...")
        await page.click("text=전기화물")
        content_loaded = await wait_for_table_content(page, "전기화물")
        if not content_loaded:
            print("[전기화물] 콘텐츠 대기 실패 - 폴백 대기 사용")
            await asyncio.sleep(5)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        cargo_data = await crawl_all_regions(page, context, "전기화물")
        all_results.extend(cargo_data)

        await browser.close()

    # CSV 저장 (BOM 포함 UTF-8 - 엑셀 호환)
    output_file = os.path.join(DATA_DIR, "kg_mobility_subsidy.csv")
    fieldnames = ["시도", "지역구분", "세부차종", "제조사", "모델명", "국비(만원)", "지방비(만원)", "보조금(만원)"]

    # data 폴더 자동 생성
    os.makedirs(DATA_DIR, exist_ok=True)

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    # 결과 요약
    print("\n" + "=" * 60)
    print("크롤링 완료!")
    print("=" * 60)

    passenger_count = len([r for r in all_results if r["세부차종"] == "전기승용"])
    cargo_count = len([r for r in all_results if r["세부차종"] == "전기화물"])

    print(f"전기승용: {passenger_count}건")
    print(f"전기화물: {cargo_count}건")
    print(f"총 데이터: {len(all_results)}건")
    print(f"\n저장 파일: {output_file} (utf-8-sig 인코딩)")


if __name__ == "__main__":
    asyncio.run(main())
