"""감시 검사(guard). PR이 바꾼 파일 목록만 보고 벽을 지킨다 (ADR-0005, ADR-0008).

`pull_request_target`으로 `main`의 이 파일이 돈다. PR 코드는 받지도 실행하지도 않는다.
바뀐 파일 목록과 라벨은 GitHub API에서 받는다.

규칙
① 감시 대상 파일(`.github/**`, `.claude/commands/verify-pr.md`, `.claude/settings.json`)이
   바뀌었는데 `infra-ok` 라벨이 없으면 실패한다. 사람이 diff를 보고 라벨을 붙이면 풀린다.
② `eval/` 벽: `eval/` 변경(`eval/README.md` 제외)은 head 브랜치가 `eval/`로 시작할 때만 허용한다.
   이 규칙은 `infra-ok`로 풀리지 않는다.

파이썬 기본 기능과 `gh` 명령만 쓴다. 사용법:
    python3 .github/scripts/guard.py --pr 64 --repo OWNER/REPO --head-ref chore/pr01l-x
"""

import argparse
import json
import subprocess
import sys

INFRA_OK = "infra-ok"

# 규칙 ①: 앞부분이 같으면 감시 대상(폴더), 이름이 같으면 감시 대상(파일)
GUARDED_PREFIXES = (".github/",)
GUARDED_FILES = {".claude/commands/verify-pr.md", ".claude/settings.json"}

# 규칙 ②: eval/ 아래는 벽, 단 README는 누구나 고칠 수 있다
EVAL_PREFIX = "eval/"
EVAL_EXEMPT = {"eval/README.md"}

RULE_INFRA = "① 감시 대상 파일 (infra-ok 라벨 필요)"
RULE_EVAL = "② eval/ 벽 (eval/ 브랜치에서만, infra-ok로 안 풀림)"


def is_guarded(path: str) -> bool:
    return path in GUARDED_FILES or path.startswith(GUARDED_PREFIXES)


def is_eval(path: str) -> bool:
    return path.startswith(EVAL_PREFIX) and path not in EVAL_EXEMPT


def check(files: list[str], head_ref: str, labels: set[str]) -> list[tuple[str, str]]:
    """규칙에 걸린 (파일, 규칙) 목록을 돌려준다. 비어 있으면 통과."""
    violations: list[tuple[str, str]] = []
    for path in sorted(set(files)):
        # 규칙 ①: 사람이 infra-ok를 붙였으면 통과
        if is_guarded(path) and INFRA_OK not in labels:
            violations.append((path, RULE_INFRA))
        # 규칙 ②: eval/ 브랜치가 아니면 라벨과 상관없이 실패
        if is_eval(path) and not head_ref.startswith(EVAL_PREFIX):
            violations.append((path, RULE_EVAL))
    return violations


def gh_json(*args: str):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:2])} 실패: {result.stderr.strip()}")
    return json.loads(result.stdout or "null")


def fetch_changed_files(repo: str, pr: int) -> list[str]:
    """PR이 바꾼 파일. 이름을 바꾼 파일은 원래 이름도 넣는다(eval/ 밖으로 옮겨 피하는 것 막기)."""
    pages = gh_json("api", "--paginate", "--slurp", f"repos/{repo}/pulls/{pr}/files?per_page=100")
    files: list[str] = []
    for page in pages:
        for item in page:
            files.append(item["filename"])
            if item.get("previous_filename"):
                files.append(item["previous_filename"])
    return files


def fetch_labels(repo: str, pr: int) -> set[str]:
    """라벨은 실행할 때 다시 읽는다. 방금 붙인 infra-ok가 반영되게."""
    data = gh_json("api", f"repos/{repo}/issues/{pr}/labels")
    return {label["name"] for label in data}


def main() -> int:
    parser = argparse.ArgumentParser(description="PR 벽 감시 검사")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--head-ref", required=True)
    args = parser.parse_args()

    files = fetch_changed_files(args.repo, args.pr)
    labels = fetch_labels(args.repo, args.pr)
    violations = check(files, args.head_ref, labels)

    print(f"바뀐 파일 {len(files)}개, 라벨: {sorted(labels) or '없음'}, 브랜치: {args.head_ref}")
    if not violations:
        print("감시 검사 통과")
        return 0
    for path, rule in violations:
        print(f"::error file={path}::{path} → {rule}")
    print("\n걸린 파일:")
    for path, rule in violations:
        print(f"  - {path} → {rule}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
