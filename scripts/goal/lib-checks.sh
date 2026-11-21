# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR source=lib-platform.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-platform.sh"
# 기계 검문 6항목. goal이 "끝났다"고 해도 스크립트가 직접 다시 확인한다 (ADR-0009).
# 각 함수는 통과하면 0, 걸리면 1을 돌려주고, 걸린 이유를 CHECK_REASON에 남긴다.
# 실제 명령 대신 대역을 넣을 수 있다: GOAL_GH, GOAL_UV (시험용).

GOAL_GH=${GOAL_GH:-gh}
GOAL_UV=${GOAL_UV:-uv}
GOAL_VERIFY_WAIT_SEC=${GOAL_VERIFY_WAIT_SEC:-1200}
GOAL_VERIFY_POLL_SEC=${GOAL_VERIFY_POLL_SEC:-60}
CHECK_REASON=""
PR_NUMBER=""
PR_URL=""
VERIFY_VERDICT=""

# 1. agent/에서 테스트·ruff 세 명령이 모두 0으로 끝나는가
check_tests() {
  local log=$1
  CHECK_REASON=""
  if (cd agent && "$GOAL_UV" run pytest -q && "$GOAL_UV" run ruff check . \
      && "$GOAL_UV" run ruff format --check .) >"$log" 2>&1; then
    return 0
  fi
  CHECK_REASON="pytest/ruff 실패 (기록: $log)"
  return 1
}

# 2. base 대비 바뀐 파일에 eval/, .github/, .claude/가 없는가
#    --no-renames: 막힌 폴더 밖으로 옮긴 파일도 "지움"으로 잡히게 한다.
check_paths() {
  local base=$1 bad
  CHECK_REASON=""
  bad=$(git diff --name-only --no-renames "$base"...HEAD \
    | grep -E '^(eval|\.github|\.claude)/' || true)
  if [[ -n $bad ]]; then
    CHECK_REASON="막힌 폴더 변경: $(echo "$bad" | tr '\n' ' ')"
    return 1
  fi
  return 0
}

# diff에서 더해진(+) 줄 또는 지워진(-) 줄만 뽑는다. 앞뒤 공백은 지운다.
_diff_lines() {
  local base=$1 sign=$2
  git diff --no-renames -U0 "$base"...HEAD -- '*.py' '*.toml' '*.ini' '*.cfg' \
    | grep -v -E '^(\+\+\+|---) ' \
    | grep -E "^\\${sign}" \
    | sed -E "s/^\\${sign}//; s/^[[:space:]]+//; s/[[:space:]]+$//" || true
}

# 3. base 대비 "새로 생긴" skip·xfail이 없고, 지워진 테스트 함수가 없는가
#    원래 있던 skip을 옮기기만 한 경우(지운 줄과 더한 줄이 같음)는 잡지 않는다.
check_skips() {
  local base=$1 pat='pytest\.mark\.skip|skipif|xfail|pytest\.skip\('
  local def='^(async[[:space:]]+)?def[[:space:]]+(test_[A-Za-z0-9_]*)'
  local added removed new_skips gone_tests
  CHECK_REASON=""
  added=$(_diff_lines "$base" +)
  removed=$(_diff_lines "$base" -)
  # 줄 집합 차이: 더한 skip 줄 - 지운 skip 줄 (같은 줄이 여러 번이면 개수까지 비교)
  new_skips=$(comm -23 \
    <(grep -E "$pat" <<<"$added" | sort) \
    <(grep -E "$pat" <<<"$removed" | sort) || true)
  # 테스트 이름 집합 차이: 지운 test_ 이름 - 다시 더한 test_ 이름 (옮기기·고치기는 통과)
  gone_tests=$(comm -23 \
    <(grep -E "$def" <<<"$removed" | sed -E "s/$def.*/\\2/" | sort -u) \
    <(grep -E "$def" <<<"$added" | sed -E "s/$def.*/\\2/" | sort -u) || true)
  if [[ -n $new_skips ]]; then
    CHECK_REASON="새 skip/xfail: $(echo "$new_skips" | head -3 | tr '\n' ' ')"
  fi
  if [[ -n $gone_tests ]]; then
    CHECK_REASON="${CHECK_REASON:+$CHECK_REASON; }지운 테스트: $(echo "$gone_tests" | tr '\n' ' ')"
  fi
  [[ -z $CHECK_REASON ]]
}

# 4. 이 브랜치의 PR이 열려 있고, Closes #이슈, needs-verify 옮김, base·head가 맞는가
check_pr() {
  local branch=$1 issue=$2 base=$3 json body head pr_base issue_nv pr_nv pr_title issue_title
  CHECK_REASON=""; PR_NUMBER=""; PR_URL=""
  json=$("$GOAL_GH" pr list --head "$branch" --state open \
    --json number,url,title,body,labels,baseRefName,headRefOid 2>/dev/null || echo '[]')
  PR_NUMBER=$(jq -r '.[0].number // empty' <<<"$json")
  if [[ -z $PR_NUMBER ]]; then
    CHECK_REASON="브랜치 $branch 의 열린 PR 없음"
    return 1
  fi
  PR_URL=$(jq -r '.[0].url' <<<"$json")
  body=$(jq -r '.[0].body' <<<"$json")
  pr_base=$(jq -r '.[0].baseRefName' <<<"$json")
  head=$(jq -r '.[0].headRefOid' <<<"$json")
  pr_title=$(jq -r '.[0].title // ""' <<<"$json")
  # "#7"이 "#73"에 맞지 않도록 숫자 뒤를 막는다
  grep -Eiq "closes #${issue}([^0-9]|$)" <<<"$body" \
    || CHECK_REASON="PR 설명에 Closes #$issue 없음"
  [[ $pr_base == "${base#origin/}" ]] \
    || CHECK_REASON="${CHECK_REASON:+$CHECK_REASON; }PR base가 $pr_base (기대: ${base#origin/})"
  [[ $head == "$(git rev-parse HEAD)" ]] \
    || CHECK_REASON="${CHECK_REASON:+$CHECK_REASON; }PR head가 로컬 HEAD와 다름 (push 안 됨)"
  # PR 제목은 Issue 제목과 똑같이 ("PR N: …"). 다음 묶음의 선행 PR 판단과 사람이 PR 목록을 읽기 쉽게.
  issue_title=$("$GOAL_GH" issue view "$issue" --json title --jq .title 2>/dev/null || true)
  [[ -n $issue_title && $pr_title == "$issue_title" ]] \
    || CHECK_REASON="${CHECK_REASON:+$CHECK_REASON; }PR 제목을 Issue 제목과 같게: \"$issue_title\" (지금: \"$pr_title\", gh pr edit --title로 고침)"
  issue_nv=$("$GOAL_GH" issue view "$issue" --json labels \
    --jq '[.labels[].name] | index("needs-verify") != null' 2>/dev/null || echo false)
  pr_nv=$(jq -r '[.[0].labels[].name] | index("needs-verify") != null' <<<"$json")
  if [[ $issue_nv == true && $pr_nv != true ]]; then
    CHECK_REASON="${CHECK_REASON:+$CHECK_REASON; }Issue의 needs-verify가 PR에 없음"
  fi
  [[ -z $CHECK_REASON ]]
}

# 5. 검증 Action의 [검증] 코멘트가 지금 커밋 기준으로 달렸고 "미달"이 아닌가
#    같은 계정이 쓴 가짜 [검증]을 막으려고 작성자가 github-actions인 것만 본다.
check_verify() {
  local pr=$1 head line sha deadline
  head=$(git rev-parse HEAD)
  deadline=$(( $(date +%s) + GOAL_VERIFY_WAIT_SEC ))
  CHECK_REASON=""; VERIFY_VERDICT=""
  while :; do
    line=$("$GOAL_GH" pr view "$pr" --json comments --jq '[.comments[]
      | select(.author.login == "github-actions" or .author.login == "github-actions[bot]")
      | select(.body | startswith("[검증]"))] | last | .body // "" | split("\n")[0]' \
      2>/dev/null || true)
    sha=$(sed -nE 's/.*기준 커밋 ([0-9a-f]{7,40}).*/\1/p' <<<"$line")
    if [[ -n $sha && $head == "$sha"* ]]; then
      VERIFY_VERDICT=$(sed -nE 's/.*판정: *(통과|조건부 통과|미달).*/\1/p' <<<"$line")
      break
    fi
    if (( $(date +%s) >= deadline )); then
      CHECK_REASON="${GOAL_VERIFY_WAIT_SEC}초 안에 지금 커밋의 [검증] 코멘트 없음"
      return 1
    fi
    sleep "$GOAL_VERIFY_POLL_SEC"
  done
  case $VERIFY_VERDICT in
    통과|"조건부 통과") return 0 ;;
    미달) CHECK_REASON="[검증] 판정: 미달" ;;
    *) CHECK_REASON="[검증] 판정을 읽지 못함: $line" ;;
  esac
  return 1
}

# 6. base 대비 바뀐 파일이 모두 Issue의 "손대는 폴더" 안에 있는가 (줄끼리 같은 파일을 고치지 않게)
#    $2: 손대는 폴더 목록(한 줄에 하나). "x/"는 폴더, 끝에 /가 없으면 그 파일 또는 그 폴더.
check_folders() {
  local base=$1 folders=$2 f e ok out=""
  CHECK_REASON=""
  while IFS= read -r f; do
    [[ -n $f ]] || continue
    ok=false
    while IFS= read -r e; do
      e=${e%/}
      [[ -n $e && ( $f == "$e" || $f == "$e"/* ) ]] && { ok=true; break; }
    done <<<"$folders"
    $ok || out+="$f "
  done < <(git diff --name-only --no-renames "$base"...HEAD)
  if [[ -n $out ]]; then
    CHECK_REASON="손대는 폴더 밖 변경: $out"
    return 1
  fi
  return 0
}
