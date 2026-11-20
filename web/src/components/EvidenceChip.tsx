// UI-02 근거 조문 칩. 마우스를 올리거나(컴퓨터) 누르면(휴대폰) 원문 조각과 쪽을 보여 준다.
import { useState } from "react";
import type { EvidenceItem } from "../api/types";
import { chipLabel } from "../chat/events";

/** 쪽 한 줄: "인쇄 97쪽 (PDF 115쪽)". 쪽 번호가 없으면 서버가 준 page 글자를 쓴다. */
export function pageLine(item: EvidenceItem): string {
  if (item.print_page === null) return item.page;
  const pdf = item.pdf_page === null ? "" : ` (PDF ${item.pdf_page}쪽)`;
  return `인쇄 ${item.print_page}쪽${pdf}`;
}

export function EvidenceChip({ item }: { item: EvidenceItem }) {
  const [open, setOpen] = useState(false);
  const page = item.print_page === null ? "" : ` ${item.print_page}쪽`;
  return (
    <span className="relative inline-block" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="rounded-full border border-brand-line bg-brand-card px-2 py-0.5 text-[11px] font-semibold text-brand-navy hover:border-brand-navy"
      >
        근거 · {chipLabel(item.rule_id)}
        {page}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 top-full z-10 mt-1 block w-64 rounded-2xl bg-brand-navy p-3 text-left text-xs leading-relaxed text-white shadow-lg"
        >
          <span className="block">“{item.snippet}”</span>
          <span className="mt-2 block text-brand-navyBg">
            {item.source} · {pageLine(item)}
          </span>
        </span>
      )}
    </span>
  );
}
