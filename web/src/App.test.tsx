// 화면 전체: 가짜 fetch로 SSE를 흘려 채팅·진행 한 줄·카드·다시 보내기를 본다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { allocationFixture, sse, streamOf } from "./test/fixtures";

// 화면에 보이면 안 되는 개발자 말: 도구 이름, 상태 코드, 규칙 ID 모양
const FORBIDDEN = [/check_eligibility/, /compare_allocations/, /\bok\b/, /guard_stop/, /sensor_stop/, /20\d\d\.[a-z_]+\./];

function mockApi(turns: string[][]) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
    if (url === "/api/conversations") return new Response(JSON.stringify({ id: 7 }), { status: 201 });
    return new Response(streamOf(turns.shift() ?? []), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function say(text: string) {
  await userEvent.type(screen.getByLabelText("메시지"), text);
  await userEvent.click(screen.getByRole("button", { name: "보내기" }));
}

afterEach(() => vi.unstubAllGlobals());

describe("채팅 화면", () => {
  it("답 조각을 이어 붙이고, 배분안 카드를 띄우고, 개발자 말은 보이지 않는다", async () => {
    const alloc = allocationFixture({ rule_ids: ["2025.basic.age"] } as never);
    mockApi([
      [
        sse("status", { stage: "thinking" }) +
          sse("status", { stage: "tool", tool: "check_eligibility", status: "ok" }),
        sse("status", { stage: "tool", tool: "compare_allocations", status: "ok" }) + sse("delta", { text: "어머니는 " }),
        sse("delta", { text: "아내 쪽이 좋아요." }) + sse("allocation", alloc),
        sse("evidence", { "2025.basic.age": { title: "x" } }) + sse("done", { ended: "answered", turn: 1, message_id: 3 }),
      ],
    ]);
    render(<App />);
    await say("연봉 알려 드릴게요");
    await screen.findByTestId("allocation-card");
    expect(screen.getByText("어머니는 아내 쪽이 좋아요.")).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    for (const pattern of FORBIDDEN) expect(text).not.toMatch(pattern);
    expect(screen.queryByRole("button", { name: "다시 보내기" })).not.toBeInTheDocument();
    expect(screen.getByText("참고용 계산 · 최종 판단은 본인 또는 세무사와")).toBeInTheDocument();
  });

  it("도구 진행은 쉬운 말 한 줄로 보인다", async () => {
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url === "/api/conversations") return new Response(JSON.stringify({ id: 1 }), { status: 201 });
        const enc = new TextEncoder();
        const body = new ReadableStream<Uint8Array>({
          async start(c) {
            c.enqueue(enc.encode(sse("status", { stage: "tool", tool: "compare_allocations", status: "ok" })));
            await gate;
            c.enqueue(enc.encode(sse("delta", { text: "끝" }) + sse("done", { ended: "answered", turn: 1, message_id: 1 })));
            c.close();
          },
        });
        return new Response(body, { status: 200 });
      }),
    );
    render(<App />);
    await say("계산해 주세요");
    expect(await screen.findByRole("status")).toHaveTextContent("나누는 방법을 모두 계산하고 있어요");
    expect(document.body.textContent).not.toMatch(/compare_allocations/);
    release();
    await screen.findByText("끝");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("정상 답이 아니면 받은 문구를 그대로 보여 주고 다시 보내기로 같은 글을 다시 보낸다", async () => {
    const fetchMock = mockApi([
      [sse("delta", { text: "입력 값을 확인하지 못해 계산을 멈췄어요." }) + sse("done", { ended: "guard_stop", turn: 1, message_id: 2 })],
      [sse("delta", { text: "다시 계산했어요." }) + sse("done", { ended: "answered", turn: 2, message_id: 4 })],
    ]);
    render(<App />);
    await say("엄마 소득 없어요");
    expect(await screen.findByText("입력 값을 확인하지 못해 계산을 멈췄어요.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "다시 보내기" }));
    await screen.findByText("다시 계산했어요.");
    const bodies = fetchMock.mock.calls.filter(([u]) => u !== "/api/conversations").map(([, init]) => init?.body);
    expect(bodies).toEqual([JSON.stringify({ content: "엄마 소득 없어요" }), JSON.stringify({ content: "엄마 소득 없어요" })]);
    // 대화는 처음 한 번만 만든다
    expect(fetchMock.mock.calls.filter(([u]) => u === "/api/conversations")).toHaveLength(1);
  });

  it("error 이벤트면 서버 글 대신 '잠시 뒤 다시 시도해 주세요'와 다시 보내기", async () => {
    mockApi([[sse("error", { message: "AI 호출 실패: timeout" }) + sse("done", { ended: "error", turn: 1, message_id: null })]]);
    render(<App />);
    await say("안녕하세요");
    expect(await screen.findByText(/잠시 뒤 다시 시도해 주세요/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/AI 호출 실패/);
    expect(screen.getByRole("button", { name: "다시 보내기" })).toBeInTheDocument();
  });

  it("고른 간소화 자료를 대화 만들 때 함께 보낸다", async () => {
    const fetchMock = mockApi([[sse("delta", { text: "자료 받았어요" }) + sse("done", { ended: "answered", turn: 1, message_id: 1 })]]);
    render(<App />);
    await userEvent.selectOptions(screen.getByLabelText("개발용 간소화 자료"), "couple-2024");
    await say("자료 보냈어요");
    await screen.findByText("자료 받았어요");
    const create = fetchMock.mock.calls.find(([u]) => u === "/api/conversations")!;
    const sent = JSON.parse(create[1]?.body as string);
    expect(sent.documents).toHaveLength(2);
    expect(screen.getByLabelText("개발용 간소화 자료")).toBeDisabled();
  });
});
