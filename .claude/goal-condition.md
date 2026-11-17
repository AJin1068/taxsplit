이 레포의 개발 세션으로 작업 목록 PR {{PR}}(GitHub Issue #{{ISSUE}})를 끝낸다. 사람은 자리에 없다. 계획은 이미 승인됐다(Issue의 `plan-ok` 라벨과 `[계획]` 코멘트). CLAUDE.md를 먼저 읽고 따른다.

할 일:
1. `gh issue view {{ISSUE}} --json title,body,labels,comments`로 Issue 본문·코멘트·`[계획]` 코멘트를 읽는다. 계획대로만 구현한다.
2. 지금 HEAD는 `{{BASE}}`다. 여기서 CLAUDE.md 규칙대로 `<종류>/pr{{PR}}-<짧은 설명>` 브랜치를 만든다.
3. 구현하고 `agent/`에서 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`를 돌린다. 커밋하고 push한다.
4. `gh pr create --base {{BASE}}`로 PR을 연다. 설명은 `.github/pull_request_template.md`를 채우고 `Closes #{{ISSUE}}`를 쓴다. Issue에 `needs-verify`가 있으면 `--label needs-verify`를 붙인다.

끝나는 조건 (셋 중 하나가 대화에 보이면 끝):
(가) 승인된 `[계획]`대로 구현했고, 마지막 커밋 뒤에 돌린 세 명령이 모두 통과한 출력이 보이고, PR을 열어 PR 주소가 보인다.
(나) Issue·`[계획]`·문서·ADR에 답이 없는 결정이 필요하다. 그러면 추측해서 진행하지 않는다. PR(초안이라도)의 "확인해 주세요"에 질문을 CLAUDE.md "PR 설명 쓰는 법"대로 적고, 같은 질문을 `{{BLOCKED_FILE}}` 파일에 쓴다. 파일을 쓴 출력이 보이면 끝.
(다) 턴이 {{TURNS}}턴을 넘었다. 그러면 하던 것을 커밋·push하고 남은 일을 PR 설명(없으면 초안 PR을 열어서)의 "다음에 할 것"에 적고 멈춘다.

이 Issue가 고칠 수 있는 곳("손대는 폴더"). 이 밖은 읽기만 한다. 밖을 고쳐야 하면 (나)로 끝낸다:
{{FOLDERS}}

컨텍스트 아끼기: 파일 찾기·긴 로그 읽기·넓은 검색은 subagent(따로 일하고 요약만 돌려주는 보조 Claude)에게 맡긴다.

지킬 것:
- CLAUDE.md "작업 순서" 3~6번과 "벽" 절을 지킨다.
- merge, 승인, 라벨 `ready`·`plan-ok`·`infra-ok` 붙이기, force push, rebase를 하지 않는다.
- `eval/`, `.github/`, `.claude/`를 고치지 않는다. 테스트를 건너뛰거나(skip·xfail) 지워서 통과시키지 않는다.
- 계획에 없는 새 단계·외부 서비스·DB 구조·화면이 필요하면 만들지 않고 (나)로 끝낸다.
- `[검증]` 코멘트는 직접 쓰지 않는다. 검증 Action이 단다.
- 끝나기 전에 커밋 안 된 변경을 남기지 않는다.

앞 실행에서 기계 검문에 떨어진 것 (있으면 먼저 고친다):
{{RETRY_NOTES}}
