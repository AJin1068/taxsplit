// 채팅 화면 상태(useReducer 하나). 메시지 목록, 진행 한 줄, 마지막 배분 결과.
import type { AllocationEvent, ChatEvent } from "../api/types";
import { ERROR_TEXT, statusLabel } from "../labels";

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
}

export type ChatAction =
  | { type: "send"; text: string }
  | { type: "event"; event: ChatEvent }
  | { type: "failed" };

export const initialState: ChatState = { messages: [], busy: false, progress: null, allocation: null };

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
      return { ...state, allocation: event.data };
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
      // evidence는 이 PR에서 받기만 한다(근거 칩은 PR 14b)
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
