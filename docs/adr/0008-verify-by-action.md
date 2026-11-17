# ADR-0008. 검증은 GitHub Action이 하고, 맥락은 대화방이 아니라 레포에 둔다

- 상태: 승인됨
- 날짜: 2026-11-17
- 결정자: 서아진

## 맥락

ADR-0005 이후 일은 Claude 앱의 여러 스레드(기획·검증·총괄)와 IDE 개발 세션이 나눠 했다. 그러다 보니 사람이 한 일의 대부분이 판단이 아니라 전달이었다. 검증 스레드를 열고, 찾은 내용을 총괄 스레드로 옮기고, `[총괄]` 코멘트를 받아 개발 세션에 넘겼다. 2시간마다 열린 PR을 훑는 예약 작업도 돌렸지만(지금은 꺼짐) 결과가 다시 대화방에 쌓였다.

또 ADR-0005는 점수 없는 PR을 검증하지 않았다. 사용자는 11/16에 "매번 검증해야 하는 거 아냐?"라며 모든 PR이 검증되길 원했다.

## 결정

- **검증 Action** (`.github/workflows/verify.yml`): PR이 열리거나, 새 커밋이 오거나, 다시 열리거나, draft에서 나오거나, `needs-verify` 라벨이 붙으면 Claude Code GitHub Action이 새 문맥에서 PR을 검증한다. 모든 PR에 돈다.
- **코멘트 하나**: 결과는 `[검증]` 코멘트 하나로 남고 새 커밋마다 고쳐 쓴다. 모델은 파일만 쓰고, 올리는 일은 `.github/scripts/post_verify.py`가 한다.
- **지시서는 레포에**: 할 일과 형식은 `.claude/commands/verify-pr.md` 한 곳에 둔다. Action과 IDE `/verify-pr`가 같은 파일을 쓴다. Action은 지시서와 올리기 스크립트를 `main`에서 가져온다(`main`에 없을 때만 PR 것).
- **점수 PR은 라벨로**: 점수가 나오는 PR은 `needs-verify` 라벨로 표시한다. 기획이 Issue에 붙이고, 개발 세션이 PR에 옮겨 붙인다. 평가 하네스(PR 11) 전에는 "점수 재측정: 아직 장치 없음(PR 11 이후)"만 적는다.
- **고칠 거리는 바로 Issue로**: 다음 PR에서 할 일은 해당 "PR N"의 열린 Issue에 코멘트로 남긴다. 없을 때만 `ready` 없이 새 Issue를 만든다.
- **인증과 권한**: Claude 구독 토큰(Secret `CLAUDE_CODE_OAUTH_TOKEN`)을 쓴다. GitHub 접속은 workflow 기본 토큰(`GITHUB_TOKEN`)을 쓴다. 권한은 `contents: read`, `pull-requests: write`, `issues: write`만 둔다. 모델이 쓸 수 있는 도구는 읽기와 `git`·`gh` 조회뿐이다. 테스트·ruff는 workflow 단계가 돌려 결과 파일로 넘긴다.
- **없애는 것**: 검증·총괄 스레드, `[총괄]` 코멘트, 2시간 예약 작업.
- **앱(Claude)에 남는 것**: 기획(Issue 쓰기, `ready`·`needs-verify` 붙이기), `eval/` 정답 만들기(원본 책자가 레포 밖이라 Action이 못 본다), 홀드아웃 재기(레포에 두면 안 된다).

## 검토한 대안

- **스레드 구조 유지, 검증 스레드를 모든 PR로 넓히기**: 사람이 옮기는 일이 PR 수만큼 늘어난다.
- **액션의 코멘트 기능(`use_sticky_comment`)에 맡기기**: 파일이 하나 줄지만, 모델에게 쓰기 도구를 줘야 하고 IDE와 올리는 방법이 갈린다.
- **Claude GitHub App 토큰**: 코멘트 작성자가 Claude로 보이지만 `id-token: write` 권한이 하나 더 필요하다.

## 결과

- 좋은 점: 사람은 Issue를 쓰고, 코멘트를 읽고, merge하면 된다. 모든 PR이 같은 기준으로 검증된다. 검증 내용이 PR에 남아 나중에 다시 볼 수 있다.
- 나쁜 점: `pull_request` 이벤트는 workflow 파일을 PR 브랜치에서 읽는다. PR이 `verify.yml`을 고치면 그 PR에서는 고친 검증이 돈다. 그래서 검증 장치(`verify.yml`, `verify-pr.md`, `post_verify.py`)가 바뀐 PR은 `[검증]` 첫 줄에 "검증 장치 변경, 사람 확인 필요"를 띄우고 사람이 diff를 직접 본다. 이 경고는 GitHub에서 받은 바뀐 파일 목록으로 스크립트가 붙인다.
- 나쁜 점: 검증 Action은 merge 필수 검사가 아니다. merge 판단은 사람이 코멘트를 보고 한다. 점수가 기준선보다 낮을 때 CI를 실패시키는 일은 PR 11 뒤 별도 Issue로 한다.

## 갱신 (2026-11-17, PR 1l)

- **감시 검사 `guard`** (`.github/workflows/guard.yml`, `.github/scripts/guard.py`): `pull_request_target`으로 돌아서 PR 쪽이 아니라 `main`에 있는 설정과 스크립트를 쓴다. PR이 이 검사를 고쳐서 끌 수 없다. PR 코드는 checkout·실행하지 않고, 바뀐 파일 목록은 GitHub API(PR files)로 받는다. Secret 없이 `contents: read`, `pull-requests: read`만 쓴다.
  - 규칙 ①: 감시 대상 파일(`.github/**`, `.claude/commands/verify-pr.md`, `.claude/settings.json`)이 바뀌면 실패한다. 사람이 diff를 보고 **`infra-ok` 라벨**을 붙이면 다시 돌아 통과한다.
  - 규칙 ②: `eval/` 벽(`eval/README.md` 제외). head 브랜치가 `eval/`로 시작할 때만 허용한다. `infra-ok`로 풀리지 않는다. 지금까지의 CI `eval-guard`를 대신한다.
- 위 "나쁜 점"의 첫 항목 중 **벽 검사**는 이것으로 막힌다. 검증 장치를 고친 PR은 경고 문구뿐 아니라 빨간불이 뜬다.
- 남은 한계:
  - 검증 Action(`verify.yml`) 자체는 여전히 `pull_request`로 PR 쪽 파일을 쓴다. `workflow_run`으로 나누는 일은 v1(11/22) 뒤 별도 Issue로 한다.
  - 개발 에이전트가 사람과 같은 계정이라 `infra-ok`를 직접 붙일 수 있다. 계정·토큰 분리는 별도 Issue로 한다. 지금은 "개발 세션은 `infra-ok`를 붙이지 않는다"는 규칙(`CLAUDE.md` "벽")으로만 지킨다.
  - 필수 검사(ruleset)에 `guard`를 넣는 일은 사람이 GitHub 설정에서 한다.
