#!/usr/bin/env bash
# Fetch today's Baike puzzle, save it, then play interactively
#   ./play_today.sh
#   ./play_today.sh --date 20260604
#   ./play_today.sh --sub-type history
#   ./play_today.sh --algo adaptive
set -euo pipefail

DIR=$(cd "$(dirname "$0")/.." && pwd)
DATE=
SUB_TYPE=
ALGO=

while [[ $# -gt 0 ]]; do
    case $1 in
        --date)     DATE=$2;     shift 2 ;;
        --sub-type) SUB_TYPE=$2; shift 2 ;;
        --algo)     ALGO=$2;     shift 2 ;;
        *)          echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

python3 "$DIR/cli/record_puzzle.py" ${DATE:+--date "$DATE"} ${SUB_TYPE:+--sub-type "$SUB_TYPE"}

[[ -z $DATE ]] && DATE=$(python3 -c "from cli.client import get_latest_daily_date; print(get_latest_daily_date())")
FILE="$DIR/puzzles/$DATE${SUB_TYPE:+_$SUB_TYPE}.json"

python3 "$DIR/main.py" --from-file "$FILE" ${ALGO:+--algo "$ALGO"}
