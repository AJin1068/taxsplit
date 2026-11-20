from taxsplit.core.config import Settings
from taxsplit.llm.anthropic_client import AnthropicLLMClient
from taxsplit.llm.call_log import LlmCallRepository
from taxsplit.llm.fake import FakeLLMClient
from taxsplit.llm.openai_client import OpenAILLMClient
from taxsplit.llm.recording import ProviderClient, RecordingLLMClient


def build_provider_client(settings: Settings) -> ProviderClient:
    match settings.llm_provider:
        case "fake":
            return FakeLLMClient()
        case "anthropic":
            if settings.anthropic_api_key is None:
                raise ValueError("LLM_PROVIDER=anthropic이면 ANTHROPIC_API_KEY가 필요하다")
            return AnthropicLLMClient(
                api_key=settings.anthropic_api_key.get_secret_value(),
                base_url=settings.llm_base_url,
                connect_timeout=settings.llm_connect_timeout,
                read_timeout=settings.llm_read_timeout,
                total_timeout=settings.llm_total_timeout,
            )


def build_llm_client(settings: Settings, repo: LlmCallRepository) -> RecordingLLMClient:
    """서비스가 쓰는 LLM 클라이언트. 항상 기록 래퍼로 감싸서 돌려준다."""
    return RecordingLLMClient(build_provider_client(settings), repo, settings)


# GPT 채점 기본 모델(설정값 LLM_MODEL_JUDGE가 비었을 때).
# 2026-11-19 OpenAI 가격 페이지(https://developers.openai.com/api/docs/pricing)에서 확인한 모델
JUDGE_DEFAULT_MODEL = "gpt-6.2-sol"


def judge_model(settings: Settings) -> str:
    # model_for(JUDGE)는 Claude 기본 모델로 떨어지므로 쓰지 않는다(채점은 다른 회사 모델, ADR-0006)
    return settings.llm_model_judge.strip() or JUDGE_DEFAULT_MODEL


def build_judge_client(settings: Settings) -> OpenAILLMClient:
    """평가 하네스 GPT 채점 클라이언트. 키가 없으면 ValueError(부르기 전에 멈춤)."""
    if settings.openai_api_key is None:
        raise ValueError("--judge에는 OPENAI_API_KEY가 필요하다")
    model = judge_model(settings)
    if not model.startswith("gpt"):
        raise ValueError(f"--judge에는 GPT 모델 이름 필요 (LLM_MODEL_JUDGE={model!r})")
    return OpenAILLMClient(
        api_key=settings.openai_api_key.get_secret_value(),
        model=model,
        timeout=settings.llm_total_timeout,
    )
