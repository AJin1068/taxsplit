#!/usr/bin/env bash
# scripts/ 아래 셸 스크립트의 함정을 찾는다.
# 1) "$이름" 바로 뒤에 ASCII가 아닌 글자(예: 한글)가 붙은 곳.
#    맥북 기본 bash(3.2)는 한글의 첫 바이트까지 변수 이름으로 읽어,
#    set -u에서 "unbound variable"로 죽는다 (11/17 첫 시험 실행, lib-lane.sh:60).
#    "${이름}한글"처럼 중괄호로 감싸야 한다.
# 바이트 기준으로 보도록 LC_ALL=C를 쓴다 (맥·리눅스 같은 결과).
# 실행: bash scripts/goal/test-scripts.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPTS=$(cd "$HERE/.." && pwd)
PAT=$(printf '\\$[A-Za-z_][A-Za-z0-9_]*[\x80-\xff]')

find_bad() { LC_ALL=C grep -nE "$PAT" "$@"; }

ok=0; bad=0
echo "| 경우 | 기대 | 맞음 |"
echo "| --- | --- | --- |"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
# 시험용 글자는 printf %s로 붙인다 (이 파일 자체가 검사에 걸리지 않게).
printf 'echo "goal $attempt%s"\n' '회차' >"$T/bad.sh"
printf 'echo "goal ${attempt}%s"\necho "$a %s"\n' '회차' '회차' >"$T/good.sh"
if find_bad "$T/bad.sh" >/dev/null; then ok=$((ok + 1)); echo "| 변수 바로 뒤 한글 | 걸림 | ✅ |"
else bad=$((bad + 1)); echo "| 변수 바로 뒤 한글 | 걸림 | ❌ |"; fi
if find_bad "$T/good.sh" >/dev/null; then bad=$((bad + 1)); echo "| 중괄호로 감쌈, 띄어 씀 | 안 걸림 | ❌ |"
else ok=$((ok + 1)); echo "| 중괄호로 감쌈, 띄어 씀 | 안 걸림 | ✅ |"; fi

files=$(find "$SCRIPTS" -type f \( -name '*.sh' -o -path '*/fakes/*' \) | sort)
# shellcheck disable=SC2086  # 파일 목록을 공백으로 나눈다
if hits=$(find_bad $files); then
  bad=$((bad + 1)); echo "| scripts/ 전체 | 없음 | ❌ |"; echo; echo "$hits"
else
  ok=$((ok + 1)); echo "| scripts/ 전체 | 없음 | ✅ |"
fi
echo
echo "맞음 $ok / 틀림 $bad"
(( bad == 0 ))
