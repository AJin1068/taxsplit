"""PR 무게 판정: 사람이 꼼꼼히 볼 PR(무거움)과 아닌 PR(가벼움)을 기계로 나눈다.

기준은 CLAUDE.md "PR 무게" 한 곳에 있다. 하나라도 걸리면 무거움:
  (가) eval/(정답·채점)을 고침
  (나) needs-verify 라벨(점수가 나오는 PR)
  (다) "확인해 주세요"에 "누가 답하나: 사람"인데 ✅·➡️가 없는 항목
  (라) 바뀐 규칙표 규칙 중 바깥 정답 사례가 한 번도 안 지나간 것
       (사례 비교 코드 agent/tests/cases/가 바뀌면 사례 수를 그대로 믿지 않고 무겁게 본다)

검증 Action이 main에 있는 이 파일로 돌린다(PR이 자기 무게를 고쳐 쓰지 못하게).
파이썬 기본 기능, git, gh만 쓴다. 사용법:
    python3 .github/scripts/pr_weight.py --pr 110 --coverage cov.json [--out weight.json]
"""

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

LABEL = "human-review"
RULES_FILE = re.compile(r"^agent/src/taxsplit/rules/rules_\d{4}\.toml$")
CASE_CODE_DIR = "agent/tests/cases/"
_SECTION = re.compile(r"^#{1,2} ", re.MULTILINE)
_WHO_HUMAN = re.compile(r"누가 답하나\**\s*[:：]\s*\**\s*사람")
_WEIGHT_TAIL = re.compile(r" / 무게: .*$")


def rule_rows(text: str) -> dict[str, dict]:
    """규칙표 TOML 글자 → {규칙 ID: 그 줄 전체}. 주석만 바뀌면 같은 값이 나온다."""
    if not text.strip():
        return {}
    return {row["id"]: row for row in tomllib.loads(text).get("rule", [])}


def changed_rule_ids(base_text: str, head_text: str) -> set[str]:
    """추가·삭제·값이 바뀐 규칙 ID."""
    base, head = rule_rows(base_text), rule_rows(head_text)
    return {i for i in base.keys() | head.keys() if base.get(i) != head.get(i)}


def open_human_items(body: str) -> list[str]:
    """확인해 주세요 칸에서 사람이 답할, 아직 ✅·➡️가 없는 항목 제목."""
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    start = re.search(r"^## 확인해 주세요\s*$", body, re.MULTILINE)
    if not start:
        return []
    rest = body[start.end() :]
    end = _SECTION.search(rest)
    section = rest[: end.start()] if end else rest
    items = []
    for chunk in re.split(r"^### ", section, flags=re.MULTILINE)[1:]:
        title = chunk.splitlines()[0].strip()
        if title.startswith(("✅", "➡️", "➡")):
            continue
        if _WHO_HUMAN.search(chunk):
            items.append(title)
    return items


def judge(files, labels, body, changed_rules, coverage) -> dict:
    """무게와 이유. coverage는 {규칙 ID: 사례 수}, 없는 ID는 0건으로 본다."""
    reasons: list[tuple[str, str]] = []
    evals = [f for f in files if f.startswith("eval/")]
    if evals:
        reasons.append(("가", f"eval/ 파일 {len(evals)}개를 고침"))
    if "needs-verify" in labels:
        reasons.append(("나", "needs-verify 라벨(점수가 나오는 PR)"))
    items = open_human_items(body)
    if items:
        reasons.append(("다", "사람이 답할 열린 항목: " + " / ".join(items)))
    counts = {i: coverage.get(i, 0) for i in sorted(changed_rules)}
    zero = [i for i, n in counts.items() if n == 0]
    if zero:
        reasons.append(("라", "사례가 지나가지 않는 규칙을 바꿈: " + ", ".join(zero)))
    if any(f.startswith(CASE_CODE_DIR) for f in files):
        reasons.append(("라", "사례 비교 코드(agent/tests/cases/)가 바뀌어 사례 수를 믿지 않음"))
    criteria = sorted({c for c, _ in reasons})
    return {
        "weight": "무거움" if reasons else "가벼움",
        "criteria": criteria,
        "reasons": [f"({c}) {text}" for c, text in reasons],
        "changed_rules": counts,
    }


def weight_text(result: dict) -> str:
    if result["weight"] == "가벼움":
        return "무게: 가벼움"
    return f"무게: 무거움 ({'·'.join(result['criteria'])})"


def with_weight(body: str, result: dict) -> str:
    """[검증] 첫 줄 끝에 기계 판정 무게를 붙이고, 바로 아래에 이유 칸을 넣는다."""
    first, _, rest = body.partition("\n")
    first = f"{_WEIGHT_TAIL.sub('', first)} / {weight_text(result)}"
    lines = ["", "### PR 무게 (기계 판정)", ""]
    lines += [f"- {r}" for r in result["reasons"]] or ["- 기준 (가)~(라)에 걸린 것 없음"]
    for rule_id, n in result["changed_rules"].items():
        lines.append(f"- 바뀐 규칙 `{rule_id}`: 지나가는 바깥 정답 사례 {n}개")
    return "\n".join([first, *lines, rest]) if rest else "\n".join([first, *lines])


def _run(*cmd: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, check=False)


def _must(*cmd: str) -> str:
    result = _run(*cmd)
    if result.returncode != 0:
        sys.exit(f"{' '.join(cmd[:3])} 실패: {result.stderr.strip()}")
    return result.stdout


def label_action(heavy: bool, labels: set[str]) -> str | None:
    """붙일지("add")·뗄지("remove")·그대로(None)."""
    if heavy and LABEL not in labels:
        return "add"
    if not heavy and LABEL in labels:
        return "remove"
    return None


def sync_label(repo: str, pr: int, heavy: bool, labels: set[str], dry_run=False) -> str:
    """무거우면 human-review를 붙이고, 가벼우면 뗀다. 레포에 라벨이 없으면 만든다."""
    action = label_action(heavy, labels)
    if action is None or dry_run:
        return f"{LABEL} 라벨: {action or '그대로'}{' (dry-run)' if dry_run else ''}"
    if action == "add":
        if _run("gh", "api", f"repos/{repo}/labels/{LABEL}").returncode != 0:
            _must("gh", "api", "-X", "POST", f"repos/{repo}/labels", "-f", f"name={LABEL}",
                  "-f", "color=d93f0b", "-f", "description=사람이 꼼꼼히 볼 무거운 PR")  # fmt: skip
        _must(
            "gh", "api", "-X", "POST", f"repos/{repo}/issues/{pr}/labels", "-f", f"labels[]={LABEL}"
        )
    else:
        _must("gh", "api", "-X", "DELETE", f"repos/{repo}/issues/{pr}/labels/{LABEL}")
    return f"{LABEL} 라벨: {action}"


def _rule_texts(path: str, base: str) -> tuple[str, str]:
    """main(또는 앞 브랜치) 쪽과 PR 쪽 규칙표 글자. 없으면 빈 글자."""
    old = _run("git", "show", f"{base}:{path}")
    head = Path(path)
    return (old.stdout if old.returncode == 0 else ""), (
        head.read_text(encoding="utf-8") if head.exists() else ""
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="PR 무게 판정")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--repo", default="")
    parser.add_argument("--coverage", help="rule_coverage.py --json 결과. 없으면 모두 0건")
    parser.add_argument("--out", help="판정 결과 JSON을 쓸 곳")
    args = parser.parse_args()

    repo = ["--repo", args.repo] if args.repo else []
    info = json.loads(
        _must("gh", "pr", "view", str(args.pr), *repo, "--json", "labels,body,baseRefName")
    )
    files = _must("gh", "pr", "diff", str(args.pr), *repo, "--name-only").splitlines()
    base = _must("git", "merge-base", f"origin/{info['baseRefName']}", "HEAD").strip()
    changed: set[str] = set()
    for path in filter(RULES_FILE.match, files):
        changed |= changed_rule_ids(*_rule_texts(path, base))
    coverage = {}
    if args.coverage and Path(args.coverage).exists() and Path(args.coverage).stat().st_size:
        coverage = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    labels = {label["name"] for label in info["labels"]}
    result = judge(files, labels, info["body"], changed, coverage)
    result["labels"] = sorted(labels)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
