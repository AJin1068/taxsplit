# shellcheck shell=bash
# 휴대폰에서 한눈에 볼 .goal-runs/<날짜>/status.md. 상태가 바뀔 때마다 고쳐 쓴다.
# 줄들이 동시에 돌므로 줄마다 자기 파일(status/<줄>.md)만 쓰고,
# 모든 줄 파일을 모아 임시 파일에 쓴 뒤 mv로 바꿔 끼운다 (반쯤 쓴 파일이 보이지 않게).
# 쓰는 전역값: RUN_DIR, STATUS_LANE(줄 이름), PR_URL, STATUS_CHECKS(마지막 검문 결과)
# 시험용: GOAL_STATUS_SNAPSHOTS 폴더를 주면 바뀔 때마다 사본을 남긴다.

STATUS_PR=""; STATUS_START=0; STATUS_SEQ=0; STATUS_CHECKS=""

# status_set <PR 번호> <단계>
# 단계: 준비 / goal 실행 중 / 재시도 / 검문 / [검증] 기다림 / 끝
status_set() {
  local pr=$1 stage=$2 dir="$RUN_DIR/status" now tmp
  mkdir -p "$dir"
  if [[ $pr != "$STATUS_PR" ]]; then STATUS_PR=$pr; STATUS_START=$(date +%s); STATUS_CHECKS=""; fi
  now=$(date +%s)
  tmp=$(mktemp "$dir/.tmp.XXXXXX")
  {
    echo "### ${STATUS_LANE:-줄} · PR $pr · $stage"
    echo "- $(date -r "$STATUS_START" +%H:%M) 시작, $(( (now - STATUS_START) / 60 ))분째"
    echo "- 마지막 검문: ${STATUS_CHECKS:-아직 없음}"
    echo "- PR: ${PR_URL:-아직 없음}"
  } >"$tmp" && mv "$tmp" "$dir/${STATUS_LANE:-lane}.md"
  _status_rebuild
}

# 검문 결과 JSON(R_CHECKS)을 "1✅ 2✅ 3✅ 4❌ 5❌ 6✅"처럼 짧게
status_checks_text() {
  jq -r '[(.tests, .paths, .skips, .pr, .verify, .folders)] | to_entries
    | map("\(.key + 1)\(if .value == true then "✅" else "❌" end)") | join(" ")' <<<"$1"
}

_status_rebuild() {
  local tmp f
  tmp=$(mktemp "$RUN_DIR/.status.XXXXXX")
  {
    echo "# 밤 실행 상태 ($(date +%H:%M:%S) 갱신)"
    for f in "$RUN_DIR"/status/*.md; do [[ -f $f ]] && { echo; cat "$f"; }; done
  } >"$tmp" && mv "$tmp" "$RUN_DIR/status.md"
  if [[ -n ${GOAL_STATUS_SNAPSHOTS:-} ]]; then
    STATUS_SEQ=$((STATUS_SEQ + 1))
    cp "$RUN_DIR/status.md" "$GOAL_STATUS_SNAPSHOTS/${STATUS_LANE:-lane}-$(printf %02d "$STATUS_SEQ").md"
  fi
}
