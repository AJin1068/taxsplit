# ADR-0009. 여러 Issue를 goal로 연속 실행하고, 통과는 스크립트의 기계 검문으로 정한다

- 상태: 승인됨
- 날짜: 2026-11-17
- 결정자: 서아진

## 맥락

개발 세션은 Issue 하나마다 사람이 계획을 승인하고, merge를 기다리고, "계속해줘"를 쳐야 다음으로 갔다. 11/22까지 PR 4~21을 해야 하는데 사람 손이 묶이는 시간 대부분이 기다림이었다.

Claude Code의 `/goal`은 끝나는 조건을 주면 조건을 채울 때까지 턴을 스스로 이어 간다. 하지만 공식 문서("How evaluation works")에 따르면 판정 모델은 명령을 돌리거나 파일을 읽지 않고 대화만 읽는다. 그래서 "통과했다"는 말만으로 끝날 수 있다.

## 결정

- 규칙 세 가지를 바꾼다 (11/17 사용자 결정).
  1. 기획은 앞 PR merge를 기다리지 않고 여러 Issue를 미리 채울 수 있다. `ready`는 여전히 사람이 Issue를 보고 승인한 뒤에만 붙는다.
  2. 계획 승인은 Issue마다가 아니라 묶음으로 한 번 한다. 표시는 사람이 붙이는 `plan-ok` 라벨이다. 개발 세션·검증 Action·스크립트는 `plan-ok`를 붙이지 않는다.
     - (11/19 바뀜, PR 1x #107) `[계획]`의 "정할 것"이 `- 없음`이면 `plan-ok` 없이 시작한다. `plan-ok`는 "정할 것"이 남은 Issue에 사람이 답한 표시다. 지금 규칙은 CLAUDE.md "작업 순서" 2번과 "goal 연속 실행".
  3. 앞 PR이 merge되기 전에도 그 브랜치 위에 다음 Issue를 쌓아 진행할 수 있다. merge는 여전히 사람만, 쌓인 순서대로 한다.
- **통과는 기계 검문으로**: goal의 판정 모델은 "다음 턴을 할지" 신호로만 쓴다. 통과 여부는 `scripts/goal-run.sh`가 goal이 끝난 뒤 직접 다시 확인한 6항목으로 정한다(테스트·ruff, 막힌 폴더, 새 skip·지운 테스트, PR 모양, 지금 커밋의 `[검증]`, 손대는 폴더). 평가 하네스와 같은 원리다(ADR-0004 "정답은 외부에서 온다"). 떨어지면 떨어진 항목을 붙여 한 번만 다시 돌린다.
- **Issue마다 새 Claude** (`claude -p --permission-mode auto --permission-prompts none "/goal …"`): 한 대화로 몇 시간 돌리면 앞 Issue 내용이 섞이고, 자동 요약 때 규칙을 놓칠 수 있다.
- **줄(lane)로 병렬**: Issue 본문의 "선행 PR"·"손대는 폴더" 칸으로만 줄을 정한다(짐작하지 않음). 줄끼리는 동시에(기본 최대 3개, 동시 세션만큼 사용량이 늘어남), 줄 안은 쌓아서 순서대로. 줄마다 레포 밖 git worktree를 쓰고, 한 줄이 멈춰도 다른 줄은 계속한다. 손대는 폴더 밖 수정은 검문 6이 막는다.
- **휴대폰으로 보기**: `-p` 세션은 휴대폰에서 볼 수 없어서, 대화형 지휘 세션(`claude --remote-control … --permission-mode auto`, `/goal-run`)이 스크립트를 띄우고 `status.md`·`result.json`을 지켜보다 푸시로 알린다. 지휘 세션은 코드를 고치지 않는다.
- 기존 GitHub 장치(검증 Action, `guard`, `eval/` 벽, 라벨, PR 템플릿, `.claude/settings.json` 금지 목록)는 바꾸지 않는다. `verify.yml`·`guard.yml`·`ci.yml`은 base를 가리지 않아 쌓인 PR에도 돈다. 금지 목록은 worktree 안의 `claude -p`에도 적용되는 것을 시험했다.

## 검토한 대안

- **goal 판정 모델에 맡기기**: 파일 하나로 끝나지만, 판정 모델이 대화만 보므로 "테스트 통과"라는 말과 실제 통과를 구별하지 못한다.
- **한 세션으로 여러 Issue**: 띄우는 비용이 적지만 앞 Issue 맥락이 섞이고, 자동 요약 뒤 CLAUDE.md 규칙을 놓칠 위험이 있다.
- **실행 장치를 Python으로**: JSON 처리와 pytest 시험이 쉽지만, `agent/` 패키지 밖에 Python 실행 장치가 하나 더 생긴다. bash와 jq로 하고 가짜 명령으로 시험한다.
- **agent teams**(실험 기능, 기본 꺼짐, worktree 분리 없음)·**dynamic workflows**(한 세션 안에서 보조 Claude 여럿): 우리 일은 "Issue 하나 = 새 세션 하나 = PR 하나"라 스크립트로 직접 묶는 편이 검문을 넣기 쉽다.
- **공식 `--worktree` 옵션**: 쌓을 브랜치를 고르기 어려워, 스크립트가 `git worktree add --detach <base>`로 직접 만든다.
- **`-p` 세션마다 Remote Control 켜기**: 공식 문서가 대화형 세션만 다룬다. 지휘 세션 하나만 연다.

## 결과

- 좋은 점: 사람 손은 돌리기 전(Issue·계획 승인)과 끝난 뒤(merge·질문 답)에만 든다. 통과 판정이 말이 아니라 명령 결과에서 온다.
- 나쁜 점: 쌓인 PR은 앞 PR을 merge하고 브랜치를 지워야 base가 `main`으로 바뀐다. 레포 설정 "Automatically delete head branches"가 꺼져 있으면 사람이 `gh pr edit <번호> --base main`을 해야 한다.
- 나쁜 점: 개발 에이전트가 사람과 같은 계정이라 `[검증]` 코멘트를 흉내 낼 수 있다. 검문 5는 작성자가 `github-actions`이고 기준 커밋이 지금 PR head인 코멘트만 센다.
- 나쁜 점: 스크립트 시험(`scripts/goal/test-*.sh`)은 CI에 없다. `ci.yml`이 감시 대상이라 별도 Issue로 넣는다.
