// 빈 곳 알림 카드(FR-11): 질문 카드 선택지 → answer로 보냄, 동의 안내 카드 "문구 복사".
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { readGapCards } from "../chat/events";
import { sse, streamOf } from "../test/fixtures";

// 가상 카드(글·금액은 아무 값)
const QUESTION_CARD = {
  id: "gap.test_question",
  kind: "나",
  person: "가상어머니",
  title: "가상 질문 카드",
  why: "가상 이유",
  todo: "가상 할 일",
  source_pages: ["10", "11"],
  question: { text: "얼마쯤 썼어요?", options: [{ label: "100만 원쯤", amount: 1_000_000 }, { label: "모르겠어요" }] },
  estimate: null,
  consent_message: null,
  future_field: "PR 11c가 더할 수 있는 칸",
};
const CONSENT_CARD = {
  ...QUESTION_CARD,
  id: "gap.test_consent",
  title: "가상 동의 카드",
  question: null,
  consent_message: "가상 동의 부탁 글",
};

function mockApi(turns: string[][]) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
    if (url === "/api/conversations") return new Response(JSON.stringify({ id: 3 }), { status: 201 });
    return new Response(streamOf(turns.shift() ?? []), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const done = (turn: number) => sse("done", { ended: "answered", turn, message_id: turn });

async function start() {
  render(<App />);
  await userEvent.type(screen.getByLabelText("메시지"), "가족 알려 드릴게요");
  await userEvent.click(screen.getByRole("button", { name: "보내기" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("빈 곳 알림 카드", () => {
  it("질문 카드 선택지를 누르면 글과 answer를 함께 보낸다", async () => {
    const fetchMock = mockApi([
      [sse("delta", { text: "확인할 게 있어요" }) + sse("gaps", { cards: [QUESTION_CARD] }) + done(1)],
      [sse("delta", { text: "반영했어요" }) + done(2)],
    ]);
    await start();
    expect(await screen.findByText("가상 질문 카드")).toBeInTheDocument();
    expect(screen.getByTestId("gap-card")).toHaveTextContent("인쇄 10·11쪽");
    // 모르는 칸은 보이지 않는다
    expect(document.body.textContent).not.toMatch(/PR 11c/);
    await userEvent.click(screen.getByRole("button", { name: "100만 원쯤" }));
    await screen.findByText("반영했어요");
    const bodies = fetchMock.mock.calls.filter(([u]) => u !== "/api/conversations").map(([, i]) => JSON.parse(i!.body as string));
    expect(bodies[1]).toEqual({
      content: "100만 원쯤",
      answer: { gap_id: "gap.test_question", person: "가상어머니", choice: "100만 원쯤", amount: 1_000_000 },
    });
  });

  it("금액 없는 선택지는 amount를 보내지 않는다", async () => {
    const fetchMock = mockApi([[sse("gaps", { cards: [QUESTION_CARD] }) + done(1)], [done(2)]]);
    await start();
    await userEvent.click(await screen.findByRole("button", { name: "모르겠어요" }));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    const last = JSON.parse(fetchMock.mock.calls[2][1]!.body as string);
    expect(last.answer).toEqual({ gap_id: "gap.test_question", person: "가상어머니", choice: "모르겠어요" });
  });

  it("동의 안내 카드는 안내 문구와 '문구 복사' 버튼을 둔다", async () => {
    const writeText = vi.fn(async () => {});
    mockApi([[sse("gaps", { cards: [CONSENT_CARD] }) + done(1)]]);
    await start();
    expect(await screen.findByTestId("consent-message")).toHaveTextContent("가상 동의 부탁 글");
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await userEvent.click(screen.getByRole("button", { name: "문구 복사" }));
    expect(writeText).toHaveBeenCalledWith("가상 동의 부탁 글");
    expect(await screen.findByRole("button", { name: "복사했어요" })).toBeInTheDocument();
  });

  it("모양이 다른 카드는 버린다", () => {
    expect(readGapCards({ cards: [{ id: 1 }, QUESTION_CARD] })).toHaveLength(1);
    expect(readGapCards({ cards: "x" })).toEqual([]);
  });
});
