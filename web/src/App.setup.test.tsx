// 첫 화면 설정(UI-00)과 PDF 올리기·추출 확인 표(UI-03): 고른 값과 고친 값이 대화 만들기로 간다.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { sse, streamOf } from "./test/fixtures";

// 가상 인물 추출 결과(금액은 아무 값, 세법과 무관)
const DOC = {
  tax_year: 2025,
  worker_name: "가상아내",
  items: [
    { group: "medical", kind: "일반", person_name: "가상어머니", amount: 1_200_000, source_text: "", mark: "none" },
    { group: "card", kind: "신용카드", person_name: "가상아내", amount: 9_000_000, source_text: "", mark: "none" },
  ],
  totals: [{ group: "card", amount: 9_000_000 }],
  prior_year: false,
  notes: [],
};

function mockApi(extraction: unknown = { ok: true, doc: DOC, errors: [], fallback: null, filename: "a.pdf" }) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
    if (url === "/api/conversations") return new Response(JSON.stringify({ id: 7 }), { status: 201 });
    if (url === "/api/extractions") return new Response(JSON.stringify(extraction), { status: 200 });
    return new Response(streamOf([sse("delta", { text: "네" }) + sse("done", { ended: "answered", turn: 1, message_id: 1 })]));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const bodyOf = (fetchMock: ReturnType<typeof mockApi>, url: string) =>
  JSON.parse(fetchMock.mock.calls.find(([u]) => u === url)![1]!.body as string);

async function say(text: string) {
  await userEvent.type(screen.getByLabelText("메시지"), text);
  await userEvent.click(screen.getByRole("button", { name: "보내기" }));
  await screen.findByText("네");
}

afterEach(() => vi.unstubAllGlobals());

describe("첫 화면 설정", () => {
  it("남편·아내와 자녀 수를 고르면 대화 만들기에 두 값이 가고, 시작 뒤에는 바꿀 수 없다", async () => {
    const fetchMock = mockApi();
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "저는 아내" }));
    expect(screen.getByRole("button", { name: "저는 아내" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.selectOptions(screen.getByLabelText("공제 대상 자녀 수"), "2");
    await say("시작할게요");
    const sent = bodyOf(fetchMock, "/api/conversations");
    expect(sent.self_role).toBe("wife");
    expect(sent.child_count).toBe(2);
    expect(screen.getByRole("button", { name: "저는 남편" })).toBeDisabled();
    expect(screen.getByLabelText("공제 대상 자녀 수")).toBeDisabled();
  });

  it("고르지 않고 시작해도 된다(두 칸을 보내지 않음). 0명은 고른 값으로 보낸다", async () => {
    let fetchMock = mockApi();
    const { unmount } = render(<App />);
    await say("그냥 시작");
    let sent = bodyOf(fetchMock, "/api/conversations");
    expect("self_role" in sent || "child_count" in sent).toBe(false);
    unmount();

    fetchMock = mockApi();
    render(<App />);
    await userEvent.selectOptions(screen.getByLabelText("공제 대상 자녀 수"), "0");
    await say("자녀 없어요");
    sent = bodyOf(fetchMock, "/api/conversations");
    expect(sent.child_count).toBe(0);
  });
});

describe("PDF 올리기와 추출 확인 표", () => {
  it("PDF를 올리면 읽은 값을 표로 보여 주고, 고친 금액·가족이 documents로 간다", async () => {
    const fetchMock = mockApi();
    render(<App />);
    const pdf = new File(["%PDF-1.4 가상"], "아내.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("간소화 PDF 올리기"), pdf);
    await screen.findByTestId("extract-table");
    // 서버에 base64로 보낸다
    const req = bodyOf(fetchMock, "/api/extractions");
    expect(req.filename).toBe("아내.pdf");
    expect(atob(req.pdf_base64).startsWith("%PDF-")).toBe(true);

    const amount = screen.getByLabelText("1번째 줄 금액");
    expect(amount).toHaveValue("1200000");
    await userEvent.clear(amount);
    await userEvent.type(amount, "1500000");
    const person = screen.getByLabelText("1번째 줄 가족");
    await userEvent.clear(person);
    await userEvent.type(person, "가상시어머니");
    // 올린 자료가 있으면 견본은 고를 수 없다
    expect(screen.getByLabelText("개발용 간소화 자료")).toBeDisabled();

    await say("자료 올렸어요");
    const docs = bodyOf(fetchMock, "/api/conversations").documents;
    expect(docs).toHaveLength(1);
    expect(docs[0].items[0]).toMatchObject({ amount: 1_500_000, person_name: "가상시어머니" });
    expect(docs[0].items[1].amount).toBe(9_000_000);
    // 고친 뒤에는 PDF 합계 대조를 빼고 사용자가 고친 값을 믿는다
    expect(docs[0].totals).toBeUndefined();
  });

  it("JSON 파일은 json 칸으로 보낸다", async () => {
    const fetchMock = mockApi();
    render(<App />);
    const file = new File([JSON.stringify(DOC)], "아내.json", { type: "application/json" });
    await userEvent.upload(screen.getByLabelText("간소화 PDF 올리기"), file);
    await screen.findByTestId("extract-table");
    expect(bodyOf(fetchMock, "/api/extractions").json.worker_name).toBe("가상아내");
  });

  it("읽지 못하면 이유와 JSON으로 올리는 길을 알려 주고 표를 만들지 않는다", async () => {
    mockApi({ ok: false, doc: null, errors: ["PDF에서 글자를 찾지 못했습니다"], fallback: "json_upload", filename: "x.pdf" });
    render(<App />);
    const pdf = new File(["%PDF-1.4"], "x.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("간소화 PDF 올리기"), pdf);
    expect(await screen.findByRole("alert")).toHaveTextContent("JSON 파일로 올려 주세요");
    expect(screen.queryByTestId("extract-table")).not.toBeInTheDocument();
  });
});
