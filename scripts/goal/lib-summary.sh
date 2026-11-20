# shellcheck shell=bash
# 실행이 끝나면 .goal-runs/<날짜_시각>/summary.md를 만든다. 끝난 뒤 사람이 이 파일 하나만 본다.

_HEAD="| PR | Issue | 상태 | 1 테스트 | 2 막힌 폴더 | 3 skip | 4 PR | 5 검증 | 6 손대는 폴더 | 판정 | 분 | 턴 | 재시도 | PR 링크 | 이유 |"
_SEP="| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"

# result.json 하나를 표 한 줄로. 검문 칸은 ✅/❌, 돌리지 않았으면 -.
# 턴 칸: goal 한 회차가 --turns 한도를 넘었으면 "⚠️한도 넘음"을 붙인다(끊지는 않음).
_row() {
  # 주의: jq의 // 는 false도 "값 없음"으로 보므로 쓰지 않는다 (❌가 -로 보이는 버그가 있었음).
  jq -r 'def m($k): .checks[$k] | if . == true then "✅" elif . == false then "❌" else "-" end;
    "| \(.pr) | #\(.issue) | \(.status) | \(m("tests")) | \(m("paths")) | \(m("skips")) | \(m("pr")) | \(m("verify")) | \(m("folders")) | \(if .verify_verdict == "" then "-" else .verify_verdict end) | \(.minutes) | \(.turns)\(if .turns_over == true then " ⚠️한도 넘음" else "" end) | \(if .retried then "예" else "아니오" end) | \(if .url == "" then "-" else .url end) | \(.reason | gsub("\\|"; "/") | gsub("\n"; " ")) |"' "$1"
}

# $1: 실행 폴더, $2..: 이번 실행의 PR 번호들 (순서대로)
write_summary() {
  local dir=$1; shift
  local out="$dir/summary.md" pr f lane wt prs any=false q
  {
    echo "# goal 연속 실행 요약 ($(basename "$dir"))"
    echo
    echo "줄(lane)끼리는 동시에, 줄 안에서는 위에서 아래 순서로 쌓여 돌았습니다."
    while IFS=$'\t' read -r lane wt prs; do
      [[ -n $lane ]] || continue
      echo; echo "## $lane"; echo; echo "- 작업 폴더: \`$wt\`"; echo
      echo "$_HEAD"; echo "$_SEP"
      for pr in $prs; do
        f="$dir/pr$pr.result.json"
        if [[ -f $f ]]; then _row "$f"
        else echo "| $pr | - | 시작 안 함 (이 줄의 앞 Issue에서 멈춤) | - | - | - | - | - | - | - | - | - | - | - | - |"; fi
      done
    done <"$dir/lanes.tsv"
    echo; echo "## 시작하지 않은 Issue"; echo
    local skipped=""
    for pr in "$@"; do
      cut -f3 "$dir/lanes.tsv" | tr ' ' '\n' | grep -qx "$pr" || skipped+=" $pr"
    done
    if [[ -z $skipped ]]; then echo "없음."
    else
      echo "$_HEAD"; echo "$_SEP"
      for pr in $skipped; do _row "$dir/pr$pr.result.json"; done
    fi
    echo; echo "## 사람이 답할 질문"; echo
    for q in "$dir"/pr*.blocked.md; do
      [[ -f $q ]] || continue
      any=true; echo "### $(basename "$q" .blocked.md)"; cat "$q"; echo
    done
    for f in "$dir"/pr*.result.json; do
      [[ -f $f && $(jq -r .verify_verdict "$f") == "조건부 통과" ]] || continue
      any=true
      echo "- $(jq -r '"PR \(.pr) (\(.url))"' "$f"): [검증] 조건부 통과. PR의 \"확인해 주세요\"와 [검증] 코멘트를 봐 주세요."
    done
    [[ $any == true ]] || echo "없음."
    echo; echo "## merge 순서"; echo
    echo "- 줄마다 위 표의 순서대로 merge합니다. 쌓인 PR은 base가 앞 브랜치입니다."
    echo "- 앞 PR을 merge하고 그 브랜치를 지우면 GitHub가 뒤 PR의 base를 main으로 바꿉니다."
    echo "- 브랜치를 지우지 않았다면: \`gh pr edit <뒤 PR 번호> --base main\`"
    echo "- 작업 폴더는 지우지 않았습니다. 다 보고 나면: \`git worktree remove <작업 폴더>\`"
  } >"$out"
}
