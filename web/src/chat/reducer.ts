// 채팅 화면 상태(useReducer 하나). 메시지 목록, 진행 한 줄, 마지막 배분 결과·근거·빈 곳 카드.
import type { AllocationEvent, ChatEvent, EvidenceMap, GapCardData } from "../api/types";
import { ERROR_TEXT, statusLabel } from "../labels";
import { readEvidence, readGapCards } from "./events";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  // 정상 답이 아니면(멈춤·오류) 다시 보내기 버튼을 단다
  retry?: boolean;
}

export interface ChatState {
  messages: ChatMessage[];
  busy: boolean;
  // 진행 한 줄(쉬운 말). 답이 나오기 시작하면 지운다
  progress: string | null;
  allocation: AllocationEvent | null;
  // 배분 결과에 쓴 규칙의 근거(규칙 ID → 원문 조각). 배분 결과가 새로 오면 비운다
  evidence: EvidenceMap;
  // 마지막으로 받은 빈 곳 알림 카드
  gaps: GapCardData[];
}

export type ChatAction =
  | { type: "send"; text: string }
  | { type: "event"; event: ChatEvent }
  | { type: "failed" };

export const initialState: ChatState = {
  messages: [],
  busy: false,
  progress: null,
  allocation: null,
  evidence: {},
  gaps: [],
};

/** 마지막 메시지가 AI 답이면 고치고, 아니면 새 AI 답을 붙인다. */
function updateAssistant(state: ChatState, edit: (m: ChatMessage) => ChatMessage): ChatMessage[] {
  const last = state.messages.at(-1);
  if (last?.role === "assistant") return [...state.messages.slice(0, -1), edit(last)];
  return [...state.messages, edit({ role: "assistant", text: "" })];
}

function onEvent(state: ChatState, event: ChatEvent): ChatState {
  switch (event.name) {
    case "status":
      return { ...state, progress: statusLabel(event.data) };
    case "delta":
      // 받는 대로 말풍선에 이어 붙인다
      return {
        ...state,
        progress: null,
        messages: updateAssistant(state, (m) => ({ ...m, text: m.text + event.data.text })),
      };
    case "allocation":
      return { ...state, allocation: event.data, evidence: {} };
    case "evidence":
      return { ...state, evidence: readEvidence(event.data) };
    case "gaps":
      return { ...state, gaps: readGapCards(event.data) };
    case "error":
      // 서버 오류 글은 개발자 말이라 보여 주지 않는다
      return { ...state, messages: updateAssistant(state, (m) => ({ ...m, text: ERROR_TEXT, retry: true })) };
    case "done": {
      const answered = event.data.ended === "answered";
      return {
        ...state,
        busy: false,
        progress: null,
        messages: answered ? state.messages : updateAssistant(state, (m) => ({ ...m, retry: true })),
      };
    }
    default:
      return state;
  }
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "send":
      return { ...state, busy: true, progress: null, messages: [...state.messages, { role: "user", text: action.text }] };
    case "event":
      return onEvent(state, action.event);
    case "failed":
      return {
        ...state,
        busy: false,
        progress: null,
        messages: updateAssistant(state, (m) => ({ ...m, text: ERROR_TEXT, retry: true })),
      };
  }
}
