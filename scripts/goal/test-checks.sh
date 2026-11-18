#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# 기계 검문 6항목을 항목마다 "통과해야 하는 경우"와 "걸려야 하는 경우"로 시험한다.
# 임시 git 저장소와 가짜 gh·uv를 쓴다. 실제 GitHub·Claude에는 접속하지 않는다.
# 실행: bash scripts/goal/test-checks.sh   (결과는 PR에 붙일 수 있는 표로 나온다)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
export GOAL_GH="$HERE/fakes/gh" GOAL_UV="$HERE/fakes/uv"
export GOAL_VERIFY_WAIT_SEC=0 GOAL_VERIFY_POLL_SEC=0
# shellcheck source=lib-checks.sh
source "$HERE/lib-checks.sh"

T=$(mktemp -d); export FAKE_DIR="$T/fake"; mkdir -p "$FAKE_DIR"
trap 'rm -rf "$T"' EXIT
cd "$T" && git init -q -b main repo && cd repo || exit 1
git config user.email t@t; git config user.name t
mkdir -p agent/tests eval docs
printf 'import pytest\n\n\n@pytest.mark.skip(reason="원래 있던 정상 skip")\ndef test_old_skip():\n    pass\n\n\ndef test_keep():\n    assert 1\n' >agent/tests/test_a.py
echo "정답" >eval/answer.md; echo "문서" >docs/a.md
git add -A && git commit -q -m base

ok=0; bad=0
echo "| 항목 | 경우 | 기대 | 결과 | 맞음 |"
echo "| --- | --- | --- | --- | --- |"
# expect <항목> <경우 설명> <pass|block> <명령...>
expect() {
  local item=$1 desc=$2 want=$3 got; shift 3
  if "$@" >/dev/null 2>&1; then got=pass; else got=block; fi
  if [[ $got == "$want" ]]; then ok=$((ok + 1)); m="✅"; else bad=$((bad + 1)); m="❌ ($CHECK_REASON)"; fi
  echo "| $item | $desc | $want | $got | $m |"
}
# case_branch <이름>: base(main)에서 새 브랜치를 만든다
case_branch() { git checkout -q main && git checkout -q -B "$1"; }
commit() { git add -A && git commit -q -m "$1"; }
# sed -i는 맥(BSD)과 리눅스(GNU)의 문법이 달라, 임시 파일로 바꿔 끼운다.
sed_i() { sed "$1" "$2" >"$2.tmp" && mv "$2.tmp" "$2"; }

# 1. 테스트·ruff
case_branch c1
expect "1 테스트·ruff" "세 명령 모두 0" pass env FAKE_UV_EXIT=0 bash -c "source '$HERE/lib-checks.sh'; check_tests '$T/t.log'"
expect "1 테스트·ruff" "명령 하나가 실패" block env FAKE_UV_EXIT=1 bash -c "source '$HERE/lib-checks.sh'; check_tests '$T/t.log'"

# 2. 막힌 폴더
case_branch c2a; echo "더함" >>docs/a.md; commit docs
expect "2 막힌 폴더" "docs/만 변경" pass check_paths main
case_branch c2b; echo "한 줄" >>eval/answer.md; commit eval
expect "2 막힌 폴더" "eval/ 한 줄 변경" block check_paths main
case_branch c2c; mkdir -p .github; echo x >.github/x.yml; commit gh
expect "2 막힌 폴더" ".github/ 파일 추가" block check_paths main
case_branch c2d; mkdir -p .claude; echo x >.claude/x.md; commit claude
expect "2 막힌 폴더" ".claude/ 파일 추가" block check_paths main
case_branch c2e; git mv eval/answer.md docs/answer.md; commit mv
expect "2 막힌 폴더" "eval/ 파일을 밖으로 옮김" block check_paths main

# 3. skip·xfail·테스트 삭제 (base 대비 새로 생긴 것만)
case_branch c3a; printf '\n\ndef test_new():\n    assert 2\n' >>agent/tests/test_a.py; commit new
expect "3 skip·삭제" "원래 있던 skip 그대로 + 새 테스트" pass check_skips main
case_branch c3b; git mv agent/tests/test_a.py agent/tests/test_b.py; commit move
expect "3 skip·삭제" "원래 있던 skip 테스트 파일을 옮김" pass check_skips main
case_branch c3c; printf '\n\n@pytest.mark.xfail\ndef test_x():\n    assert 0\n' >>agent/tests/test_a.py; commit xfail
expect "3 skip·삭제" "새 xfail 추가" block check_skips main
case_branch c3d; printf '\n\n@pytest.mark.skipif(True, reason="x")\ndef test_y():\n    pass\n' >>agent/tests/test_a.py; commit skipif
expect "3 skip·삭제" "새 skipif 추가" block check_skips main
case_branch c3e; printf '\n\ndef test_z():\n    pytest.skip("나중에")\n' >>agent/tests/test_a.py; commit skipcall
expect "3 skip·삭제" "새 pytest.skip( 호출" block check_skips main
case_branch c3f; sed_i '/def test_keep/,$d' agent/tests/test_a.py; commit delete
expect "3 skip·삭제" "정상 테스트 함수 삭제" block check_skips main
case_branch c3g; sed_i 's/assert 1/assert 1 == 1/' agent/tests/test_a.py; commit edit
expect "3 skip·삭제" "테스트 본문만 고침" pass check_skips main
case_branch c3h; echo "xfail로 바꾸지 않는다" >>docs/a.md; commit doc
expect "3 skip·삭제" "문서에 xfail 낱말" pass check_skips main

# 4. PR (가짜 gh 파일로 상황을 만든다)
case_branch c4; echo y >>docs/a.md; commit pr
sha=$(git rev-parse HEAD)
echo '[{"number":73,"title":"PR 1n: x","labels":[{"name":"ready"}],"comments":[]}]' >"$FAKE_DIR/issues.json"
pr_json() { # <body> <labels-json> <base> <sha> [제목]
  jq -n --arg b "$1" --argjson l "$2" --arg base "$3" --arg s "$4" --arg t "${5:-PR 1n: x}" \
    '[{number: 9, url: "u", title: $t, body: $b, labels: $l, baseRefName: $base, headRefOid: $s}]' >"$FAKE_DIR/pr-list-c4.json"
}
pr_json "Closes #73" '[]' main "$sha"
expect "4 PR" "열린 PR, Closes #73, base·head 맞음" pass check_pr c4 73 origin/main
rm "$FAKE_DIR/pr-list-c4.json"
expect "4 PR" "열린 PR 없음" block check_pr c4 73 origin/main
pr_json "Closes #730" '[]' main "$sha"
expect "4 PR" "Closes #730 (다른 Issue)" block check_pr c4 73 origin/main
pr_json "Closes #73" '[]' feat/other "$sha"
expect "4 PR" "PR base가 정한 base와 다름" block check_pr c4 73 origin/main
pr_json "Closes #73" '[]' main 0000000
expect "4 PR" "PR head가 로컬 HEAD와 다름 (push 안 됨)" block check_pr c4 73 origin/main
pr_json "Closes #73" '[]' main "$sha" "feat: x (PR 1n)"
expect "4 PR" "PR 제목이 커밋 모양 feat: … (PR 1n)" block check_pr c4 73 origin/main
pr_json "Closes #73" '[]' main "$sha" "PR 1n: 다른 말"
expect "4 PR" "PR 제목이 PR 1n: 으로 시작하지만 Issue 제목과 다름" block check_pr c4 73 origin/main
echo '[{"number":73,"title":"PR 1n: x","labels":[{"name":"needs-verify"}],"comments":[]}]' >"$FAKE_DIR/issues.json"
pr_json "Closes #73" '[]' main "$sha"
expect "4 PR" "Issue에 needs-verify, PR에 없음" block check_pr c4 73 origin/main
pr_json "Closes #73" '[{"name":"needs-verify"}]' main "$sha"
expect "4 PR" "needs-verify를 PR에도 붙임" pass check_pr c4 73 origin/main

# 5. [검증] 코멘트
verify_json() { # <작성자> <판정> <커밋>
  jq -n --arg a "$1" --arg b "[검증] PR 1n / 판정: $2 / 기준 커밋 ${3:0:7}" \
    '{state: "OPEN", comments: [{author: {login: $a}, body: ($b + "\n\n본문")}]}' >"$FAKE_DIR/pr-9.json"
}
verify_json github-actions "통과" "$sha"
expect "5 [검증]" "Action 코멘트, 지금 커밋, 통과" pass check_verify 9
verify_json github-actions "조건부 통과" "$sha"
expect "5 [검증]" "Action 코멘트, 조건부 통과" pass check_verify 9
verify_json github-actions "미달" "$sha"
expect "5 [검증]" "Action 코멘트, 미달" block check_verify 9
verify_json someone "통과" "$sha"
expect "5 [검증]" "사람 계정이 쓴 가짜 [검증] 통과" block check_verify 9
verify_json github-actions "통과" "$(git rev-parse main)"
expect "5 [검증]" "예전 커밋 기준 코멘트만 있음" block check_verify 9
echo '{"state":"OPEN","comments":[]}' >"$FAKE_DIR/pr-9.json"
expect "5 [검증]" "코멘트 없음 (기다림 시간 0초)" block check_verify 9

# 6. 손대는 폴더 (Issue 칸에 적힌 폴더 밖은 못 고침)
case_branch c6a; echo y >>docs/a.md; printf '\n\ndef test_n():\n    assert 3\n' >>agent/tests/test_a.py; commit in
expect "6 손대는 폴더" "폴더 두 곳 안에서만 변경" pass check_folders main $'docs/\nagent/tests/'
expect "6 손대는 폴더" "폴더 하나만 허용, 다른 폴더도 변경" block check_folders main "docs/"
expect "6 손대는 폴더" "이름만 비슷한 폴더 (docs2/ 허용 아님)" block check_folders main $'doc\nagent/tests/'

echo
echo "맞음 $ok / 틀림 $bad"
(( bad == 0 ))
