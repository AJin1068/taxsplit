// 금액 표시 형식. 화면은 금액을 계산하지 않고, API 금액을 읽기 좋게 바꾸기만 한다.
// 만 원 단위 버림은 표시 형식일 뿐 새 금액이 아니다(Issue #23 "금액 표시").

const MAN = 10_000;

/** 원 단위 그대로: 472150 → "472,150원" */
export function formatWon(amount: number): string {
  return `${amount.toLocaleString("ko-KR")}원`;
}

export interface BigMoney {
  // 큰 글씨: "47만 원" (만 원 미만이면 원 단위)
  big: string;
  // 작은 글씨: 원 단위 그대로. 큰 글씨가 이미 원 단위면 null
  exact: string | null;
}

/** 큰 숫자 표시: 472150 → { big: "47만 원", exact: "472,150원" }, 9000 → { big: "9,000원", exact: null } */
export function formatBigMoney(amount: number): BigMoney {
  if (Math.abs(amount) < MAN) return { big: formatWon(amount), exact: null };
  // 0 쪽으로 버림(음수가 와도 크기를 부풀리지 않음)
  const man = Math.trunc(amount / MAN);
  return { big: `${man.toLocaleString("ko-KR")}만 원`, exact: formatWon(amount) };
}
