package taxsplit.gateway.usage

import org.yaml.snakeyaml.Yaml
import java.io.InputStream
import java.math.BigDecimal
import java.math.MathContext

/** 토큰 수 네 가지. 이름은 Anthropic usage 칸과 같다. */
data class TokenUsage(
    val inputTokens: Long = 0,
    val outputTokens: Long = 0,
    val cacheCreationInputTokens: Long = 0, // 캐시 쓰기 (5분 캐시)
    val cacheReadInputTokens: Long = 0, // 캐시 읽기
)

/** USD / 100만 토큰. */
data class Rates(
    val input: BigDecimal,
    val cacheWrite: BigDecimal,
    val cacheRead: BigDecimal,
    val output: BigDecimal,
)

data class ModelPrice(
    val base: Rates,
    val longPromptThreshold: Long? = null,
    val longPrompt: Rates? = null,
)

/**
 * 모델별 단가표(resources/pricing.yml)와 비용 계산.
 * 규칙은 에이전트 llm/pricing.py cost_usd와 같다:
 * 입력 합(입력+캐시 쓰기+캐시 읽기)이 문턱을 넘으면 긴 프롬프트 단가, 표에 없는 모델은 null.
 */
class Pricing(val prices: Map<String, ModelPrice>) {

    fun costUsd(model: String, usage: TokenUsage): BigDecimal? {
        val price = prices[model] ?: return null
        val promptTokens = usage.inputTokens + usage.cacheCreationInputTokens + usage.cacheReadInputTokens
        val threshold = price.longPromptThreshold
        val rates = if (price.longPrompt != null && threshold != null && promptTokens > threshold) {
            price.longPrompt
        } else {
            price.base
        }
        val total = rates.input * usage.inputTokens.toBigDecimal() +
            rates.cacheWrite * usage.cacheCreationInputTokens.toBigDecimal() +
            rates.cacheRead * usage.cacheReadInputTokens.toBigDecimal() +
            rates.output * usage.outputTokens.toBigDecimal()
        // 나눗셈 끝자리를 정확히 (단가 소수 자리 + 6자리라 끝나는 소수)
        return total.divide(PER_MILLION, MathContext.DECIMAL128).stripTrailingZeros()
    }

    companion object {
        private val PER_MILLION = BigDecimal(1_000_000)

        /** 게이트웨이에 들어 있는 단가표(resources/pricing.yml). */
        fun bundled(): Pricing = Pricing(load(Pricing::class.java.getResourceAsStream("/pricing.yml")!!))

        @Suppress("UNCHECKED_CAST")
        fun load(input: InputStream): Map<String, ModelPrice> {
            val data = input.use { Yaml().load<Map<String, Map<String, Any>>>(it) }
            return data.mapValues { (_, table) ->
                ModelPrice(
                    base = rates(table),
                    longPromptThreshold = (table["long_prompt_threshold"] as Number?)?.toLong(),
                    longPrompt = (table["long_prompt"] as Map<String, Any>?)?.let(::rates),
                )
            }
        }

        private fun rates(table: Map<String, Any>) = Rates(
            input = BigDecimal(table["input"].toString()),
            cacheWrite = BigDecimal(table["cache_write"].toString()),
            cacheRead = BigDecimal(table["cache_read"].toString()),
            output = BigDecimal(table["output"].toString()),
        )
    }
}
