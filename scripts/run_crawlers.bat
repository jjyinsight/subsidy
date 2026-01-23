@echo off
chcp 65001 >nul
title EV 크롤러 실행기

echo === EV 보조금 크롤러 동시 실행 ===
echo.

REM Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo Python이 설치되어 있지 않습니다. 설치를 시작합니다...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    echo Python 설치 완료. 환경변수 적용을 위해 이 창을 닫고 다시 실행해주세요.
    pause
    exit
)

REM playwright 설치 확인
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo playwright 모듈을 설치합니다...
    pip install playwright
    echo playwright 브라우저를 설치합니다...
    playwright install
)

echo 환경 준비 완료!
echo.

REM 프로젝트 루트로 이동
cd /d %~dp0..

REM 첫 번째 창: crawl_ev_subsidy.py (케이지모빌리티 보조금)
start "케이지모빌리티 보조금 크롤러" cmd /k "cd /d %~dp0.. && python src/crawl_ev_subsidy.py && echo. && echo === 완료. 아무 키나 누르면 창이 닫힙니다 === && pause >nul"

REM 두 번째 창: ev_crawler.py (전기차 보조금 접수현황)
start "전기차 보조금 접수현황 크롤러" cmd /k "cd /d %~dp0.. && python src/ev_crawler.py && echo. && echo === 완료. 아무 키나 누르면 창이 닫힙니다 === && pause >nul"

echo 두 크롤러가 별도 창에서 실행 중입니다.
timeout /t 3 >nul
