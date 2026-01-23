#!/usr/bin/env python3
"""
ev.or.kr 케이지모빌리티 보조금 데이터 크롤링 스크립트
전기승용 + 전기화물 차량의 전체 지역 보조금 데이터를 CSV로 저장
"""

import asyncio
import csv
import random
import os
from playwright.async_api import async_playwright, Page, BrowserContext

# 스크립트 위치 기준 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


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


async def get_region_links(page: Page) -> list[tuple[str, str, str]]:
    """지역 링크 정보 수집 (지역코드, 시도, 지역구분)"""
    rows = await page.query_selector_all("table tbody tr")
    region_info = []

    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) >= 3:
            sido = await cells[0].inner_text()      # 시도 (예: 경기)
            district = await cells[1].inner_text()  # 지역구분 (예: 수원시)

            # onclick에서 지역코드 추출
            link = await row.query_selector("a[onclick*='psPopupLocalCarModelPrice']")
            if link:
                onclick = await link.get_attribute("onclick")
                if onclick:
                    parts = onclick.split("'")
                    region_code = parts[3] if len(parts) >= 4 else ""
                    region_info.append((region_code, sido.strip(), district.strip()))

    return region_info


async def crawl_vehicle_type(page: Page, context: BrowserContext, vehicle_category: str, tab_text: str) -> list[dict]:
    """특정 차종(전기승용/전기화물)의 전체 지역 데이터 크롤링"""
    all_data = []

    # 해당 탭 클릭
    print(f"\n[{vehicle_category}] 탭 선택 중...")
    await page.click(f"text={tab_text}")
    await asyncio.sleep(random.uniform(1.5, 2.5))

    # 지역 링크 정보 가져오기 (지역코드, 시도, 지역구분)
    region_links = await get_region_links(page)
    region_count = len(region_links)
    print(f"[{vehicle_category}] 총 {region_count}개 지역 발견")

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
            all_data.extend(data)
            print(f"케이지모빌리티 {len(data)}건")

            # 팝업 닫기
            await popup.close()

        except Exception as e:
            print(f"오류: {str(e)[:50]}")
            # 열린 팝업이 있으면 닫기
            try:
                pages = context.pages
                for p in pages[1:]:
                    await p.close()
            except:
                pass
            continue

        await asyncio.sleep(random.uniform(0.2, 0.5))

    return all_data


async def crawl_all_regions(page: Page, context: BrowserContext, vehicle_category: str) -> list[dict]:
    """전체 지역 크롤링 (개선된 버전)"""
    all_data = []

    # 지역 링크 정보 가져오기 (지역코드, 시도, 지역구분)
    region_links = await get_region_links(page)
    region_count = len(region_links)
    print(f"[{vehicle_category}] 총 {region_count}개 지역 발견")

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
            all_data.extend(data)
            print(f"케이지모빌리티 {len(data)}건")

            # 팝업 닫기
            await popup.close()

        except Exception as e:
            print(f"오류: {str(e)[:50]}")
            # 열린 팝업이 있으면 닫기
            try:
                pages = context.pages
                for p in pages[1:]:
                    await p.close()
            except:
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

        # 전기승용 크롤링 (기본 탭 - 먼저 명시적으로 클릭)
        print("\n[전기승용] 탭 선택 중...")
        await page.click("text=전기승용")
        await asyncio.sleep(random.uniform(1.5, 2.5))
        passenger_data = await crawl_all_regions(page, context, "전기승용")
        all_results.extend(passenger_data)

        # 전기화물 크롤링
        print("\n[전기화물] 탭 선택 중...")
        await page.click("text=전기화물")
        await asyncio.sleep(random.uniform(1.5, 2.5))
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
