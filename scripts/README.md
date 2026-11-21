# scripts

## goal 연속 실행 (여러 Issue를 이어서 돌리기)

사람이 "계속해줘"를 치지 않아도 여러 Issue를 몇 시간씩 이어서 돌리는 장치입니다. 낮이든 밤이든 돌릴 수 있습니다. 규칙은 `CLAUDE.md` "goal 연속 실행", 결정과 이유는 `docs/adr/0009-goal-runner.md`에 있습니다.

| 파일 | 하는 일 |
| --- | --- |
| `goal-run.sh` | 시작 명령. 줄(lane)을 나누고, 줄마다 작업 폴더를 만들어 동시에 돌리고, 요약을 만든다 |
| `goal/lib-lanes.sh` | Issue의 "선행 PR"·"손대는 폴더" 칸을 읽어 줄로 묶는다 |
| `goal/lib-lane.sh` | 줄 하나를 순서대로 돌린다 (시작 조건 → 쌓기 → goal → 검문 → 재시도 → 결과) |
| `goal/lib-run.sh` | Claude를 `/goal`로 띄우고 시간 상한을 지킨다. 조건문을 채운다. 결과 파일을 쓴다 |
| `goal/lib-checks.sh` | 기계 검문 6항목 |
| `goal/lib-status.sh` | 휴대폰에서 볼 `status.md`를 고쳐 쓴다 |
| `goal/lib-platform.sh` | OS마다 다른 곳을 맞춘다 (Windows jq의 CRLF) |
| `goal/lib-summary.sh` | 끝난 뒤 볼 `summary.md`를 만든다 |
| `goal/test-*.sh`, `goal/fakes/` | 가짜 claude·gh·uv로 하는 시험 (실제 GitHub·Claude에 접속하지 않음) |

### 휴대폰으로 보기: 처음 한 번 세팅

1. 휴대폰에 Claude 앱을 설치하고, 맥북 Claude Code와 **같은 계정**으로 로그인합니다. 알림 권한을 허용합니다.
2. 맥북 터미널에서 `claude`를 켜고 `/config`에서 **Push when Claude decides**와 **Push when actions required**를 켭니다.
   - `/config`에 "No mobile registered"가 보이면 휴대폰 앱을 한 번 열어 주세요.
   - iPhone은 집중 모드나 알림 요약이 푸시를 막거나 늦출 수 있습니다(설정 → 알림 → Claude).

### 어떤 Issue가 시작되나 (시작 조건)

`ready` 라벨과 `[계획]` 코멘트가 있고, 아래 둘 중 하나면 시작합니다. 둘 다 아니면 "시작 안 함: 정할 것 남음"으로 건너뜁니다.

1. `[계획]`의 `## 정할 것` 칸이 정확히 `- 없음`이다. 사람이 정할 것이 없다는 뜻이라 사람 승인 없이 시작합니다.
2. `plan-ok` 라벨이 있다. 사람이 "정할 것"에 답하고 붙인 표시입니다.

"정할 것" 칸이 없는 예전 `[계획]`은 "남음"으로 봅니다(`plan-ok`가 있으면 지금처럼 시작). 무엇을 "정할 것"에 적는지는 `CLAUDE.md` "작업 순서" 2번에 있습니다.

### 돌릴 때마다

3. 레포 루트에서 지휘 세션을 띄우고 명령을 줍니다.

   ```bash
   cd ~/dev/Workspace/taxsplit
   claude --remote-control "taxsplit goal 실행" --permission-mode auto
   # 세션 안에서
   /goal-run 4 5 6 7
   ```

   - `--permission-mode auto`: 스크립트 실행과 감시를 시작할 때마다 승인을 묻지 않게 합니다. 위험한 동작은 auto 판정이 막고, `.claude/settings.json`의 금지 목록(merge, main push, `.env` 읽기 등)은 그대로 적용됩니다. 줄 작업 폴더(git worktree) 안의 Claude에도 적용되는 것을 시험했습니다(`cat .env`, `gh pr merge --help` 둘 다 거절됨).
   - 휴대폰 Claude 앱의 Code 탭에서 "taxsplit goal 실행" 세션을 엽니다.
4. 맥북은 켜 둡니다. 스크립트가 `caffeinate`로 잠들지 않게 합니다. 덮개를 닫으면 멈출 수 있습니다.
   - 맥북 터미널을 보고 있거나 입력하는 동안에는 휴대폰 푸시가 오지 않습니다.
5. PR이 열리거나 `[검증]` 코멘트가 달리면 GitHub 모바일 앱으로도 알림이 옵니다.

터미널에서 바로 돌려도 됩니다(휴대폰 알림 없음):

```bash
scripts/goal-run.sh --minutes 90 --max-lanes 3 4 5 6 7
```

### 끝난 뒤

- `.goal-runs/<날짜_시각>/summary.md`를 봅니다. 줄별 상태, 검문 6항목, 걸린 시간, PR 링크, 사람이 답할 질문, merge 순서가 있습니다.
- 줄마다 표의 위에서 아래 순서로 merge합니다. 쌓인 PR은 base가 앞 브랜치입니다. 앞 PR을 merge하고 그 브랜치를 지우면 GitHub가 뒤 PR의 base를 `main`으로 바꿉니다. 지우지 않았다면 `gh pr edit <뒤 PR 번호> --base main`.
- 줄 작업 폴더는 지우지 않습니다. 다 보고 나면 `git worktree remove <작업 폴더>`.

### Windows에서 돌리기

**Git Bash**에서 돌립니다. Windows용 Claude Code도 Git Bash를 쓰기 때문입니다. PowerShell판은 따로 없습니다.

1. 도구가 있는지 확인합니다. 없으면 `winget`으로 설치합니다.

   ```bash
   jq --version        # 없으면: winget install jqlang.jq
   gh auth status      # 없으면: winget install GitHub.cli 뒤 gh auth login
   uv --version
   claude --version
   ```

   - 설치한 뒤에는 **VSCode나 터미널을 완전히 껐다 켭니다.** 새 PATH는 이미 떠 있는 프로그램과 그 안의 터미널에 들어가지 않습니다.
2. 레포를 이 PR(`.gitattributes`) 전에 받았다면 셸 스크립트가 CRLF일 수 있습니다. 커밋 안 한 변경이 없을 때만 아래 명령으로 LF로 다시 받습니다.

   ```bash
   git ls-files --eol scripts/ | grep -v 'w/lf'   # .sh·fakes가 나오면 CRLF
   git rm -rq --cached . && git reset -q --hard
   ```

3. 실행은 맥과 같습니다: `scripts/goal-run.sh 4 5 6`.
4. 실행 중에 PC가 잠들지 않게 합니다. 맥의 `caffeinate`가 Windows에는 없어서 스크립트가 막아 주지 않습니다. 설정 → 시스템 → 전원 → "화면 및 절전"에서 전원 연결 시 절전을 "안 함"으로 둡니다.

스크립트가 Windows를 위해 하는 것:
- `.gitattributes`로 `.sh`와 대역 스크립트를 LF로 고정합니다 (CRLF면 bash가 `$'\r': command not found`로 멈춤).
- `claude -p "/goal …"`를 부를 때 `MSYS2_ARG_CONV_EXCL=/goal`을 줍니다. Git Bash가 `/goal`을 `C:/Program Files/Git/goal`로 바꾸지 않게 합니다. 다른 경로는 그대로 Windows 경로로 바뀌어야 `jq.exe`가 파일을 엽니다.
- Windows용 `jq`는 줄 끝을 CRLF로 내므로 `jq -b`로 감쌉니다 (`goal/lib-platform.sh`).
- `status.md` 시작 시각은 BSD `date -r <초>`가 안 되면 GNU `date -d @<초>`로 냅니다.

WSL에서도 돌릴 수 있지만 claude·gh·uv·jq를 WSL 안에 따로 설치하고 로그인해야 합니다.

### 시험

```bash
bash scripts/goal/test-checks.sh   # 검문 6항목, 통과·걸림 경우별
bash scripts/goal/test-lanes.sh    # 줄 나누기
bash scripts/goal/test-chain.sh    # 처음부터 끝까지 (재시도, 멈춤, 동시 실행, status.md, 줄 오류)
bash scripts/goal/test-scripts.sh  # 셸 함정: 변수 바로 뒤 한글 (맥북 bash 3.2에서 죽음), 줄 끝 CR
bash scripts/goal/test-windows.sh  # Windows: /goal 인자, GNU date 시작 시각 (Git Bash에서는 cmd.exe로도 확인)
```

출처: Remote Control https://code.claude.com/docs/en/remote-control , 모바일 https://code.claude.com/docs/en/mobile , `/goal` https://code.claude.com/docs/en/goal , 비대화 실행 https://code.claude.com/docs/en/headless

## PR 무게 판정 (사람이 꼼꼼히 볼 PR 고르기)

goal 연속 실행과 별개입니다. 기준은 `CLAUDE.md` "PR 무게"에 있고, 판정 스크립트는 감시 검사가 지키는 `.github/scripts/pr_weight.py`에 둡니다(PR이 자기 무게를 고쳐 쓰지 못하게, 검증 Action은 `main` 것을 씁니다).

```bash
cd agent
uv run python tests/cases/rule_coverage.py                    # 규칙 ID마다 지나간 바깥 정답 사례 수(표)
uv run python tests/cases/rule_coverage.py --json > /tmp/cov.json
uv run python ../.github/scripts/pr_weight.py --pr <PR 번호> --coverage /tmp/cov.json   # 무게 판정(JSON)
```

PR 설명만 고치면(새 커밋 없이 ✅·➡️ 달기 등) 검증 Action의 `reweigh` job이 Claude 없이 무게만 다시 재서 `[검증]` 첫 줄 무게·"PR 무게" 칸·`human-review` 라벨을 맞춥니다(`.github/scripts/reweigh.py`). 나머지 `[검증]` 글은 다음 커밋의 전체 검증이 다시 씁니다.

`tomllib`이 필요해서 파이썬 3.11 이상으로 돌립니다(맥 기본 `python3`가 아니라 `uv run python`).
