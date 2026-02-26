from portal.routing.model_backends import OllamaBackend


def test_normalize_tool_calls_openai_function_shape():
    raw = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "weather.lookup",
                "arguments": {"city": "Seattle"},
            },
            "server": "weather",
        }
    ]

    normalized = OllamaBackend._normalize_tool_calls(raw)

    assert normalized == [
        {
            "tool": "weather.lookup",
            "name": "weather.lookup",
            "arguments": {"city": "Seattle"},
            "server": "weather",
        }
    ]


def test_normalize_tool_calls_passthrough_and_invalid_inputs():
    passthrough = [{"tool": "clock.now", "arguments": {}}]

    assert OllamaBackend._normalize_tool_calls(passthrough) == passthrough
    assert OllamaBackend._normalize_tool_calls("invalid") is None
    assert OllamaBackend._normalize_tool_calls([]) is None
