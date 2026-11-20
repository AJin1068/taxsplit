package taxsplit.gateway

import taxsplit.gateway.usage.ModelPrice
import taxsplit.gateway.usage.Pricing
import taxsplit.gateway.usage.Rates
import taxsplit.gateway.usage.TokenUsage
import java.io.File
import java.math.BigDecimal
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class PricingTest {
    private val pricing = Pricing.bundled()

    @Test
    fun `토큰 종류별 단가를 곱해 더한다`() {
        // sonnet: 입력 2, 캐시 쓰기 2.5, 캐시 읽기 0.1, 출력 10 (USD/MTok)
        val usage = TokenUsage(inputTokens = 1000, outputTokens = 200, cacheCreationInputTokens = 400, cacheReadInputTokens = 5000)
        // (2*1000 + 2.5*400 + 0.1*5000 + 10*200) / 1e6 = 5500 / 1e6
        assertEquals(BigDecimal("0.0055"), pricing.costUsd("claude-sonnet-5-5", usage))
    }

    @Test
    fun `입력 합이 문턱을 넘으면 긴 프롬프트 단가`() {
        val atThreshold = TokenUsage(inputTokens = 100_000)
        val over = TokenUsage(inputTokens = 99_000, cacheReadInputTokens = 1_001)
        assertEquals(BigDecimal("0.01"), pricing.costUsd("claude-haiku-5-5", atThreshold))
        // 0.5*99000 + 0.05*1001 = 49550.05 → / 1e6
        assertEquals(BigDecimal("0.04955005"), pricing.costUsd("claude-haiku-5-5", over))
    }

    @Test
    fun `단가표에 없는 모델은 0이 아니라 null`() {
        assertNull(pricing.costUsd("claude-unknown-9", TokenUsage(inputTokens = 10)))
    }

    /** 에이전트 단가표(agent/src/taxsplit/llm/pricing.toml)의 anthropic 칸과 값이 같아야 한다. */
    @Test
    fun `에이전트 단가표와 어긋나지 않는다`() {
        val toml = File("../agent/src/taxsplit/llm/pricing.toml")
        assertTrue(toml.isFile, "에이전트 단가표를 못 찾음: ${toml.absolutePath} (레포 루트 전체를 두고 돌린다)")
        assertEquals(anthropicPrices(toml.readLines()), pricing.prices)
    }

    // pricing.toml은 [anthropic."모델"] / [anthropic."모델".long_prompt] 칸과 key = 값 줄뿐이라 직접 읽는다
    private fun anthropicPrices(lines: List<String>): Map<String, ModelPrice> {
        val tables = linkedMapOf<String, MutableMap<String, String>>()
        var current: MutableMap<String, String>? = null
        for (raw in lines) {
            val line = raw.substringBefore('#').trim()
            if (line.isEmpty()) continue
            val header = Regex("""^\[anthropic\."([^"]+)"(\.long_prompt)?]$""").find(line)
            when {
                header != null -> {
                    val key = header.groupValues[1] + header.groupValues[2]
                    current = tables.getOrPut(key) { mutableMapOf() }
                }
                line.startsWith("[") -> current = null
                current != null -> current[line.substringBefore('=').trim()] = line.substringAfter('=').trim().trim('"')
            }
        }
        fun rates(t: Map<String, String>) =
            Rates(BigDecimal(t["input"]), BigDecimal(t["cache_write"]), BigDecimal(t["cache_read"]), BigDecimal(t["output"]))
        return tables.filterKeys { !it.endsWith(".long_prompt") }.mapValues { (model, t) ->
            ModelPrice(
                base = rates(t),
                longPromptThreshold = t["long_prompt_threshold"]?.toLong(),
                longPrompt = tables["$model.long_prompt"]?.let(::rates),
            )
        }
    }
}
