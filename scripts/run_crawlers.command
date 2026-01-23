#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

osascript -e "tell application \"Terminal\"
    do script \"cd '$SCRIPT_DIR' && echo '=== 케이지모빌리티 보조금 크롤러 ===' && python3 crawl_ev_subsidy.py; echo ''; echo '=== 완료. 아무 키나 누르면 창이 닫힙니다 ==='; read\"
end tell"

osascript -e "tell application \"Terminal\"
    do script \"cd '$SCRIPT_DIR' && echo '=== 전기차 보조금 접수현황 크롤러 ===' && python3 ev_crawler.py; echo ''; echo '=== 완료. 아무 키나 누르면 창이 닫힙니다 ==='; read\"
end tell"
