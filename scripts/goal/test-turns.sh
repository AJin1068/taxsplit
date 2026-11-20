#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# goal 턴 세기를 본다 (lib-run.sh read_turns·write_result, lib-summary.sh _row).
# 한 기록에 result 줄이 여러 번 나오면 모두 더해야 한다 (묶음 3 PR 11: 47턴 + 6턴이 6턴으로 적힘).
# 실행: bash scripts/goal/test-turns.sh (맥북은 /bin/bash scripts/goal/test-turns.sh)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib-run.sh
source "$HERE/lib-run.sh"
# shellcheck source=lib-summary.sh
source "$HERE/lib-summary.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

ok=0; bad=0
echo "| 경우 | 기대 | 맞음 |"
echo "| --- | --- | --- |"
check() { # <경우> <기대> <실제>
  if [[ $2 == "$3" ]]; then ok=$((ok + 1)); echo "| $1 | $2 | ✅ |"
  else bad=$((bad + 1)); echo "| $1 | $2 (실제: $3) | ❌ |"; fi
}

# 가짜 기록: result 두 번, 사이에 다른 메시지와 JSON이 아닌 줄
{
  echo '{"type":"system","subtype":"init"}'
  echo '{"type":"result","subtype":"success","num_turns":47}'
  echo 'JSON이 아닌 줄'
  echo '{"type":"assistant","message":{}}'
  echo '{"type":"result","subtype":"success","num_turns":6}'
} >"$T/two.jsonl"
echo '{"type":"result","num_turns":3}' >"$T/one.jsonl"
echo '{"type":"result","subtype":"error"}' >"$T/noturns.jsonl"
: >"$T/empty.jsonl"

check "result 두 줄 (47 + 6)" 53 "$(read_turns "$T/two.jsonl")"
check "result 한 줄" 3 "$(read_turns "$T/one.jsonl")"
check "num_turns 없음" 0 "$(read_turns "$T/noturns.jsonl")"
check "빈 기록" 0 "$(read_turns "$T/empty.jsonl")"
check "기록 파일 없음" 0 "$(read_turns "$T/none.jsonl")"

# 결과 파일과 요약 표: 한도를 넘었으면 turns_over: true, 표에 "한도 넘음"
R_PR=11; R_ISSUE=1; R_STATUS=passed; R_CHECKS=""; R_REASON=""; R_MINUTES=5
R_RETRIED=false; R_URL=""; R_BRANCH=b; R_BASE=main; R_VERDICT=""
R_TURNS=53; R_TURNS_OVER=true; write_result "$T/over.json"
check "한도 넘음 → turns_over" true "$(jq -r .turns_over "$T/over.json")"
check "한도 넘음 → 턴 합계" 53 "$(jq -r .turns "$T/over.json")"
_row "$T/over.json" | grep -q '53 ⚠️한도 넘음' && r=yes || r=no
check "한도 넘음 → 요약 표시" yes "$r"

R_TURNS=3; unset R_TURNS_OVER; write_result "$T/under.json"
check "값 없으면 turns_over 기본 false" false "$(jq -r .turns_over "$T/under.json")"
_row "$T/under.json" | grep -q '한도 넘음' && r=yes || r=no
check "한도 안 → 요약 표시 없음" no "$r"

echo
echo "맞음 $ok / 틀림 $bad"
(( bad == 0 ))
