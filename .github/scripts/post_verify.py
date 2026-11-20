"""검증 결과를 GitHub에 올린다. GitHub Action과 IDE(/verify-pr)가 같이 쓴다.

하는 일 세 가지:
1. `[검증]` 코멘트를 PR에 하나만 둔다. 숨은 표시가 붙은 코멘트가 있으면 고쳐 쓰고, 없으면 새로 단다.
2. 다음 PR에서 할 일(followups.json)을 해당 "PR N" 열린 Issue에 코멘트로 남긴다.
   그런 Issue가 없으면 `ready` 없이 새 Issue를 만든다. 새 Issue 제목은 `[할 일] PR N 뒤: …`이다.
   `PR N:`으로 시작하면 goal의 선행 PR 판정(같은 번호의 열린 Issue가 있으면 안 끝남)과
   "새 PR 번호는 비어 있을 때만 쓴다" 규칙에 걸리므로 `PR `으로 시작하지 않게 한다.
3. PR 무게(weight.json, pr_weight.py가 만든 것)가 있으면 첫 줄에 무게를 붙이고
   무거우면 `human-review` 라벨을 붙인다(가벼우면 뗀다). 모델의 말이 아니라 이 파일을 따른다.

파이썬 기본 기능과 `gh` 명령만 쓴다. 사용법:
    python3 .github/scripts/post_verify.py --pr 61 [--dir .verify-out] [--dry-run]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 같은 폴더의 pr_weight.py (Action에서는 둘 다 main에서 .verify-out/로 가져온다)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_weight  # noqa: E402

# 같은 PR의 [검증] 코멘트를 찾는 숨은 표시. 바꾸면 기존 코멘트를 못 찾아 새로 달린다.
MARKER = "<!-- taxsplit-verify -->"

# 이 파일이 바뀐 PR은 검증 장치 자체가 바뀐 것이라 사람이 diff를 봐야 한다.
GUARDED_FILES = {
    ".github/workflows/verify.yml",
    ".claude/commands/verify-pr.md",
    ".github/scripts/post_verify.py",
    ".github/scripts/pr_weight.py",
    ".github/scripts/reweigh.py",
}
GUARD_WARNING = "⚠️ 검증 장치 변경, 사람 확인 필요"


def gh(*args: str, stdin: str | None = None) -> str:
    """gh 명령을 실행하고 표준 출력을 돌려준다. 실패하면 바로 멈춘다."""
    result = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:3])} 실패: {result.stderr.strip()}")
    return result.stdout


def gh_json(*args: str):
    return json.loads(gh(*args) or "null")


def add_guard_warning(body: str, changed: list[str]) -> str:
    """검증 장치 파일이 바뀌었으면 첫 줄의 `[검증]` 바로 뒤에 경고를 넣는다."""
    if not GUARDED_FILES.intersection(changed) or GUARD_WARNING in body:
        return body
    first, _, rest = body.partition("\n")
    if first.startswith("[검증]"):
        first = f"[검증] {GUARD_WARNING} / {first[len('[검증]') :].strip()}"
    else:
        first = f"[검증] {GUARD_WARNING} / {first}"
    return f"{first}\n{rest}" if rest else first


def with_marker(body: str) -> str:
    return f"{body.rstrip()}\n\n{MARKER}\n"


def find_verify_comment(repo: str, pr: int) -> int | None:
    """PR에 이미 달린 [검증] 코멘트의 id를 찾는다. 없으면 None."""
    pages = gh_json("api", "--paginate", "--slurp", f"repos/{repo}/issues/{pr}/comments")
    for page in pages or []:
        for comment in page:
            if MARKER in (comment.get("body") or ""):
                return comment["id"]
    return None


def upsert_comment(repo: str, pr: int, body: str, dry_run: bool) -> str:
    """같은 코멘트를 고쳐 쓰거나 새로 단다. 무엇을 했는지 한 줄로 돌려준다."""
    payload = json.dumps({"body": body})
    comment_id = find_verify_comment(repo, pr)
    if comment_id is None:
        if not dry_run:
            gh("api", "--method", "POST", f"repos/{repo}/issues/{pr}/comments",
               "--input", "-", stdin=payload)  # fmt: skip
        return f"새 [검증] 코멘트를 PR #{pr}에 단다"
    if not dry_run:
        gh("api", "--method", "PATCH", f"repos/{repo}/issues/comments/{comment_id}",
           "--input", "-", stdin=payload)  # fmt: skip
    return f"기존 [검증] 코멘트({comment_id})를 고쳐 쓴다"


def find_issue_for(pr_label: str, open_issues: list[dict]) -> int | None:
    """제목이 `PR <번호>:`로 시작하는 열린 Issue를 찾는다. 예: "5" → "PR 5: ..." """
    pattern = re.compile(rf"^PR\s*{re.escape(pr_label)}\s*:", re.IGNORECASE)
    for issue in open_issues:
        if pattern.match(issue["title"]):
            return issue["number"]
    return None


def followup_title(pr_label: str, title: str) -> str:
    """새 할 일 Issue 제목. `PR `으로 시작하지 않아 작업(PR N:)으로 골라지지 않는다."""
    title = title.strip()
    # 모델이 제목을 "PR 5: …"처럼 써도 앞의 PR 번호를 떼어 내 작업 Issue로 보이지 않게 한다
    title = re.sub(r"^PR\s*[0-9][0-9a-z]*\s*:\s*", "", title, flags=re.IGNORECASE) or title
    return f"[할 일] PR {pr_label} 뒤: {title}" if pr_label else f"[할 일] {title}"


def post_followups(repo: str, source_pr: int, items: list[dict], dry_run: bool) -> list[str]:
    """다음 PR에서 할 일을 Issue로 넘긴다. `ready` 라벨은 붙이지 않는다."""
    if not items:
        return []
    open_issues = gh_json(
        "issue", "list", "--repo", repo, "--state", "open",
        "--limit", "300", "--json", "number,title",
    )  # fmt: skip
    log = []
    for item in items:
        pr_label = str(item.get("pr", "")).strip()
        body = f"[검증] PR #{source_pr} 검증에서 넘긴 할 일\n\n{item['body']}"
        number = find_issue_for(pr_label, open_issues) if pr_label else None
        if number is not None:
            if not dry_run:
                gh("issue", "comment", str(number), "--repo", repo,
                   "--body-file", "-", stdin=body)  # fmt: skip
            log.append(f"Issue #{number}(PR {pr_label})에 코멘트")
            continue
        title = followup_title(pr_label, item.get("title") or "검증에서 넘긴 할 일")
        if not dry_run:
            gh("issue", "create", "--repo", repo, "--title", title,
               "--body-file", "-", stdin=body)  # fmt: skip
        log.append(f"새 Issue '{title}' (ready 없음)")
    return log


def main() -> None:
    parser = argparse.ArgumentParser(description="[검증] 코멘트와 할 일을 올린다")
    parser.add_argument("--pr", type=int, required=True, help="GitHub PR 번호")
    parser.add_argument("--repo", help="owner/name. 비우면 현재 레포")
    parser.add_argument("--dir", default=".verify-out", help="결과 파일 폴더")
    parser.add_argument("--dry-run", action="store_true", help="올리지 않고 보여만")
    args = parser.parse_args()

    out_dir = Path(args.dir)
    comment_path = out_dir / "comment.md"
    if not comment_path.exists():
        sys.exit(f"{comment_path}가 없다. 검증 단계가 코멘트를 쓰지 못했다.")
    repo = args.repo or gh("repo", "view", "--json", "nameWithOwner",
                           "-q", ".nameWithOwner").strip()  # fmt: skip

    # 바뀐 파일 목록은 GitHub에서 직접 받는다(검증 모델의 말에 기대지 않는다).
    changed = gh("pr", "diff", str(args.pr), "--repo", repo, "--name-only").splitlines()
    body = add_guard_warning(comment_path.read_text(encoding="utf-8"), changed)
    weight_path = out_dir / "weight.json"
    weight = json.loads(weight_path.read_text(encoding="utf-8")) if weight_path.exists() else None
    if weight:
        body = pr_weight.with_weight(body, weight)
    body = with_marker(body)

    followups_path = out_dir / "followups.json"
    items = (
        json.loads(followups_path.read_text(encoding="utf-8")) if followups_path.exists() else []
    )

    print(upsert_comment(repo, args.pr, body, args.dry_run))
    for line in post_followups(repo, args.pr, items, args.dry_run):
        print(line)
    if weight:
        heavy = weight["weight"] == "무거움"
        labels = set(weight.get("labels", []))
        print(pr_weight.sync_label(repo, args.pr, heavy, labels, args.dry_run))
    if args.dry_run:
        print("--- 올릴 코멘트 (dry-run) ---")
        print(body)


if __name__ == "__main__":
    main()
