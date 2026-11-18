#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# goal 연속 실행 장치 (PR 1n, ADR-0009).
# 사람이 맥북 터미널에서 실행한다:
#   scripts/goal-run.sh [--minutes 90] [--turns 60] [--max-lanes 3] 4 5 6 7
# Issue들을 줄(lane)로 나눠 줄끼리는 동시에, 줄 안에서는 순서대로 돌린다.
# Issue마다 새 Claude를 줄 전용 작업 폴더(git worktree)에서 /goal로 띄우고, 끝나면 기계 검문을 직접 한다.
# 하지 않는 것: merge, 라벨(ready·plan-ok·infra-ok) 붙이기, force push, rebase.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=goal/lib-checks.sh
source "$HERE/goal/lib-checks.sh"
# shellcheck source=goal/lib-run.sh
source "$HERE/goal/lib-run.sh"
# shellcheck source=goal/lib-lanes.sh
source "$HERE/goal/lib-lanes.sh"
# shellcheck source=goal/lib-status.sh
source "$HERE/goal/lib-status.sh"
# shellcheck source=goal/lib-lane.sh
source "$HERE/goal/lib-lane.sh"
# shellcheck source=goal/lib-summary.sh
source "$HERE/goal/lib-summary.sh"

MINUTES=90; TURNS=60; MAX_LANES=3; PRS=()
while (($#)); do
  case $1 in
    --minutes) MINUTES=$2; shift 2 ;;
    --turns) TURNS=$2; shift 2 ;;
    --max-lanes) MAX_LANES=$2; shift 2 ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) PRS+=("$1"); shift ;;
  esac
done
(( ${#PRS[@]} )) || { echo "PR 번호를 하나 이상 주세요. 예: scripts/goal-run.sh 4 5" >&2; exit 2; }

REPO=$(git rev-parse --show-toplevel) || exit 2
cd "$REPO" || exit 2
STAMP=$(date +%Y-%m-%d_%H%M%S)
TEMPLATE="$REPO/.claude/goal-condition.md"
RUN_DIR=${GOAL_RUNS_DIR:-"$REPO/.goal-runs/$STAMP"}
# 줄 작업 폴더는 레포 밖에 둔다 (사람의 레포 폴더에 추적 안 되는 파일이 생기지 않게).
LANES_DIR=${GOAL_LANES_DIR:-"$(dirname "$REPO")/$(basename "$REPO")-lanes/$STAMP"}
LIMIT_SEC=${GOAL_TIMEOUT_SEC:-$(( MINUTES * 60 ))}
ISSUES_JSON="$RUN_DIR/issues.json"

# 시작 전 확인: 커밋 안 된 변경이 있으면 시작하지 않는다.
if [[ -n $(git status --porcelain) ]]; then
  echo "작업 폴더에 커밋 안 된 변경이 있어 시작하지 않습니다." >&2
  exit 1
fi
mkdir -p "$RUN_DIR" "$LANES_DIR"
# 실행 중에 맥북이 잠들지 않게 한다 (이 스크립트가 끝나면 같이 끝난다).
command -v caffeinate >/dev/null && caffeinate -dims -w $$ &
# 동시에 fetch하면 잠금이 부딪히므로 시작할 때 한 번만 받는다.
git fetch -q origin

# 1) Issue 정보 모으기 → 줄 나누기. 시작 안 할 Issue는 결과 파일에 이유만 남긴다.
for pr in "${PRS[@]}"; do collect_issue "$pr" "${PRS[*]}"; done | jq -s . >"$ISSUES_JSON"
LANES=$(plan_lanes <"$ISSUES_JSON")
for pr in "${PRS[@]}"; do
  grep -qE "^lane-[^ ]+ (.* )?$pr( |$)" <<<"$LANES" && continue
  R_PR=$pr; R_STATUS=blocked; R_CHECKS=""; R_MINUTES=0; R_TURNS=0; R_RETRIED=false
  R_URL=""; R_BRANCH=""; R_BASE=""; R_VERDICT=""
  R_ISSUE=$(jq -r --arg pr "$pr" '.[] | select(.pr == $pr) | .issue' "$ISSUES_JSON")
  R_REASON=$(jq -r --arg pr "$pr" \
    '.[] | select(.pr == $pr) | .skip // "시작 안 함: 선행 PR이 시작되지 않음"' "$ISSUES_JSON")
  write_result "$RUN_DIR/pr$pr.result.json"
done

# 2) 줄마다 작업 폴더를 만들고, 최대 MAX_LANES개까지 동시에 돌린다.
#    맥북 bash 3.2에는 wait -n이 없어, 돌고 있는 줄 수를 직접 센다.
: >"$RUN_DIR/lanes.tsv"
pids=""
running() { local n=0 p; for p in $pids; do kill -0 "$p" 2>/dev/null && n=$((n + 1)); done; echo $n; }
while read -r lane lane_prs; do
  [[ -n $lane ]] || continue
  wt="$LANES_DIR/$lane"
  git worktree add -q --detach "$wt" origin/main || { echo "$lane: worktree를 만들지 못함" >&2; continue; }
  printf '%s\t%s\t%s\n' "$lane" "$wt" "$lane_prs" >>"$RUN_DIR/lanes.tsv"
  while (( $(running) >= MAX_LANES )); do sleep "${GOAL_LANE_POLL_SEC:-5}"; done
  # shellcheck disable=SC2086  # lane_prs는 공백으로 나눈 PR 번호 목록
  (run_lane "$lane" "$wt" $lane_prs) >"$RUN_DIR/$lane.log" 2>&1 &
  pids+=" $!"
  echo "[$(date +%H:%M:%S)] $lane 시작: $lane_prs (기록: $RUN_DIR/$lane.log)"
done <<<"$LANES"
for p in $pids; do wait "$p"; done
# 줄 스크립트가 오류로 죽어 결과 파일이 없는 Issue에 이유를 남긴다 (lib-lane.sh).
fill_crashed_lanes "$RUN_DIR"

write_summary "$RUN_DIR" "${PRS[@]}"
echo "요약: $RUN_DIR/summary.md"
