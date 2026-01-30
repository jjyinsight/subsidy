# EV 보조금 크롤링 시스템 분석 보고서

## 1. 시스템 개요

| 항목 | 내용 |
|------|------|
| **대상 사이트** | ev.or.kr (환경부 무공해차 통합누리집) |
| **크롤링 도구** | **Playwright** (Python) |
| **실행 방식** | GitHub Actions 스케줄 (하루 2회) + 수동 실행 |
| **출력 형식** | CSV (UTF-8 BOM) |

---

## 2. 크롤러 구성

### 2.1 크롤러 파일 목록

| 파일 | 용도 | API 방식 |
|------|------|----------|
| `src/ev_crawler.py` | 보조금 접수현황 (전체 지역) | Playwright **동기 API** |
| `src/crawl_ev_subsidy.py` | KG모빌리티 보조금 상세 | Playwright **비동기 API** |
| `src/report_generator.py` | 변화 감지 보고서 생성 | 순수 Python |

---

## 3. 크롤러별 상세 분석

### 3.1 `ev_crawler.py` — 보조금 접수현황 크롤러

```
대상 URL: https://ev.or.kr/nportal/buySupprt/initSubsidyPaymentCheckAction.do
```

#### 크롤링 흐름

```
1. robots.txt 확인 (urllib.robotparser)
2. Playwright Chromium 브라우저 실행 (headless=True)
3. 메인 페이지 접속 → networkidle 대기
4. 차종별 탭 클릭 (전기승용, 전기화물)
   ├─ 콘텐츠 기반 대기 (wait_for_function)
   ├─ 테이블 데이터 추출
   └─ 차종 검증 후 저장
5. CSV 저장 (data/ev_subsidy_data.csv)
```

#### 데이터 추출 방식

| 항목 | 방법 |
|------|------|
| 테이블 선택 | `page.locator('table').nth(1)` |
| 행 추출 | `table.locator('tbody tr')` |
| 셀 추출 | `row.locator('td')` + `inner_text()` |
| 숫자 파싱 | 정규식 `re.findall(r'[\d,]+', text)` |

#### 수집 필드 (26개 컬럼)

```
시도, 지역구분, 차종구분, 공고파일, 접수방법,
민간공고대수_(전체/우선순위/법인기관/택시/일반),
접수대수_(전체/우선순위/법인기관/택시/일반),
출고대수_(전체/우선순위/법인기관/택시/일반),
출고잔여대수_(전체/우선순위/법인기관/택시/일반),
비고
```

---

### 3.2 `crawl_ev_subsidy.py` — KG모빌리티 보조금 크롤러

```
대상 URL: https://ev.or.kr/nportal/buySupprt/initPsLocalCarPirceAction.do
```

#### 크롤링 흐름

```
1. Playwright 비동기 브라우저 실행
2. 메인 페이지 접속
3. 연도 선택 (2026년)
4. 차종별 탭 클릭 (전기승용, 전기화물)
5. 지역별 반복:
   ├─ 조회 버튼 클릭 → 팝업 대기 (context.expect_page)
   ├─ 팝업 테이블에서 "케이지모빌리티" 필터링
   ├─ 데이터 추출
   └─ 팝업 닫기
6. CSV 저장 (data/kg_mobility_subsidy.csv)
```

#### 데이터 추출 방식

| 항목 | 방법 |
|------|------|
| 팝업 핸들링 | `context.expect_page()` |
| 지역코드 추출 | `onclick` 속성 파싱 |
| 제조사 필터 | `"케이지모빌리티" in manufacturer` |
| 셀 추출 | `query_selector_all("td")` |

#### 수집 필드 (8개 컬럼)

```
시도, 지역구분, 세부차종, 제조사, 모델명,
국비(만원), 지방비(만원), 보조금(만원)
```

---

## 4. 스케줄 및 자동화

### GitHub Actions Workflow (`.github/workflows/crawl.yml`)

| 항목 | 설정 |
|------|------|
| **실행 시간** | UTC 23:17 (KST 08:17), UTC 06:17 (KST 15:17) |
| **실행 요일** | 월-금 |
| **Runner** | ubuntu-latest |
| **Python** | 3.12 |

#### 실행 순서

```
1. Playwright 설치 (chromium + deps)
2. 이전 데이터 백업 (*_prev.csv)
3. 크롤러 실행 (crawl_ev_subsidy.py → ev_crawler.py)
4. 보고서 생성 (report_generator.py)
5. 변경사항 있으면 → 커밋 + 이메일 알림
```

---

## 5. 부하 방지 및 안정성

### Rate Limiting

| 크롤러 | 대기 시간 |
|--------|-----------|
| ev_crawler.py | `random.uniform(1.5, 3.0)초` 페이지 로드 후 |
| crawl_ev_subsidy.py | `random.uniform(0.8, 1.5)초` 팝업 로드 후 |

### 재시도 로직

```python
# ev_crawler.py
MAX_RETRIES = 3
RETRY_DELAY_SEC = 5
```

### 안정성 기법

- **콘텐츠 기반 대기**: `wait_for_function()`으로 실제 데이터 로드 확인
- **차종 검증**: 추출된 데이터의 차종이 예상값과 일치하는지 확인
- **폴백 대기**: 콘텐츠 대기 실패 시 `networkidle` 대기

---

## 6. 데이터 흐름 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (cron)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  1. crawl_ev_subsidy.py                                          │
│     └─ ev.or.kr/nportal/buySupprt/initPsLocalCarPirceAction.do  │
│        └─ Playwright async → 팝업 크롤링                         │
│           └─ data/kg_mobility_subsidy.csv                        │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. ev_crawler.py                                                │
│     └─ ev.or.kr/nportal/buySupprt/initSubsidyPaymentCheckAction.do│
│        └─ Playwright sync → 테이블 크롤링                        │
│           └─ data/ev_subsidy_data.csv                            │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. report_generator.py                                          │
│     ├─ 이전 데이터 비교 (*_prev.csv)                              │
│     ├─ 변화 감지 (민간공고대수, 출고잔여대수)                      │
│     └─ 보고서 생성 (reports/*.md, reports/*.html)                 │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  4. Git Commit + Email 알림 (CSV + HTML 첨부)                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. 법적/윤리적 준수 현황

| 항목 | 상태 | 비고 |
|------|------|------|
| robots.txt 확인 | ✅ 준수 | `check_robots_txt()` 함수 구현 |
| 접근통제 우회 | ✅ 없음 | 공개 페이지만 접근 |
| 차단 회피 | ✅ 없음 | IP 로테이션/프록시 미사용 |
| 서버 부하 | ✅ 최소화 | 랜덤 딜레이, 하루 2회 실행 |
| 개인정보 수집 | ✅ 없음 | 통계 데이터만 수집 |
| 출처 표시 | ✅ 포함 | CSV 첫 줄에 출처 명시 |

---

## 8. 기술 스택 요약

```
┌─────────────────────────────────────────┐
│              크롤링 엔진                 │
├─────────────────────────────────────────┤
│  Playwright (Python)                    │
│  - sync_api (ev_crawler.py)             │
│  - async_api (crawl_ev_subsidy.py)      │
│  - Chromium headless browser            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│              데이터 처리                 │
├─────────────────────────────────────────┤
│  - csv (표준 라이브러리)                 │
│  - re (정규식 파싱)                      │
│  - urllib.robotparser (robots.txt)      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│              자동화                      │
├─────────────────────────────────────────┤
│  - GitHub Actions (cron 스케줄)          │
│  - dawidd6/action-send-mail (이메일)     │
└─────────────────────────────────────────┘
```

---

*보고서 생성일: 2026-01-30*
