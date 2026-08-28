# Models and Fallback

ROSIE uses LiteLLM as its model-provider abstraction.

## Default model

```text
ollama/qwen2.5-coder:7b
```

This supports a local default path without requiring an API key.

## Fallback chain

Unless `--no-fallback` is supplied, ROSIE builds a model chain from the selected primary model followed by the configured fallback models that are not duplicates of the primary.

Current configured fallbacks:

```text
openrouter/deepseek/deepseek-chat
ollama/qwen2.5-coder:7b
```

## Selecting a model

```bash
python -m wrapper.cli . --model <litellm-model-string>
```

Example:

```bash
python -m wrapper.cli . --model gemini/gemini-2.5-pro
```

The Gemini example above represents ROSIE's existing generic LiteLLM path. It is not, by itself, a Google Agent Framework integration.

## Disabling fallback

```bash
python -m wrapper.cli . --no-fallback
```

With this flag, only the selected primary model is attempted.

## Failures that trigger fallback

The current `_completion()` implementation falls through to another configured model for several provider/runtime failures, including:

- authentication failure;
- rate limit;
- service unavailable;
- API connection failure;
- model not found;
- bad gateway;
- internal server error;
- generic LiteLLM `APIError` responses with status 401, 402, 429, or 503.

Other API errors are re-raised rather than silently redirected to another model.

## Environment variables

ROSIE checks for these provider-key environment variables before starting a chain that contains no Ollama model:

```text
GEMINI_API_KEY
ANTHROPIC_API_KEY
OPENAI_API_KEY
DEEPSEEK_API_KEY
GROK_API_KEY
XAI_API_KEY
OPENROUTER_API_KEY
```

LiteLLM performs the provider-specific authentication.

## Tool calling

Every model request receives `TOOL_SCHEMAS`. Models used with ROSIE therefore need a LiteLLM-compatible tool/function-calling path for full agentic execution.

## Provider independence

The core execution loop does not contain separate Gemini, Claude, OpenAI, DeepSeek, or Ollama agent implementations. Provider selection is concentrated at the LiteLLM model-call boundary.
