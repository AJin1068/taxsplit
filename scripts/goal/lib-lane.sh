# shellcheck shell=bash
# 줄(lane) 하나를 줄 전용 작업 폴더(git worktree)에서 순서대로 돌린다.
# 줄 안의 Issue는 앞 Issue 위에 쌓인다. 하나가 passed가 아니면 그 줄만 멈춘다 (다른 줄은 계속).
# 쓰는 전역값: TEMPLATE TURNS LIMIT_SEC RUN_DIR ISSUES_JSON

# 시작 조건: ready 라벨과 [계획] 코멘트가 있고, 아래 둘 중 하나면 시작한다. 안 맞으면 이유를 출력한다.
#   ① 가장 최근 [계획]의 "## 정할 것" 칸이 정확히 "- 없음" (사람이 정할 것이 없음)
#   ② plan-ok 라벨이 있음 (사람이 "정할 것"에 답하고 붙인 표시)
# "정할 것" 칸이 아예 없는 예전 [계획]은 "남음"으로 본다(plan-ok가 있어야 시작).
start_blocker() {
  local issue=$1 info
  info=$("$GOAL_GH" issue view "$issue" --json labels,comments) || { echo "Issue를 읽지 못함"; return; }
  jq -e '[.labels[].name] | index("ready")' >/dev/null <<<"$info" || { echo "ready 라벨 없음"; return; }
  jq -e '[.comments[].body | select(startswith("[계획]"))] | length > 0' >/dev/null <<<"$info" \
    || { echo "[계획] 코멘트 없음"; return; }
  jq -e '[.labels[].name] | index("plan-ok")' >/dev/null <<<"$info" && return
  # "## 정할 것" 제목 뒤부터 다음 "## " 제목 앞까지를 잘라, 앞뒤 빈칸을 지우고 "- 없음"인지 본다.
  jq -e '[.comments[].body | select(startswith("[계획]"))] | last
    | (split("\n## 정할 것") | if length > 1 then .[1] | split("\n## ")[0]
       | sub("^[^\n]*\n"; "") | gsub("^\\s+|\\s+$"; "") else "" end) == "- 없음"' \
    >/dev/null <<<"$info" || echo "정할 것 남음"
}

# Issue 하나: 시작 조건 → 쌓을 base로 옮기기 → goal(최대 2번) → 검문 → result.json
# $1: PR 번호, $2: 앞 Issue 브랜치(없으면 ""), $3: 앞 Issue의 GitHub PR 번호
run_issue() {
  local pr=$1 prev_branch=$2 prev_pr=$3 why state started notes="" attempt cond chars log
  local result="$RUN_DIR/pr$pr.result.json" blocked_local=".goal-runs/pr$pr.blocked.md"
  R_PR=$pr; R_STATUS=failed; R_CHECKS=""; R_REASON=""; R_MINUTES=0
  R_TURNS=0; R_RETRIED=false; R_URL=""; R_BRANCH=""; R_BASE=""; R_VERDICT=""
  PR_NUMBER=""; PR_URL=""; VERIFY_VERDICT=""
  R_ISSUE=$(jq -r --arg pr "$pr" '.[] | select(.pr == $pr) | .issue' "$ISSUES_JSON")
  local folders
  folders=$(jq -r --arg pr "$pr" '.[] | select(.pr == $pr) | .folders[]' "$ISSUES_JSON")
  status_set "$pr" "준비"

  why=$(start_blocker "$R_ISSUE")
  if [[ -n $why ]]; then
    R_STATUS=blocked; R_REASON="시작 안 함: $why"; write_result "$result"
    status_set "$pr" "끝: 시작 안 함 ($why)"; return 1
  fi

  # 쌓기: 앞 Issue PR이 merge 전이면 앞 브랜치 위에, merge됐으면(또는 줄의 첫 Issue면) main 위에.
  R_BASE=origin/main
  if [[ -n $prev_branch ]]; then
    state=$("$GOAL_GH" pr view "$prev_pr" --json state --jq .state 2>/dev/null)
    [[ $state == MERGED ]] || R_BASE=$prev_branch
  fi
  if ! git checkout -q --detach "$R_BASE"; then
    R_REASON="base $R_BASE 로 옮기지 못함"; write_result "$result"; return 1
  fi

  # 대역(가짜 claude)과 조건문이 쓰는 값. 진짜 claude에는 영향이 없다.
  # blocked 파일은 goal이 자기 작업 폴더 안에 쓰게 한다 (폴더 밖 쓰기를 auto 모드가 막을 수 있음).
  export GOAL_CURRENT_PR=$pr GOAL_CURRENT_ISSUE=$R_ISSUE GOAL_CURRENT_BASE=$R_BASE
  export GOAL_BLOCKED_FILE=$blocked_local GOAL_CURRENT_FOLDERS=$folders
  # shellcheck disable=SC2016  # 백틱은 마크다운 글자 그대로 넣는 것
  GOAL_CURRENT_FOLDERS_TEXT=$(sed 's/^/- `/; s/$/`/' <<<"$folders")
  started=$(date +%s)
  for attempt in 1 2; do
    cond=$(build_condition "$TEMPLATE" "$pr" "$R_ISSUE" "$R_BASE" "$TURNS" "$blocked_local" "$notes")
    # 공식 문서의 조건문 한도는 4,000자. 한글이 바이트로 세지지 않게 wc -m(글자 수)을 쓴다.
    chars=$(printf '%s' "$cond" | LC_ALL=en_US.UTF-8 wc -m | tr -d ' ')
    if (( chars > 4000 )); then
      R_REASON="조건문이 4,000자를 넘음 (${chars}자)"; break
    fi
    log="$RUN_DIR/pr$pr.jsonl"; (( attempt == 2 )) && log="$RUN_DIR/pr$pr.retry.jsonl"
    echo "[$(date +%H:%M:%S)] PR $pr (#$R_ISSUE) goal ${attempt}회차, base ${R_BASE#origin/}"
    if (( attempt == 1 )); then status_set "$pr" "goal 실행 중"
    else status_set "$pr" "재시도 (goal 2회차 실행 중)"; fi
    run_goal "$cond" "$log" "$LIMIT_SEC"
    R_TURNS=$(( R_TURNS + $(read_turns "$log") ))
    if [[ -f $blocked_local ]]; then
      cp "$blocked_local" "$RUN_DIR/pr$pr.blocked.md"
      R_STATUS=blocked; R_REASON="결정이 필요해 멈춤 (질문: pr$pr.blocked.md)"; break
    fi
    R_BRANCH=$(git branch --show-current)
    status_set "$pr" "검문"
    if [[ -n $R_BRANCH ]] && run_all_checks "$R_BRANCH" "$R_ISSUE" "$R_BASE" "$RUN_DIR" "$folders"; then
      R_STATUS=passed; R_REASON=""; break
    fi
    [[ -n $R_BRANCH ]] || FAILED_NOTES="- 새 브랜치를 만들지 않음 (detached HEAD)"$'\n'
    $TIMED_OUT && FAILED_NOTES+="- 시간 상한(${LIMIT_SEC}초)을 넘어 끊음"$'\n'
    R_REASON=$FAILED_NOTES
    # 재시도는 한 번만. 떨어진 항목을 조건문 뒤에 붙여 다시 돌린다.
    (( attempt == 1 )) && { notes=$FAILED_NOTES; R_RETRIED=true; }
  done
  R_URL=$PR_URL; R_VERDICT=$VERIFY_VERDICT
  R_MINUTES=$(( ($(date +%s) - started + 59) / 60 ))
  if [[ $R_STATUS == passed && -n $(git status --porcelain) ]]; then
    R_STATUS=failed; R_REASON="커밋 안 된 변경이 남음"
  fi
  write_result "$result"
  [[ -n $R_CHECKS ]] && STATUS_CHECKS=$(status_checks_text "$R_CHECKS")
  status_set "$pr" "끝: $R_STATUS"
  [[ $R_STATUS == passed ]]
}

# $1: 줄 이름, $2: 작업 폴더, $3..: 줄 안 PR 번호(순서대로)
run_lane() {
  local lane=$1 wt=$2 pr prev_branch="" prev_pr=""
  shift 2
  STATUS_LANE=$lane
  cd "$wt" || return 1
  echo "[$(date +%H:%M:%S)] $lane 시작: $* (작업 폴더 $wt)"
  if ! (cd agent && "$GOAL_UV" sync -q); then
    echo "$lane: uv sync 실패" >&2
  fi
  for pr in "$@"; do
    if ! run_issue "$pr" "$prev_branch" "$prev_pr"; then
      echo "[$(date +%H:%M:%S)] $lane: PR $pr $R_STATUS. 이 줄의 뒤 Issue는 시작하지 않습니다."
      return 1
    fi
    prev_branch=$R_BRANCH; prev_pr=$PR_NUMBER
  done
  echo "[$(date +%H:%M:%S)] $lane 끝"
}

# 줄 스크립트가 중간에 죽으면(예: 맥북 bash 3.2 문법 오류) 그 줄의 Issue에 결과 파일이 안 남는다.
# 모든 줄이 끝난 뒤 불러, 결과가 없는 Issue에 이유를 남긴다. 앞 Issue가 정상으로 멈춘 경우
# (failed·blocked 결과 파일이 있음)는 그대로 둔다. 요약의 "앞 Issue에서 멈춤"이 맞기 때문이다.
# $1: 실행 폴더 (lanes.tsv: 줄 이름, 작업 폴더, PR 번호들)
fill_crashed_lanes() {
  local dir=$1 lane wt prs pr f prev err
  [[ -f $dir/lanes.tsv ]] || return 0
  while IFS=$'\t' read -r lane wt prs; do
    [[ -n $lane ]] || continue
    prev=passed; err=""
    for pr in $prs; do
      f="$dir/pr$pr.result.json"
      if [[ -f $f ]]; then prev=$(jq -r .status "$f"); continue; fi
      [[ $prev == passed || $prev == crashed ]] || break
      R_PR=$pr; R_CHECKS=""; R_MINUTES=0; R_TURNS=0; R_RETRIED=false
      R_URL=""; R_BRANCH=""; R_BASE=""; R_VERDICT=""
      R_ISSUE=$(jq -r --arg pr "$pr" '.[] | select(.pr == $pr) | .issue' "$dir/issues.json" 2>/dev/null)
      [[ $R_ISSUE =~ ^[0-9]+$ ]] || R_ISSUE=0
      if [[ $prev == passed ]]; then
        # bash 오류 줄("…: line 60: …")을 먼저 찾고, 없으면 기록의 마지막 줄
        err=$(grep -E ': line [0-9]+: ' "$dir/$lane.log" 2>/dev/null | tail -1)
        [[ -n $err ]] || err=$(grep -v '^[[:space:]]*$' "$dir/$lane.log" 2>/dev/null | tail -1)
        R_STATUS=failed
        R_REASON="줄 스크립트 오류로 끝남 ($lane.log): ${err:-기록 없음}"
        STATUS_LANE=$lane; PR_URL=""; STATUS_CHECKS=""
        status_set "$pr" "끝(오류): 줄 스크립트 오류"
        prev=crashed
      else
        R_STATUS=blocked; R_REASON="시작 안 함: 같은 줄 앞 Issue가 failed (줄 스크립트 오류)"
      fi
      write_result "$f"
    done
  done <"$dir/lanes.tsv"
}
