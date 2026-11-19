"""PR 설명만 바뀌었을 때(새 커밋 없음) [검증] 코멘트의 무게 부분과 human-review 라벨만 다시 맞춘다.

검증 Action의 가벼운 job(`reweigh`)이 쓴다. Claude를 부르지 않는다.
- 이미 달린 [검증] 코멘트를 찾아 첫 줄 끝 "/ 무게: …"와 "### PR 무게 (기계 판정)" 칸만 바꿔 쓴다.
  나머지(모델이 쓴 판정, "사람 확인 필요" 목록)는 그대로 둔다. 다음 커밋의 전체 검증이 다시 쓴다.
- [검증] 코멘트가 아직 없으면 아무것도 하지 않는다(첫 전체 검증이 곧 단다).

사용법:
    python3 .github/scripts/reweigh.py --pr 61 [--dir .verify-out] [--dry-run]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 같은 폴더의 pr_weight.py·post_verify.py (Action에서는 셋 다 main에서 .verify-out/로 가져온다)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_verify  # noqa: E402
import pr_weight  # noqa: E402

# with_weight가 첫 줄 바로 아래에 넣는 칸: 빈 줄, 제목, 빈 줄, "- …" 줄들
_WEIGHT_SECTION = re.compile(r"\n\n### PR 무게 \(기계 판정\)\n\n(?:- [^\n]*(?:\n|$))*")


def reweigh_body(body: str, result: dict) -> str:
    """옛 무게 칸·숨은 표시를 지우고 새 판정으로 다시 붙인다. 여러 번 해도 칸이 겹치지 않는다."""
    body = body.replace(post_verify.MARKER, "").rstrip()
    body = _WEIGHT_SECTION.sub("\n", body, count=1).rstrip()
    return post_verify.with_marker(pr_weight.with_weight(body, result))


def main() -> None:
    parser = argparse.ArgumentParser(description="설명만 바뀐 PR의 무게를 다시 맞춘다")
    parser.add_argument("--pr", type=int, required=True, help="GitHub PR 번호")
    parser.add_argument("--repo", help="owner/name. 비우면 현재 레포")
    parser.add_argument("--dir", default=".verify-out", help="weight.json이 있는 폴더")
    parser.add_argument("--dry-run", action="store_true", help="올리지 않고 보여만")
    args = parser.parse_args()

    weight_path = Path(args.dir) / "weight.json"
    if not weight_path.exists():
        sys.exit(f"{weight_path}가 없다. 무게 판정 단계가 실패했다.")
    weight = json.loads(weight_path.read_text(encoding="utf-8"))
    repo = args.repo or post_verify.gh("repo", "view", "--json", "nameWithOwner",
                                       "-q", ".nameWithOwner").strip()  # fmt: skip

    comment_id = post_verify.find_verify_comment(repo, args.pr)
    if comment_id is None:
        print(f"PR #{args.pr}에 [검증] 코멘트가 아직 없어 그대로 둔다")
        return
    old = post_verify.gh_json("api", f"repos/{repo}/issues/comments/{comment_id}")["body"]
    new = reweigh_body(old, weight)
    if new.strip() == old.strip():
        print("무게가 그대로라 코멘트를 고치지 않는다")
    else:
        print(post_verify.upsert_comment(repo, args.pr, new, args.dry_run))
    heavy = weight["weight"] == "무거움"
    print(pr_weight.sync_label(repo, args.pr, heavy, set(weight.get("labels", [])), args.dry_run))
    if args.dry_run:
        print("--- 고칠 코멘트 (dry-run) ---")
        print(new)


if __name__ == "__main__":
    main()
