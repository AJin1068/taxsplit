# shellcheck shell=bash
# OS마다 다른 곳을 맞춘다 (PR 1ad). 여러 번 읽어도 된다.
# Windows용 jq(jq.exe)는 줄 끝을 CRLF로 낸다. 그러면 $(jq -r ...) 값 끝에 \r가 붙어
# 줄 이름·상태 비교가 모두 어긋난다. -b(--binary)를 붙여 LF만 내게 한다.
# macOS·Linux에서는 아무것도 하지 않는다 (예전 jq 1.6은 Windows 밖에서 -b를 모른다).
case $(uname -s) in
  MINGW* | MSYS* | CYGWIN*)
    jq() { command jq -b "$@"; }
    # 줄 스크립트·대역 claude/gh 같은 자식 bash도 같은 jq를 쓰게 한다
    export -f jq
    ;;
esac
