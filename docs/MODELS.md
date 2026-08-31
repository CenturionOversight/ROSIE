# Models and Fallback

ROSIE's product responsibility is the local-machine bridge/runtime. It does not require ROSIE to own the primary reasoning model in the complete HACKASS → ARCHESTRATOR → ROSIE stack.

The **standalone ROSIE CLI** uses LiteLLM as its model-provider abstraction so the local runtime can also operate independently for development, testing, and direct local use.

## Architecture distinction

```text
Complete product path:
HACKASS → ARCHESTRATOR → ROSIE → local machine

Standalone ROSIE mode:
local operator → LiteLLM/model → ROSIE local tools → local machine
```

In the Google hackathon HACKASS path, Google ADK and Gemini provide the hackathon reasoning/framework path and delegate authorized actions into the incorporated local execution surface.

## Default standalone model

The configured standalone model depends on the current runtime configuration. See the root README and `wrapper/cli.py` for the current default used by the repository.

## Selecting a standalone model

```bash
python -m wrapper.cli . --model <litellm-model-string>
```

Example:

```bash
python -m wrapper.cli . --model ollama/qwen2.5-coder:7b
```

Generic Gemini access through LiteLLM is a standalone provider path. It is not, by itself, the Google Agent Framework integration used by HACKASS for the hackathon.

## Disabling fallback

```bash
python -m wrapper.cli . --no-fallback
```

With this flag, only the selected primary model is attempted.

## Fallback behavior

Unless `--no-fallback` is supplied, the standalone CLI can build a model chain from the selected primary model followed by configured fallback models that are not duplicates of the primary.

The exact configured list is implementation state and should be read from the current source rather than treated as part of ROSIE's architectural identity.

## Provider failures

The standalone `_completion()` path can fall through to another configured model for selected provider/runtime failures such as authentication, rate limits, service availability, connection failure, missing models, and supported upstream API errors.

Other API errors are surfaced rather than silently redirected.

## Environment variables

Standalone provider credentials may be supplied through provider-specific environment variables supported by the configured LiteLLM path.

Do not treat those credentials as part of the web-to-local transport architecture. A future attached ROSIE process should preserve an explicit boundary between local machine authority and whichever reasoning provider the higher-level system uses.

## Tool calling

Standalone model requests receive the local `TOOL_SCHEMAS` so the model can request ROSIE actions.

Models used in standalone ROSIE mode therefore need a compatible tool/function-calling path for full local agentic execution.

## Provider independence

The local action layer is intentionally separable from any single provider.

That is important to ROSIE's role: the bridge to the machine should remain usable even as the intelligence provider or higher-level agent framework changes.
