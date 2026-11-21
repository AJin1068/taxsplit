# shellcheck shell=bash
# shellcheck source-path=SCRIPTDIR source=lib-platform.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-platform.sh"
# 줄(lane) 나누기. 짐작하지 않고 Issue 본문의 두 칸으로만 정한다 (CLAUDE.md "goal 연속 실행").
#   ## 선행 PR        - 4  (없으면 "- 없음")
#   ## 손대는 폴더     - `agent/src/taxsplit/engine/`
# 같은 실행 안의 선행 PR → 같은 줄 뒤에 붙음. 손대는 폴더가 겹치면 → 한 줄로 합침.

# 제목이 "PR <번호>:"로 시작하는 열린 Issue의 JSON 한 개
find_issue() {
  "$GOAL_GH" issue list --state open --limit 300 --json number,title,labels \
    --jq "[.[] | select(.title | startswith(\"PR $1:\"))] | first // empty"
}

# 본문(stdin)에서 제목이 $1인 절의 목록 항목을 한 줄에 하나씩 뽑는다. 절이 없으면 1.
parse_field() {
  awk -v h="$1" '
    /^#+[[:space:]]/ {
      if (inside) exit
      t = $0; sub(/^#+[[:space:]]*/, "", t); sub(/[[:space:]]+$/, "", t)
      if (t == h) { inside = 1; found = 1 }
      next
    }
    inside && /^[[:space:]]*[-*][[:space:]]+/ {
      s = $0; sub(/^[[:space:]]*[-*][[:space:]]+/, "", s); gsub(/`/, "", s); sub(/[[:space:]]+$/, "", s)
      if (s != "") print s
    }
    END { exit found ? 0 : 1 }'
}

# 작업 목록 PR $1이 이미 끝났는가: 제목이 "PR <번호>:"인 Issue가 닫혀 있고, 같은 번호의 열린 Issue가 없다.
# PR 제목은 사람·Claude마다 흔들릴 수 있어(11/18 묶음 1) 기획이 정한 Issue 제목으로 본다.
# PR이 merge되면 PR 설명의 "Closes #<Issue>"로 Issue가 닫힌다.
pred_merged() {
  local q="[.[] | select(.title | startswith(\"PR $1:\"))] | length"
  [[ $("$GOAL_GH" issue list --state closed --limit 300 --json title --jq "$q" 2>/dev/null) =~ ^[1-9] ]] \
    && [[ $("$GOAL_GH" issue list --state open --limit 300 --json title --jq "$q" 2>/dev/null) == 0 ]]
}

# PR 하나의 정보 JSON: {pr, issue, preds, folders, skip}. skip이 null이 아니면 시작하지 않는다.
# $1: PR 번호, $2: 이번 실행의 PR 번호들(공백으로 구분)
collect_issue() {
  local pr=$1 run=" $2 " j num body preds="" folders="" skip="" p
  j=$(find_issue "$pr")
  if [[ -z $j ]]; then
    jq -cn --arg pr "$pr" '{pr: $pr, issue: 0, preds: [], folders: [],
      skip: "시작 안 함: 제목이 \"PR \($pr):\"인 열린 Issue 없음"}'
    return
  fi
  num=$(jq -r .number <<<"$j")
  body=$("$GOAL_GH" issue view "$num" --json body --jq .body)
  if preds=$(parse_field "선행 PR" <<<"$body"); then
    # "4", "PR 4", "PR 4: …"에서 번호만 남긴다. "없음"은 번호가 아니라 빠진다.
    preds=$(sed -nE 's/^(PR[[:space:]]*)?([0-9]+[a-z]?).*/\2/p' <<<"$preds")
  else
    skip="칸 없음 (선행 PR)"
  fi
  folders=$(parse_field "손대는 폴더" <<<"$body") || true
  [[ -n $folders ]] || skip="${skip:+$skip, }칸 없음 (손대는 폴더)"
  for p in $preds; do
    [[ $run == *" $p "* ]] && continue
    pred_merged "$p" || skip="${skip:+$skip, }선행 PR $p 가 merge 안 됐고 이번 실행에도 없음"
  done
  jq -cn --arg pr "$pr" --argjson issue "$num" --arg preds "$preds" --arg folders "$folders" \
    --arg skip "$skip" '{pr: $pr, issue: $issue,
      preds: ($preds | split("\n") | map(select(. != ""))),
      folders: ($folders | split("\n") | map(select(. != ""))),
      skip: (if $skip == "" then null else "시작 안 함: " + $skip end)}'
}

# stdin: collect_issue 결과를 이번 실행 순서대로 모은 JSON 배열
# stdout: 한 줄에 줄 하나 "lane-<첫 PR> <PR> <PR> ..." (줄 안은 선행 PR이 먼저 오게)
# 시작하지 않을 Issue는 줄에 넣지 않는다 (선행 PR이 시작 안 하면 뒤도 시작 안 함).
plan_lanes() {
  jq -r '
    def norm: sub("/+$"; "");
    def ov($a; $b): any($a[] | norm; . as $x
      | any($b[] | norm; . == $x or startswith($x + "/") or ($x | startswith(. + "/"))));
    def pos($x): . as $arr | first(range(0; $arr | length) | select($arr[.] == $x)) // null;
    def has($x): pos($x) != null;
    . as $all | ($all | map(.pr)) as $ids
    # 선행 PR이 시작 안 하면 뒤 Issue도 시작 안 함 (끝까지 퍼뜨린다)
    | (reduce range(0; $all | length) as $_ ($all; . as $cur | map(
        if .skip == null and any(.preds[]; . as $p | any($cur[]; .pr == $p and .skip != null))
        then .skip = "시작 안 함: 선행 PR이 시작되지 않음" else . end))) as $res
    | ($res | map(select(.skip == null))) as $run
    | ($run | map(.pr)) as $rids
    # 이을 것: 선행 PR 관계 + 손대는 폴더가 겹치는 쌍
    | ([$run[] as $a | $a.preds[] | select(. as $p | $rids | has($p)) | [., $a.pr]]
       + [range(0; $run | length) as $i | range($i + 1; $run | length) as $j
          | select(ov($run[$i].folders; $run[$j].folders)) | [$run[$i].pr, $run[$j].pr]]) as $edges
    # 이어진 것끼리 한 묶음으로 합친다
    | (reduce $edges[] as $e ($rids | map([.]);
        (map(select(has($e[0]) or has($e[1]))) | add) as $m
        | map(select((has($e[0]) or has($e[1])) | not)) + [$m])) as $groups
    # 묶음 안 순서: 실행 순서대로 두되, 선행 PR이 먼저 오게 한다
    | $groups | map(. as $g | reduce range(0; $g | length) as $_ ([]; . as $done
        | ($g | map(select(. as $p | ($done | has($p)) | not)) | sort_by(. as $p | $ids | pos($p))) as $left
        | ($left | map(select(. as $p | all($res[] | select(.pr == $p) | .preds[];
            . as $q | (($g | has($q)) | not) or ($done | has($q))))) | first) as $next
        | . + [$next // $left[0]]))
    | sort_by(.[0] as $p | $ids | pos($p))
    | .[] | "lane-\(.[0]) \(join(" "))"'
}
