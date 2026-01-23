#!/usr/bin/env python3
"""
EV 보조금 데이터 변화 보고서 생성 모듈
ev_subsidy_data.csv와 kg_mobility_subsidy.csv의 변화를 분석하여 보고서 생성
"""

import csv
import os
from datetime import datetime
from collections import defaultdict


# 스크립트 위치 기준 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


class EVSubsidyReportGenerator:
    """ev_subsidy_data.csv 보고서 생성기"""

    def __init__(self):
        self.current_file = os.path.join(DATA_DIR, "ev_subsidy_data.csv")
        self.prev_file = os.path.join(DATA_DIR, "ev_subsidy_data_prev.csv")

    def load_data(self, filepath: str) -> list[dict]:
        """CSV 파일 로드"""
        if not os.path.exists(filepath):
            return []

        data = []
        # 여러 인코딩 시도
        encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
        for encoding in encodings:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    # 첫 번째 행이 주석인 경우 건너뛰기
                    for row in reader:
                        # 시도 컬럼이 #으로 시작하면 건너뛰기 (주석 행)
                        if row.get("시도", "").startswith("#"):
                            continue
                        data.append(row)
                return data
            except UnicodeDecodeError:
                continue
        return data

    def generate_summary(self, data: list[dict]) -> dict:
        """시도/차종별 현황 요약"""
        summary = defaultdict(lambda: {"지역수": 0, "민간공고대수_일반": 0, "출고잔여대수_전체": 0})

        for row in data:
            key = (row.get("시도", ""), row.get("차종구분", ""))
            summary[key]["지역수"] += 1

            try:
                summary[key]["민간공고대수_일반"] += int(row.get("민간공고대수_일반", 0) or 0)
            except ValueError:
                pass

            try:
                summary[key]["출고잔여대수_전체"] += int(row.get("출고잔여대수_전체", 0) or 0)
            except ValueError:
                pass

        return summary

    def detect_changes(self, current_data: list[dict], prev_data: list[dict]) -> list[dict]:
        """이전 데이터 대비 유의미한 변화 감지"""
        changes = []

        # 현재 데이터를 키로 매핑
        current_map = {}
        for row in current_data:
            key = (row.get("시도", ""), row.get("지역구분", ""), row.get("차종구분", ""))
            current_map[key] = row

        # 이전 데이터를 키로 매핑
        prev_map = {}
        for row in prev_data:
            key = (row.get("시도", ""), row.get("지역구분", ""), row.get("차종구분", ""))
            prev_map[key] = row

        # 변화 감지 (민간공고대수_일반, 출고잔여대수_전체)
        check_fields = ["민간공고대수_일반", "출고잔여대수_전체"]

        for key, current_row in current_map.items():
            if key in prev_map:
                prev_row = prev_map[key]
                for field in check_fields:
                    try:
                        current_val = int(current_row.get(field, 0) or 0)
                        prev_val = int(prev_row.get(field, 0) or 0)
                        diff = current_val - prev_val

                        if diff != 0:
                            changes.append({
                                "시도": key[0],
                                "지역": key[1],
                                "차종": key[2],
                                "항목": field,
                                "이전": prev_val,
                                "현재": current_val,
                                "변화": diff
                            })
                    except ValueError:
                        continue

        return changes

    def generate_report(self) -> list[str]:
        """보고서 생성"""
        lines = []

        current_data = self.load_data(self.current_file)
        prev_data = self.load_data(self.prev_file)

        lines.append("## EV 보조금 현황 요약 (ev_subsidy_data)")
        lines.append("")

        if not current_data:
            lines.append("데이터가 없습니다.")
            lines.append("")
            return lines

        # 시도/차종별 현황
        lines.append("### 시도/차종별 현황")
        lines.append("| 시도 | 차종 | 지역수 | 민간공고대수_일반 합계 | 출고잔여대수_전체 합계 |")
        lines.append("|------|------|--------|------------------------|------------------------|")

        summary = self.generate_summary(current_data)
        for (sido, vehicle_type), stats in sorted(summary.items()):
            lines.append(f"| {sido} | {vehicle_type} | {stats['지역수']} | {stats['민간공고대수_일반']:,} | {stats['출고잔여대수_전체']:,} |")

        lines.append("")

        # 유의미한 변화 감지
        if prev_data:
            changes = self.detect_changes(current_data, prev_data)
            if changes:
                lines.append("### 유의미한 변화")
                lines.append("| 시도 | 지역 | 차종 | 항목 | 이전 | 현재 | 변화 |")
                lines.append("|------|------|------|------|------|------|------|")

                for change in sorted(changes, key=lambda x: abs(x["변화"]), reverse=True)[:20]:
                    diff_text = f"+{change['변화']}대 증가" if change["변화"] > 0 else f"{change['변화']}대 감소"
                    lines.append(f"| {change['시도']} | {change['지역']} | {change['차종']} | {change['항목']} | {change['이전']:,} | {change['현재']:,} | {diff_text} |")

                lines.append("")
            else:
                lines.append("### 유의미한 변화")
                lines.append("변화 없음")
                lines.append("")
        else:
            lines.append("### 유의미한 변화")
            lines.append("이전 데이터가 없어 비교할 수 없습니다.")
            lines.append("")

        return lines


class KGMobilityReportGenerator:
    """kg_mobility_subsidy.csv 보고서 생성기"""

    def __init__(self):
        self.current_file = os.path.join(DATA_DIR, "kg_mobility_subsidy.csv")
        self.prev_file = os.path.join(DATA_DIR, "kg_mobility_subsidy_prev.csv")

    def load_data(self, filepath: str) -> list[dict]:
        """CSV 파일 로드"""
        if not os.path.exists(filepath):
            return []

        data = []
        # 여러 인코딩 시도
        encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
        for encoding in encodings:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data.append(row)
                return data
            except UnicodeDecodeError:
                continue
        return data

    def get_regions_by_sido(self, data: list[dict]) -> dict[str, set[str]]:
        """시도별 지역구분 목록 (중복 제거)"""
        regions = defaultdict(set)
        for row in data:
            sido = row.get("시도", "")
            district = row.get("지역구분", "")
            # 이전 형식("지역" 컬럼만 있는 경우) 처리
            if not sido and "지역" in row:
                # 지역명에서 시도 추출 시도 (예: "서울특별시" -> "서울")
                region = row.get("지역", "")
                regions["미분류"].add(region)
            elif sido and district:
                regions[sido].add(district)
        return regions

    def detect_new_regions(self, current_data: list[dict], prev_data: list[dict]) -> dict[str, list[str]]:
        """새로 추가된 지역 감지"""
        current_regions = self.get_regions_by_sido(current_data)
        prev_regions = self.get_regions_by_sido(prev_data)

        new_regions = {}
        for sido, districts in current_regions.items():
            prev_districts = prev_regions.get(sido, set())
            added = districts - prev_districts
            if added:
                new_regions[sido] = sorted(added)

        return new_regions

    def generate_report(self) -> list[str]:
        """보고서 생성"""
        lines = []

        current_data = self.load_data(self.current_file)
        prev_data = self.load_data(self.prev_file)

        lines.append("## KG 모빌리티 보조금 현황 (kg_mobility_subsidy)")
        lines.append("")

        if not current_data:
            lines.append("데이터가 없습니다.")
            lines.append("")
            return lines

        # 시도별 지역 현황
        lines.append("### 시도별 지역 현황 (중복제거)")
        lines.append("| 시도 | 지역 수 | 지역구분 목록 |")
        lines.append("|------|---------|---------------|")

        regions_by_sido = self.get_regions_by_sido(current_data)
        for sido in sorted(regions_by_sido.keys()):
            districts = regions_by_sido[sido]
            district_list = ", ".join(sorted(districts)[:10])
            if len(districts) > 10:
                district_list += f" 외 {len(districts) - 10}개"
            lines.append(f"| {sido} | {len(districts)} | {district_list} |")

        lines.append("")

        # 총 데이터 건수
        lines.append(f"**총 데이터 건수**: {len(current_data)}건")
        lines.append("")

        # 새로 추가된 지역
        if prev_data:
            new_regions = self.detect_new_regions(current_data, prev_data)
            if new_regions:
                lines.append("### 새로 추가된 지역")
                lines.append("| 시도 | 추가 지역 수 | 추가된 지역구분 |")
                lines.append("|------|--------------|-----------------|")

                for sido in sorted(new_regions.keys()):
                    added = new_regions[sido]
                    lines.append(f"| {sido} | {len(added)} | {', '.join(added)} |")

                lines.append("")
            else:
                lines.append("### 새로 추가된 지역")
                lines.append("새로 추가된 지역 없음")
                lines.append("")
        else:
            lines.append("### 새로 추가된 지역")
            lines.append("이전 데이터가 없어 비교할 수 없습니다.")
            lines.append("")

        return lines


def generate_full_report() -> str:
    """전체 보고서 생성"""
    now = datetime.now()

    lines = []
    lines.append("# EV 보조금 데이터 변화 보고서")
    lines.append(f"**보고서 생성일시**: {now.strftime('%Y년 %m월 %d일 %H:%M:%S')}")
    lines.append(f"**데이터 기준일**: {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # EV 보조금 보고서
    ev_generator = EVSubsidyReportGenerator()
    lines.extend(ev_generator.generate_report())

    lines.append("---")
    lines.append("")

    # KG 모빌리티 보고서
    kg_generator = KGMobilityReportGenerator()
    lines.extend(kg_generator.generate_report())

    return "\n".join(lines)


def save_report(content: str) -> str:
    """보고서를 파일로 저장"""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    now = datetime.now()
    filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}.md"
    filepath = os.path.join(REPORTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def main():
    print("=" * 60)
    print("EV 보조금 데이터 변화 보고서 생성")
    print("=" * 60)

    report_content = generate_full_report()
    filepath = save_report(report_content)

    print(f"\n보고서 생성 완료: {filepath}")
    print("\n" + "=" * 60)
    print("보고서 내용 미리보기:")
    print("=" * 60)
    print(report_content[:2000])
    if len(report_content) > 2000:
        print("\n... (이하 생략)")


if __name__ == "__main__":
    main()
