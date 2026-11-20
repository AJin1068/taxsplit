package taxsplit.gateway

/** 가짜 Anthropic 답. 모양은 Messages API 문서와 에이전트 테스트(test_anthropic_client.py)를 따른다. */
object Fixtures {
    val MESSAGE_JSON = """
        {"id":"msg_1","type":"message","role":"assistant","model":"claude-sonnet-5-5",
         "content":[{"type":"text","text":"안녕하세요"}],"stop_reason":"end_turn","stop_sequence":null,
         "usage":{"input_tokens":12,"output_tokens":4,"cache_creation_input_tokens":3,"cache_read_input_tokens":5}}
    """.trimIndent().replace("\n", "")

    val ERROR_JSON = """{"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}"""

    private val EVENTS = listOf(
        "message_start" to """{"type":"message_start","message":{"id":"msg_2","type":"message","role":"assistant","model":"claude-haiku-5-5","content":[],"stop_reason":null,"usage":{"input_tokens":12,"output_tokens":1,"cache_creation_input_tokens":0,"cache_read_input_tokens":2}}}""",
        "content_block_start" to """{"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}""",
        "content_block_delta" to """{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"안녕"}}""",
        "content_block_delta" to """{"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"하세요"}}""",
        "content_block_stop" to """{"type":"content_block_stop","index":0}""",
        "message_delta" to """{"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":4}}""",
        "message_stop" to """{"type":"message_stop"}""",
    )

    val SSE_EVENTS: List<String> = EVENTS.map { (name, data) -> "event: $name\ndata: $data\n\n" }
    val SSE: String = SSE_EVENTS.joinToString("")
}
