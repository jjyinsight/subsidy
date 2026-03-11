#!/usr/bin/env python3
"""
크롤링 실행 여부 판단 모듈

.crawl_state.json을 읽어 현재 모드를 계산하고,
모드/요일/시간에 따라 크롤링 실행 여부를 결정한다.

모드 전환 규칙:
  Active (30일) → Slowing (14일) → Dormant (주1회)
  트리거 재감지 시 즉시 Active 복귀
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import holidays

KST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, ".crawl_state.json")

ACTIVE_DAYS = 30
SLOWING_DAYS = 14


def load_state() -> dict:
    """상태 파일 로드. 없으면 기본 Active 상태 반환."""
    if not os.path.exists(STATE_FILE):
        return {
            "last_trigger_date": datetime.now(KST).strftime("%Y-%m-%d"),
            "trigger_reason": "초기 상태 - 파일 없음",
            "mode": "active",
        }
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict):
    """상태 파일 저장."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def calculate_mode(state: dict, now: datetime) -> str:
    """last_trigger_date 기준으로 현재 모드를 계산."""
    try:
        trigger_date = datetime.strptime(state["last_trigger_date"], "%Y-%m-%d").replace(
            tzinfo=KST
        )
    except (KeyError, ValueError):
        return "active"

    days_since = (now - trigger_date).days

    if days_since <= ACTIVE_DAYS:
        return "active"
    elif days_since <= ACTIVE_DAYS + SLOWING_DAYS:
        return "slowing"
    else:
        return "dormant"


def is_holiday(date) -> bool:
    """한국 공휴일 여부 확인."""
    kr = holidays.KR()
    return date in kr


def is_morning_slot(now: datetime) -> bool:
    """오전 크롤링 시간대(KST 7-10시) 여부."""
    hour = now.hour
    return 7 <= hour <= 10


def should_crawl(event_name: str = "") -> dict:
    """
    크롤링 실행 여부를 판단한다.

    Returns:
        dict with keys:
            should_crawl: "true" or "false"
            crawl_reason: 판단 사유
            current_mode: 현재 모드
            mode_changed: "true" or "false"
            prev_mode: 이전 모드 (mode_changed=true일 때)
            new_mode: 새 모드 (mode_changed=true일 때)
    """
    now = datetime.now(KST)
    today = now.date()
    weekday = now.weekday()  # 0=Monday

    result = {
        "should_crawl": "false",
        "crawl_reason": "",
        "current_mode": "",
        "mode_changed": "false",
        "prev_mode": "",
        "new_mode": "",
    }

    # 수동 실행은 항상 크롤링
    if event_name == "workflow_dispatch":
        state = load_state()
        result["current_mode"] = calculate_mode(state, now)
        result["should_crawl"] = "true"
        result["crawl_reason"] = "수동 실행 (workflow_dispatch)"
        return result

    # 공휴일 스킵
    if is_holiday(today):
        kr = holidays.KR()
        result["crawl_reason"] = f"공휴일 스킵: {kr[today]}"
        state = load_state()
        result["current_mode"] = calculate_mode(state, now)
        return result

    # 상태 파일 읽기 + 모드 계산
    state = load_state()
    stored_mode = state.get("mode", "active")
    computed_mode = calculate_mode(state, now)

    result["current_mode"] = computed_mode

    # 모드 다운그레이드 감지
    mode_order = {"active": 0, "slowing": 1, "dormant": 2}
    if mode_order.get(computed_mode, 0) > mode_order.get(stored_mode, 0):
        result["mode_changed"] = "true"
        result["prev_mode"] = stored_mode
        result["new_mode"] = computed_mode

        # 상태 파일 갱신 (모드만 업데이트, trigger_date는 유지)
        state["mode"] = computed_mode
        save_state(state)

    # 모드별 크롤링 실행 판단
    if computed_mode == "active":
        # Active: 하루 2회 (기존 cron 스케줄 그대로)
        result["should_crawl"] = "true"
        result["crawl_reason"] = f"Active 모드 - 하루 2회 크롤링"

    elif computed_mode == "slowing":
        # Slowing: 하루 1회 (오전만)
        if is_morning_slot(now):
            result["should_crawl"] = "true"
            result["crawl_reason"] = "Slowing 모드 - 오전 1회 크롤링"
        else:
            result["crawl_reason"] = "Slowing 모드 - 오후 스킵"

    elif computed_mode == "dormant":
        # Dormant: 주 1회 (월요일 오전)
        if weekday == 0 and is_morning_slot(now):
            result["should_crawl"] = "true"
            result["crawl_reason"] = "Dormant 모드 - 월요일 오전 크롤링"
        else:
            result["crawl_reason"] = f"Dormant 모드 - 월요일 오전만 실행 (현재: {'월화수목금토일'[weekday]}요일)"

    return result


def main():
    """GitHub Actions에서 호출. 결과를 $GITHUB_OUTPUT에 출력."""
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    github_output = os.environ.get("GITHUB_OUTPUT", "")

    result = should_crawl(event_name)

    # 콘솔 출력 (로그용)
    print(f"현재 모드: {result['current_mode']}")
    print(f"크롤링 실행: {result['should_crawl']}")
    print(f"사유: {result['crawl_reason']}")
    if result["mode_changed"] == "true":
        print(f"모드 변경: {result['prev_mode']} → {result['new_mode']}")

    # $GITHUB_OUTPUT에 출력
    if github_output:
        with open(github_output, "a") as f:
            for key, value in result.items():
                f.write(f"{key}={value}\n")
    else:
        # 로컬 테스트용
        for key, value in result.items():
            print(f"  {key}={value}")


if __name__ == "__main__":
    main()
