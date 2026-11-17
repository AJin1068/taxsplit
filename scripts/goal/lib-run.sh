# shellcheck shell=bash
# goal 한 번 실행하기, 조건문 만들기, 결과 파일 쓰기.
# 대역: GOAL_CLAUDE (시험에서 claude 대신 넣는 명령).

GOAL_CLAUDE=${GOAL_CLAUDE:-claude}
GOAL_RUN_POLL_SEC=${GOAL_RUN_POLL_SEC:-5}
GOAL_KILL_GRACE_SEC=${GOAL_KILL_GRACE_SEC:-30}
TIMED_OUT=false

# 조건문 틀(.claude/goal-condition.md)의 {{칸}}을 채운다.
# sed 대신 bash 치환을 써서 값에 / & 같은 글자가 있어도 깨지지 않게 한다.
build_condition() {
  local tpl=$1 pr=$2 issue=$3 base=$4 turns=$5 blocked=$6 notes=$7 text
  text=$(<"$tpl")
  text=${text//\{\{PR\}\}/$pr}
  text=${text//\{\{ISSUE\}\}/$issue}
  text=${text//\{\{BASE\}\}/${base#origin/}}
  text=${text//\{\{TURNS\}\}/$turns}
  text=${text//\{\{BLOCKED_FILE\}\}/$blocked}
  text=${text//\{\{FOLDERS\}\}/$GOAL_CURRENT_FOLDERS_TEXT}
  text=${text//\{\{RETRY_NOTES\}\}/${notes:-없음 (첫 실행)}}
  printf '%s' "$text"
}

# goal을 띄우고 시간 상한을 넘으면 끊는다. 맥북에는 timeout 명령이 없어 직접 잰다.
# 끊을 때는 먼저 SIGINT(턴을 마무리)를 보내고, 안 끝나면 SIGTERM을 보낸다.
run_goal() {
  local cond=$1 log=$2 limit_sec=$3 pid deadline
  TIMED_OUT=false
  "$GOAL_CLAUDE" -p --permission-mode auto --permission-prompts none \
    --output-format stream-json --verbose "/goal $cond" >>"$log" 2>>"$log.err" &
  pid=$!
  deadline=$(( $(date +%s) + limit_sec ))
  while kill -0 "$pid" 2>/dev/null; do
    if (( $(date +%s) >= deadline )); then
      TIMED_OUT=true
      kill -INT "$pid" 2>/dev/null
      sleep "$GOAL_KILL_GRACE_SEC"
      kill -TERM "$pid" 2>/dev/null
      break
    fi
    sleep "$GOAL_RUN_POLL_SEC"
  done
  wait "$pid" 2>/dev/null || true
}

# 실행 기록(stream-json)의 마지막 result 메시지에서 턴 수를 읽는다.
read_turns() {
  local log=$1
  [[ -s $log ]] || { echo 0; return; }
  jq -R 'fromjson? | select(.type == "result") | .num_turns // 0' "$log" \
    | tail -1 | grep -E '^[0-9]+$' || echo 0
}

# Issue 하나의 결과를 result.json으로 쓴다 (Issue에서 정한 칸 + 링크·브랜치 등 참고 칸).
write_result() {
  local out=$1 checks=${R_CHECKS:-}
  [[ -n $checks ]] || checks='{}'
  jq -n \
    --arg pr "$R_PR" --argjson issue "${R_ISSUE:-0}" --arg status "$R_STATUS" \
    --argjson checks "$checks" --arg reason "$R_REASON" \
    --argjson minutes "${R_MINUTES:-0}" --argjson turns "${R_TURNS:-0}" \
    --argjson retried "${R_RETRIED:-false}" --arg url "$R_URL" \
    --arg branch "$R_BRANCH" --arg base "${R_BASE#origin/}" --arg verdict "$R_VERDICT" \
    '{pr: $pr, issue: $issue, status: $status, checks: $checks, reason: $reason,
      minutes: $minutes, turns: $turns, retried: $retried,
      url: $url, branch: $branch, base: $base, verify_verdict: $verdict}' >"$out"
}

# 검문 6항목을 차례로 돌리고 R_CHECKS(JSON)·FAILED_NOTES(재시도에 붙일 말)를 채운다.
# 4번(PR)이 떨어지면 PR 번호가 없으므로 5번은 돌리지 않고 실패로 둔다.
run_all_checks() {
  local branch=$1 issue=$2 base=$3 logdir=$4 folders=$5 t p s r v fo
  FAILED_NOTES=""
  _note() { FAILED_NOTES+="- 검문 $1 실패: $CHECK_REASON"$'\n'; }
  if check_tests "$logdir/pr${GOAL_CURRENT_PR:-x}.tests.log"; then t=true; else t=false; _note "1(pytest·ruff)"; fi
  if check_paths "$base"; then p=true; else p=false; _note "2(막힌 폴더)"; fi
  if check_skips "$base"; then s=true; else s=false; _note "3(skip·테스트 삭제)"; fi
  if check_pr "$branch" "$issue" "$base"; then r=true; else r=false; _note "4(PR)"; fi
  # 휴대폰 상태판에 "[검증] 기다림"을 띄운다 (최대 20분 걸릴 수 있어서)
  if [[ $r == true ]] && type status_set >/dev/null 2>&1; then status_set "$GOAL_CURRENT_PR" "[검증] 기다림"; fi
  if [[ $r == true ]] && check_verify "$PR_NUMBER"; then v=true
  else
    v=false
    [[ $r == true ]] || CHECK_REASON="검문 4가 떨어져 돌리지 않음"
    _note "5([검증] 코멘트)"
  fi
  if check_folders "$base" "$folders"; then fo=true; else fo=false; _note "6(손대는 폴더)"; fi
  R_CHECKS=$(jq -cn --argjson t $t --argjson p $p --argjson s $s --argjson r $r --argjson v $v \
    --argjson fo $fo '{tests: $t, paths: $p, skips: $s, pr: $r, verify: $v, folders: $fo}')
  [[ -z $FAILED_NOTES ]]
}
