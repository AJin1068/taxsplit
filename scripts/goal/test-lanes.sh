#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# 줄(lane) 나누기 시험. 가짜 Issue 정보(가짜 gh)로 collect_issue·plan_lanes가 맞게 묶는지 본다.
# 실행: bash scripts/goal/test-lanes.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
export GOAL_GH="$HERE/fakes/gh"
# shellcheck source=lib-lanes.sh
source "$HERE/lib-lanes.sh"
T=$(mktemp -d); export FAKE_DIR="$T"; trap 'rm -rf "$T"' EXIT

# issue <Issue 번호> <PR> <선행 PR 칸 목록|-> <손대는 폴더 칸 목록|-> : "-"면 그 칸(제목)을 빼고 쓴다
ISSUES="[]"
issue() {
  local body="## 범위"$'\n\n'"설명"$'\n'
  [[ $3 == - ]] || body+=$'\n## 선행 PR\n\n'"$(tr ',' '\n' <<<"$3" | sed 's/^/- /')"$'\n'
  # shellcheck disable=SC2016  # 백틱은 마크다운 글자 그대로 넣는 것
  [[ $4 == - ]] || body+=$'\n## 손대는 폴더\n\n'"$(tr ',' '\n' <<<"$4" | sed 's/^/- `/; s/$/`/')"$'\n'
  body+=$'\n## 완료 기준\n\n- [ ] 무엇\n'
  ISSUES=$(jq --argjson n "$1" --arg t "PR $2: 시험" --arg b "$body" \
    '. + [{number: $n, title: $t, body: $b, labels: [], comments: []}]' <<<"$ISSUES")
}
issue 104 4 "없음" "agent/src/taxsplit/engine/,agent/tests/engine/"
issue 105 5 "PR 4" "agent/src/taxsplit/engine/allocate/"
issue 106 6 "없음" "docs/"
issue 107 7 "없음" "agent/src/taxsplit/rag/"
issue 108 8 "없음" "agent/src/taxsplit/rag/index.py"
issue 109 9 "없음" "-"
issue 110 10 "9" "agent/src/taxsplit/web/"
issue 111 11 "3" "agent/src/taxsplit/db/"
issue 112 12 "2" "agent/src/taxsplit/api/"
issue 113 13 "-" "agent/src/taxsplit/x/"
issue 114 14 "없음" "agent/src/taxsplit/eng"
issue 115 15 "4" "agent/src/taxsplit/report/"
issue 116 16 "1" "agent/src/taxsplit/ui/"
# 끝난 작업: PR 2·PR 1은 Issue가 닫힘. PR 1은 같은 번호의 열린 Issue가 또 있다.
# merge된 PR 제목은 일부러 커밋 모양(feat: …)으로 둔다. 선행 판단은 PR 제목을 보지 않는다.
ISSUES=$(jq '. + [{number: 102, title: "PR 2: 이미 끝남", body: "", labels: [], comments: [], state: "CLOSED"},
  {number: 101, title: "PR 1: 끝남", body: "", labels: [], comments: [], state: "CLOSED"},
  {number: 117, title: "PR 1: 다시 열림", body: "", labels: [], comments: [], state: "OPEN"}]' <<<"$ISSUES")
echo "$ISSUES" >"$T/issues.json"
echo '[{"title": "feat: 이미 merge됨 (PR 2)"}]' >"$T/merged.json"

lanes_for() { # PR 번호들 → plan_lanes 결과
  local p; for p in "$@"; do collect_issue "$p" "$*"; done | jq -s . | plan_lanes
}
skip_of() { collect_issue "$1" "$2" | jq -r '.skip // "없음"'; }

ok=0; bad=0
echo "| 경우 | 기대 | 결과 | 맞음 |"
echo "| --- | --- | --- | --- |"
expect() { # <경우> <기대> <결과>
  local m="✅"
  if [[ $2 == "$3" ]]; then ok=$((ok + 1)); else bad=$((bad + 1)); m="❌"; fi
  echo "| $1 | \`${2//$'\n'/ ; }\` | \`${3//$'\n'/ ; }\` | $m |"
}

expect "선행 PR이 같은 실행에 있으면 같은 줄 뒤에 붙음" \
  $'lane-4 4 5\nlane-6 6' "$(lanes_for 4 5 6)"
expect "순서를 거꾸로 줘도 줄 안에서는 선행 PR이 먼저 (줄 순서는 받은 순서)" \
  $'lane-6 6\nlane-4 4 5' "$(lanes_for 6 5 4)"
expect "손대는 폴더가 겹치면(폴더 안 파일) 한 줄로 합침" \
  'lane-7 7 8' "$(lanes_for 7 8)"
expect "이름만 비슷한 폴더(engine vs eng)는 안 겹침" \
  $'lane-4 4\nlane-14 14' "$(lanes_for 4 14)"
expect "손대는 폴더 칸이 빈 Issue는 시작 안 함" \
  "시작 안 함: 칸 없음 (손대는 폴더)" "$(skip_of 9 9)"
expect "선행 PR 칸(제목)이 없는 Issue는 시작 안 함" \
  "시작 안 함: 칸 없음 (선행 PR)" "$(skip_of 13 13)"
expect "칸 없는 Issue를 선행으로 둔 Issue도 시작 안 함 (줄에 없음)" \
  'lane-6 6' "$(lanes_for 9 10 6)"
expect "선행 PR이 merge 안 됐고 이번 실행에도 없으면 시작 안 함" \
  "시작 안 함: 선행 PR 3 가 merge 안 됐고 이번 실행에도 없음" "$(skip_of 11 11)"
expect "선행 PR의 Issue가 닫혔으면 독립 줄 (merge된 PR 제목이 feat: …여도)" \
  'lane-12 12' "$(lanes_for 12)"
expect "선행 PR의 Issue가 열려 있고 이번 실행에도 없으면 시작 안 함" \
  "시작 안 함: 선행 PR 4 가 merge 안 됐고 이번 실행에도 없음" "$(skip_of 15 15)"
expect "같은 번호의 Issue가 닫힌 것과 열린 것이 함께 있으면 끝나지 않은 것으로 봄" \
  "시작 안 함: 선행 PR 1 가 merge 안 됐고 이번 실행에도 없음" "$(skip_of 16 16)"

echo
echo "맞음 $ok / 틀림 $bad"
(( bad == 0 ))
