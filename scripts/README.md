# scripts

## goal 연속 실행 (밤에 여러 Issue 돌리기)

사람이 "계속해줘"를 치지 않아도 여러 Issue를 밤새 돌리는 장치입니다. 규칙은 `CLAUDE.md` "goal 연속 실행", 결정과 이유는 `docs/adr/0009-goal-runner.md`에 있습니다.

| 파일 | 하는 일 |
| --- | --- |
| `goal-run.sh` | 시작 명령. 줄(lane)을 나누고, 줄마다 작업 폴더를 만들어 동시에 돌리고, 요약을 만든다 |
| `goal/lib-lanes.sh` | Issue의 "선행 PR"·"손대는 폴더" 칸을 읽어 줄로 묶는다 |
| `goal/lib-lane.sh` | 줄 하나를 순서대로 돌린다 (시작 조건 → 쌓기 → goal → 검문 → 재시도 → 결과) |
| `goal/lib-run.sh` | Claude를 `/goal`로 띄우고 시간 상한을 지킨다. 조건문을 채운다. 결과 파일을 쓴다 |
| `goal/lib-checks.sh` | 기계 검문 6항목 |
| `goal/lib-status.sh` | 휴대폰에서 볼 `status.md`를 고쳐 쓴다 |
| `goal/lib-summary.sh` | 아침에 볼 `summary.md`를 만든다 |
| `goal/test-*.sh`, `goal/fakes/` | 가짜 claude·gh·uv로 하는 시험 (실제 GitHub·Claude에 접속하지 않음) |

### 휴대폰으로 보기: 처음 한 번 세팅

1. 휴대폰에 Claude 앱을 설치하고, 맥북 Claude Code와 **같은 계정**으로 로그인합니다. 알림 권한을 허용합니다.
2. 맥북 터미널에서 `claude`를 켜고 `/config`에서 **Push when Claude decides**와 **Push when actions required**를 켭니다.
   - `/config`에 "No mobile registered"가 보이면 휴대폰 앱을 한 번 열어 주세요.
   - iPhone은 집중 모드나 알림 요약이 푸시를 막거나 늦출 수 있습니다(설정 → 알림 → Claude).

### 밤마다

3. 레포 루트에서 지휘 세션을 띄우고 명령을 줍니다.

   ```bash
   cd ~/dev/Workspace/taxsplit
   claude --remote-control "taxsplit 밤 실행" --permission-mode auto
   # 세션 안에서
   /goal-night 4 5 6 7
   ```

   - `--permission-mode auto`: 스크립트 실행과 감시를 시작할 때마다 승인을 묻지 않게 합니다. 위험한 동작은 auto 판정이 막고, `.claude/settings.json`의 금지 목록(merge, main push, `.env` 읽기 등)은 그대로 적용됩니다. 줄 작업 폴더(git worktree) 안의 Claude에도 적용되는 것을 시험했습니다(`cat .env`, `gh pr merge --help` 둘 다 거절됨).
   - 휴대폰 Claude 앱의 Code 탭에서 "taxsplit 밤 실행" 세션을 엽니다.
4. 맥북은 켜 둡니다. 스크립트가 `caffeinate`로 잠들지 않게 합니다. 덮개를 닫으면 멈출 수 있습니다.
   - 맥북 터미널을 보고 있거나 입력하는 동안에는 휴대폰 푸시가 오지 않습니다.
5. PR이 열리거나 `[검증]` 코멘트가 달리면 GitHub 모바일 앱으로도 알림이 옵니다.

터미널에서 바로 돌려도 됩니다(휴대폰 알림 없음):

```bash
scripts/goal-run.sh --minutes 90 --max-lanes 3 4 5 6 7
```

### 아침에

- `.goal-runs/<날짜_시각>/summary.md`를 봅니다. 줄별 상태, 검문 6항목, 걸린 시간, PR 링크, 사람이 답할 질문, merge 순서가 있습니다.
- 줄마다 표의 위에서 아래 순서로 merge합니다. 쌓인 PR은 base가 앞 브랜치입니다. 앞 PR을 merge하고 그 브랜치를 지우면 GitHub가 뒤 PR의 base를 `main`으로 바꿉니다. 지우지 않았다면 `gh pr edit <뒤 PR 번호> --base main`.
- 줄 작업 폴더는 지우지 않습니다. 다 보고 나면 `git worktree remove <작업 폴더>`.

### 시험

```bash
bash scripts/goal/test-checks.sh   # 검문 6항목, 통과·걸림 경우별
bash scripts/goal/test-lanes.sh    # 줄 나누기
bash scripts/goal/test-chain.sh    # 처음부터 끝까지 (재시도, 멈춤, 동시 실행, status.md, 줄 오류)
bash scripts/goal/test-scripts.sh  # 셸 함정: 변수 바로 뒤 한글 (맥북 bash 3.2에서 죽음)
```

출처: Remote Control https://code.claude.com/docs/en/remote-control , 모바일 https://code.claude.com/docs/en/mobile , `/goal` https://code.claude.com/docs/en/goal , 비대화 실행 https://code.claude.com/docs/en/headless
