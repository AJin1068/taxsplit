"""동의 안내 문구: 메뉴 이름·순서가 국세청 원문 발췌(Issue #126 "정해진 결정")와 같은가."""

from taxsplit.gaps import consent_message
from taxsplit.gaps.consent import CLOSING

# Issue #126 원문 발췌를 그대로 옮긴 것(인쇄 379·380쪽). 코드 상수를 복사하지 않고 따로 적는다
WEB = (
    "홈택스 접속 → [장려금･연말정산･기부금]에서 ｢연말정산간소화｣ 클릭 → [부양가족 자료제공 동의 "
    "신청/조회/취소]에서 ｢본인인증 신청｣ 클릭 → 신청에 필요한 사항 입력 후 [신청하기] 클릭 → "
    "본인인증 수단(간편인증, 인증서, 휴대전화, 신용카드, 아이핀 등) 선택 → 본인 인증하여 신청"
)
FAX = (
    "홈택스 접속하여 로그인 → [장려금･연말정산･기부금]에서 "
    "｢부양가족 자료제공 동의 신청/조회/취소｣ 클릭 → ｢팩스 신청｣ 클릭 → "
    "[제공동의 신청정보 입력]에서 필요사항 입력 후 [신청하기 및 출력하기] 클릭 → "
    "출력된 신청서에 신분증 사본을 부착하여 팩스로 전송(☏1544-7020)"
)
MOBILE = (
    "손택스앱 실행하여 로그인 → 전체메뉴 → [장려금･연말정산･기부금] 선택 → [연말정산간소화] → "
    "[제공동의 신청/취소] 선택 → [제공동의 신청] 선택 → 자료제공자 정보 입력 → "
    "본인인증 방법(휴대전화 인증, 인증서 인증) 선택 → 본인 인증 → "
    "자료조회자 정보 입력 → [다음] 선택"
)


def _steps(text: str) -> list[str]:
    return text.split(" → ")


def test_steps_match_source_in_order():
    msg = consent_message("어머니")
    pos = -1
    # 방법 순서: ① 손택스 앱 → ② 홈택스 웹 본인인증 → ③ 팩스
    for excerpt in (MOBILE, WEB, FAX):
        for step in _steps(excerpt):
            found = msg.find(step, pos + 1)
            assert found > pos, f"단계가 없거나 순서가 다름: {step}"
            pos = found


def test_method_headers_in_order_and_closing_last():
    msg = consent_message("어머니")
    heads = [msg.index(h) for h in ("① 휴대폰 손택스 앱", "② 홈택스 웹에서 본인인증", "③ 팩스")]
    assert heads == sorted(heads)
    assert msg.rstrip().endswith(CLOSING)
    assert CLOSING == "동의하면 1월 15일 간소화가 열릴 때 자료가 함께 보여요."


def test_menu_names_kept_verbatim():
    msg = consent_message("어머니")
    for name in (
        "[장려금･연말정산･기부금]",
        "｢연말정산간소화｣",
        "[부양가족 자료제공 동의 신청/조회/취소]",
        "｢본인인증 신청｣",
        "｢팩스 신청｣",
        "[제공동의 신청/취소]",
        "☏1544-7020",
    ):
        assert name in msg


def test_adult_child_note_only_for_adult_child():
    assert "19세가 넘으면 본인이 직접" in consent_message("큰애", adult_child=True)
    assert "19세" not in consent_message("어머니")
    assert consent_message("어머니").startswith("어머니, ")
