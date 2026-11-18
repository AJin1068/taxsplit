---
description: 지휘 세션에서 goal 연속 실행을 띄우고 지켜보다가 휴대폰으로 알린다 (코드는 고치지 않음)
argument-hint: "<PR 번호들> [--minutes 90] [--max-lanes 3] (예: 4 5 6 7)"
---

이 세션은 **지휘 세션**이다. 사람이 맥북에서 `claude --remote-control "taxsplit goal 실행" --permission-mode auto`로 띄우고, 휴대폰 Claude 앱(Code 탭)에서 본다. 세팅은 `scripts/README.md`, 규칙은 CLAUDE.md "goal 연속 실행"과 ADR-0009.

대상: $ARGUMENTS

## 하지 않는 것

- 코드·문서·브랜치를 고치지 않는다. 할 수 있는 일은 읽기와 `scripts/goal-run.sh` 실행, 상태 보고, 푸시 알림뿐이다.
- merge, 승인, 라벨(`ready`·`plan-ok`·`infra-ok`) 붙이기, force push, rebase를 하지 않는다.
- 줄 작업 폴더(`../taxsplit-lanes/…`) 안의 Claude에게 끼어들지 않는다. 그쪽은 스크립트가 맡는다.

## 할 일

1. 시작 전 확인: 레포 루트에서 `git status --porcelain`이 비어 있는지 본다. 비어 있지 않으면 시작하지 않고 알린다.
2. `scripts/goal-run.sh $ARGUMENTS`를 **백그라운드로** 실행한다. 첫 줄에 나오는 결과 폴더(`.goal-runs/<날짜_시각>/`)를 기억한다. 이 폴더가 아래의 `<실행 폴더>`다.
3. 지켜보기: 짧은 간격으로 계속 확인하지 않는다. 백그라운드 감시(Monitor)로 아래가 생기거나 바뀔 때만 깨어난다.
   - `<실행 폴더>/pr*.result.json`이 새로 생김 → 그 Issue가 끝남
   - `<실행 폴더>/summary.md`가 생김 → 전체가 끝남
4. 깨어날 때마다 `<실행 폴더>/status.md`와 새 `result.json`을 읽고, 아래 경우에는 **푸시 알림**을 보낸다. 한 문장, PR 번호와 상태를 앞에 쓴다.
   - 줄 하나가 끝남: "lane-4 끝: PR 4 passed, PR 5 passed"
   - `blocked`: "PR 5 blocked: 결정이 필요함. 질문은 pr5.blocked.md"
   - `failed`: "PR 5 failed: 검문 4(PR) 실패. 이 줄의 뒤 Issue는 시작 안 함"
   - 전체 끝: "goal 연속 실행 끝: passed 3, failed 1. summary.md 확인"
5. 휴대폰에서 물으면 `status.md`, `result.json`, `<실행 폴더>/lane-*.log`, `pr<N>.jsonl`(실행 기록)로 답한다. 실행 기록은 길기 때문에 subagent에게 요약을 맡긴다. 모르는 것은 지어내지 않고 "기록에 없음"이라고 한다.
6. 다 끝나면 `summary.md`를 그대로 보여 주고, "사람이 답할 질문"과 "merge 순서"를 다시 짚는다.
