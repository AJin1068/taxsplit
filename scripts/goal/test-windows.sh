#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
# Windows(Git Bash)에서 깨지던 곳을 본다 (PR 1ad). 맥·리눅스에서도 같은 결과가 나와야 한다.
# 1) run_goal이 claude에 "/goal ..."를 그대로 넘긴다 (Git Bash의 경로 바꾸기에 걸리지 않게)
# 2) date -r <초>가 안 되는 GNU date에서도 status.md에 "HH:MM 시작"이 찍힌다
# 실행: bash scripts/goal/test-windows.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=lib-run.sh
source "$HERE/lib-run.sh"
# shellcheck source=lib-status.sh
source "$HERE/lib-status.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT

ok=0; bad=0
echo "| 경우 | 기대 | 맞음 |"
echo "| --- | --- | --- |"
check() { # <경우> <기대> <실제>
  if [[ $2 == "$3" ]]; then ok=$((ok + 1)); echo "| $1 | $2 | ✅ |"
  else bad=$((bad + 1)); echo "| $1 | $2 (실제: $3) | ❌ |"; fi
}

# --- 1) /goal 인자 ---
# 받은 인자를 한 줄씩 적는 대역 claude.
# Git Bash의 경로 바꾸기는 Windows 프로그램을 부를 때만 일어나서 bash 대역 자신은 잡지 못한다.
# 그래서 Git Bash에서는 대역이 받은 환경 그대로 진짜 Windows 프로그램(cmd.exe)에 같은 인자를 넘겨 본다.
cat >"$T/claude" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" >"$ARGS_OUT"
case $(uname -s) in
  MINGW* | MSYS* | CYGWIN*)
    # //c는 Git Bash가 /c로 바꿔 넘긴다. 끝 인자와 경로 인자 하나를 같이 넘긴다.
    cmd.exe //c echo "${@: -1}" /tmp/x 2>/dev/null | tr -d '\r"' >"$ARGS_OUT.win" ;;
esac
EOF
chmod +x "$T/claude"
export ARGS_OUT="$T/args.txt"
GOAL_CLAUDE="$T/claude" GOAL_RUN_POLL_SEC=0.1 run_goal "x" "$T/run.log" 30
check "대역 claude가 받은 마지막 인자" "/goal x" "$(tail -1 "$ARGS_OUT")"
case $(uname -s) in
  MINGW* | MSYS* | CYGWIN*)
    win=$(cat "$ARGS_OUT.win")
    check "Git Bash: cmd.exe가 받은 /goal 인자" "/goal x" "${win% *}"
    # 다른 경로는 계속 Windows 경로로 바뀌어야 한다 (jq.exe·git이 파일을 열 수 있게)
    check "Git Bash: 다른 경로 인자는 그대로 바뀜" "바뀜" "$([[ ${win##* } != /tmp/x ]] && echo 바뀜 || echo 안 바뀜)" ;;
  *) echo "| Git Bash: cmd.exe가 받은 인자 | Windows가 아니라 돌리지 않음 | - |" ;;
esac

# --- 2) status.md 시작 시각 ---
# 가짜 date를 PATH 앞에 둔다. GNU처럼 -r <초>는 실패, -d @<초>는 12:34. 나머지는 진짜 date.
REAL_DATE=$(command -v date)
mkdir -p "$T/gnu" "$T/bsd"
cat >"$T/gnu/date" <<EOF
#!/usr/bin/env bash
case \$1 in -r) exit 1 ;; -d) echo 12:34; exit 0 ;; esac
exec "$REAL_DATE" "\$@"
EOF
# BSD처럼 -r <초>는 23:45, -d는 실패
cat >"$T/bsd/date" <<EOF
#!/usr/bin/env bash
case \$1 in -r) echo 23:45; exit 0 ;; -d) exit 1 ;; esac
exec "$REAL_DATE" "\$@"
EOF
# GNU에서 -r <이름>의 파일이 있을 때: 그 파일 시각(99:99)을 내버린다
mkdir -p "$T/gnufile"
cat >"$T/gnufile/date" <<EOF
#!/usr/bin/env bash
case \$1 in -r) echo 99:99; exit 0 ;; -d) echo 12:34; exit 0 ;; esac
exec "$REAL_DATE" "\$@"
EOF
chmod +x "$T/gnu/date" "$T/bsd/date" "$T/gnufile/date"

run_status() { # <PATH 앞에 둘 폴더|없음> → status.md 시작 줄
  local dir=$1
  RUN_DIR="$T/run-$(basename "$dir")"; STATUS_PR=""; STATUS_LANE=lane-1
  if [[ $dir == 없음 ]]; then status_set 7 "준비"
  else PATH="$dir:$PATH" status_set 7 "준비"; fi
  grep -m1 ' 시작, ' "$RUN_DIR/status.md"
}
check "GNU date(-r 실패)" "- 12:34 시작, 0분째" "$(run_status "$T/gnu")"
check "BSD date(-d 실패)" "- 23:45 시작, 0분째" "$(run_status "$T/bsd")"
check "이 PC의 진짜 date" "HH:MM" "$(run_status 없음 | grep -qE '^- [0-9]{2}:[0-9]{2} 시작, ' && echo HH:MM || echo 빈칸)"
# GNU date의 -r <파일>에 걸리지 않게: 초와 같은 이름의 파일이 있어도 -d로 간다
( cd "$T" && touch 1700000000 && PATH="$T/gnufile:$PATH" epoch_hm 1700000000 ) >"$T/same.txt"
check "초와 같은 이름의 파일이 있음" "12:34" "$(cat "$T/same.txt")"

echo
echo "맞음 $ok / 틀림 $bad"
(( bad == 0 ))
