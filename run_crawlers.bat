@echo off
chcp 65001 >nul
title EV 크롤러 실행기

echo === EV 보조금 크롤러 동시 실행 ===
echo.

REM 첫 번째 창: crawl_ev_subsidy.py (케이지모빌리티 보조금)
start "케이지모빌리티 보조금 크롤러" cmd /k "cd /d %~dp0 && python crawl_ev_subsidy.py && echo. && echo === 완료. 아무 키나 누르면 창이 닫힙니다 === && pause >nul"

REM 두 번째 창: ev_crawler.py (전기차 보조금 접수현황)
start "전기차 보조금 접수현황 크롤러" cmd /k "cd /d %~dp0 && python ev_crawler.py && echo. && echo === 완료. 아무 키나 누르면 창이 닫힙니다 === && pause >nul"

echo 두 크롤러가 별도 창에서 실행 중입니다.
timeout /t 3 >nul
