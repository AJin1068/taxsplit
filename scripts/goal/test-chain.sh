#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# goal-run.sh를 가짜 claude·gh·uv로 처음부터 끝까지 돌려 본다 (실제 GitHub·Claude 접속 없음).
# 재시도 1번, 실패·blocked면 그 줄만 멈춤, 다른 줄은 계속, 시작 조건, 쌓기, 동시 실행 수, 시간 상한.
# 실행: bash scripts/goal/test-chain.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
RUNNER="$HERE/../goal-run.sh"
export GOAL_CLAUDE="$HERE/fakes/claude" GOAL_GH="$HERE/fakes/gh" GOAL_UV="$HERE/fakes/uv"
export GOAL_VERIFY_WAIT_SEC=0 GOAL_VERIFY_POLL_SEC=0 GOAL_RUN_POLL_SEC=0.2 GOAL_LANE_POLL_SEC=0.2
export GOAL_KILL_GRACE_SEC=1
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

# 임시 원격(bare)과 작업 레포. 조건문 틀은 진짜 파일을 복사한다.
git init -q --bare -b main "$T/origin.git"
git clone -q "$T/origin.git" "$T/repo" 2>/dev/null
cd "$T/repo" || exit 1
git config user.email t@t; git config user.name t
mkdir -p agent .claude && touch agent/.keep
cp "$HERE/../../.claude/goal-condition.md" .claude/
echo ".goal-runs/" >.gitignore
git add -A && git commit -q -m base && git push -q origin main

ok=0; bad=0
echo "| 경우 | 확인한 것 | 맞음 |"
echo "| --- | --- | --- |"
check() { # <경우> <확인한 것> <명령...>
  local c=$1 w=$2; shift 2
  if "$@" >/dev/null 2>&1; then ok=$((ok + 1)); echo "| $c | $w | ✅ |"
  else bad=$((bad + 1)); echo "| $c | $w | ❌ |"; fi
}
# Issue 하나를 가짜 gh에 넣는다: <Issue 번호> <PR> <선행 PR> <폴더> [라벨들] [계획 있음 yes|no]
add_issue() {
  local labels=${5:-ready,plan-ok} plan=${6:-yes} body
  body=$'## 선행 PR\n\n- '"$3"$'\n\n## 손대는 폴더\n\n- `'"$4"$'`\n'
  jq --argjson n "$1" --arg t "PR $2: 시험" --arg b "$body" --arg l "$labels" --arg p "$plan" \
    '. + [{number: $n, title: $t, body: $b,
      labels: ($l | split(",") | map(select(. != "") | {name: .})),
      comments: (if $p == "yes" then [{body: "[계획] 승인된 계획"}] else [] end)}]' \
    "$FAKE_DIR/issues.json" >"$FAKE_DIR/i.tmp" && mv "$FAKE_DIR/i.tmp" "$FAKE_DIR/issues.json"
}
# 새 시나리오: 가짜 상태를 비우고 결과 폴더를 새로 잡는다
scenario() {
  export FAKE_DIR="$T/fake-$1" GOAL_RUNS_DIR="$T/runs-$1" GOAL_LANES_DIR="$T/lanes-$1"
  mkdir -p "$FAKE_DIR"; echo '[]' >"$FAKE_DIR/issues.json"; : >"$FAKE_DIR/claude-calls.log"
}
mode() { echo "$2" >"$FAKE_DIR/mode-$1"; }
calls() { grep -c "^$1\$" "$FAKE_DIR/claude-calls.log"; }
res() { jq -r "$2" "$GOAL_RUNS_DIR/pr$1.result.json"; }
eq() { [[ $1 == "$2" ]]; }

# 1) 4는 두 번 다 실패, 5는 4 위에 쌓임, 6은 다른 줄
scenario a
add_issue 104 4 없음 agent/a/; add_issue 105 5 4 agent/a/; add_issue 106 6 없음 docs/
mode 4 "fail fail"; mode 5 pass; mode 6 pass
bash "$RUNNER" 4 5 6 >/dev/null 2>&1
check "재시도" "PR 4 goal 호출이 정확히 2번" eq "$(calls 4)" 2
check "재시도" "두 번째도 떨어지면 failed, retried=true" eq "$(res 4 '.status + " " + (.retried|tostring)')" "failed true"
check "줄 멈춤" "failed 뒤 같은 줄의 PR 5는 시작 안 함 (호출 0번, 결과 파일 없음)" \
  bash -c "[[ \$(grep -c '^5\$' '$FAKE_DIR/claude-calls.log') == 0 && ! -f '$GOAL_RUNS_DIR/pr5.result.json' ]]"
check "다른 줄 계속" "PR 4가 failed여도 다른 줄의 PR 6은 passed" eq "$(res 6 .status)" passed
check "요약" "summary.md에 시작 안 한 PR 5가 적힘" grep -q "| 5 | - | 시작 안 함" "$GOAL_RUNS_DIR/summary.md"
# GOAL_EXAMPLE_OUT을 주면 PR에 붙일 예시(summary.md, result.json)를 그 폴더에 복사한다
[[ -n ${GOAL_EXAMPLE_OUT:-} ]] && cp "$GOAL_RUNS_DIR"/summary.md "$GOAL_RUNS_DIR"/pr*.result.json "$GOAL_EXAMPLE_OUT"/

# 2) 첫 번째는 떨어지고 재시도에서 통과
scenario b
add_issue 107 7 없음 agent/b/; mode 7 "fail pass"
bash "$RUNNER" 7 >/dev/null 2>&1
check "재시도" "재시도에서 통과하면 passed, 호출 2번" eq "$(res 7 .status) $(calls 7)" "passed 2"

# 3) blocked면 그 줄의 뒤 Issue를 시작하지 않음
scenario c
add_issue 108 8 없음 agent/c/; add_issue 109 9 8 agent/c/; mode 8 blocked; mode 9 pass
bash "$RUNNER" 8 9 >/dev/null 2>&1
check "blocked" "PR 8 blocked, PR 9 호출 0번" eq "$(res 8 .status) $(calls 9)" "blocked 0"
check "blocked" "질문 파일이 결과 폴더로 옮겨지고 summary에 질문이 나옴" grep -q "가짜 질문" "$GOAL_RUNS_DIR/summary.md"

# 4) ready·plan-ok·[계획]이 없으면 시작 안 함
scenario d
add_issue 110 10 없음 agent/d1/ ready; add_issue 111 11 없음 agent/d2/ plan-ok
add_issue 112 12 없음 agent/d3/ ready,plan-ok no; mode 10 pass; mode 11 pass; mode 12 pass
bash "$RUNNER" 10 11 12 >/dev/null 2>&1
check "시작 조건" "plan-ok 없음 → 시작 안 함 (호출 0번)" eq "$(res 10 .reason) $(calls 10)" "시작 안 함: plan-ok 라벨 없음 0"
check "시작 조건" "ready 없음 → 시작 안 함 (호출 0번)" eq "$(res 11 .reason) $(calls 11)" "시작 안 함: ready 라벨 없음 0"
check "시작 조건" "[계획] 코멘트 없음 → 시작 안 함" eq "$(res 12 .reason)" "시작 안 함: [계획] 코멘트 없음"

# 5) 쌓기: 앞 PR이 merge 전이면 뒤 PR의 base는 앞 브랜치
scenario e
add_issue 113 13 없음 agent/e/; add_issue 114 14 13 agent/e/; mode 13 pass; mode 14 pass
mkdir -p "$T/snap"
GOAL_STATUS_SNAPSHOTS="$T/snap" bash "$RUNNER" 13 14 >/dev/null 2>&1
check "쌓기" "PR 13 base=main, PR 14 base=PR 13 브랜치" \
  eq "$(res 13 .base) $(res 14 .base) $(res 14 .status)" "main feat/pr13-fake passed"

# 5-1) status.md가 단계마다 바뀜 (휴대폰 상태판)
for stage in "준비" "goal 실행 중" "검문" "\[검증\] 기다림" "끝: passed"; do
  check "status.md" "단계 '$stage'가 찍힌 스냅샷이 있음" grep -rlq "PR 1[34] · $stage" "$T/snap"
done
check "status.md" "끝난 뒤 status.md에 마지막 검문 결과가 적힘" \
  grep -q "마지막 검문: 1✅ 2✅ 3✅ 4✅ 5✅ 6✅" "$GOAL_RUNS_DIR/status.md"
[[ -n ${GOAL_EXAMPLE_OUT:-} ]] && mkdir -p "$GOAL_EXAMPLE_OUT/status" && cp "$T/snap"/* "$GOAL_EXAMPLE_OUT/status/"

# 6) --max-lanes 2: 세 번째 줄은 앞 줄 하나가 끝난 뒤 시작
scenario f
add_issue 115 15 없음 agent/f1/; add_issue 116 16 없음 agent/f2/; add_issue 117 17 없음 agent/f3/
mode 15 slow; mode 16 slow; mode 17 slow
bash "$RUNNER" --max-lanes 2 15 16 17 >/dev/null 2>&1
t() { awk -v k="$1" -v p="$2" '$1 == k && $2 == p { print $3; exit }' "$FAKE_DIR/times.log"; }
first_end=$(( $(t end 15) < $(t end 16) ? $(t end 15) : $(t end 16) ))
check "동시 실행 수" "줄 1·2는 같이 시작, 줄 3은 앞 줄이 끝난 뒤 시작" \
  bash -c "(( $(t start 16) - $(t start 15) <= 1 && $(t start 17) >= $first_end ))"
check "동시 실행 수" "세 줄 모두 passed" eq "$(res 15 .status)$(res 16 .status)$(res 17 .status)" passedpassedpassed

# 7) 시간 상한을 넘으면 끊고, 재시도도 넘으면 failed
scenario g
add_issue 118 18 없음 agent/g/; mode 18 "hang hang"
GOAL_TIMEOUT_SEC=1 bash "$RUNNER" 18 >/dev/null 2>&1
check "시간 상한" "두 번 다 끊기면 failed, 이유에 시간 상한" \
  bash -c "[[ \$(jq -r .status '$GOAL_RUNS_DIR/pr18.result.json') == failed ]] && jq -r .reason '$GOAL_RUNS_DIR/pr18.result.json' | grep -q '시간 상한'"

echo
echo "맞음 $ok / 틀림 $bad"
(( bad == 0 ))
