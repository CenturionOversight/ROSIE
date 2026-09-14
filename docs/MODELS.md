# Models and Provider Boundaries

ROSIE's durable responsibility is local-machine execution and authority. It does not require one fixed reasoning provider.

Two model paths currently exist in the repository.

## Agents for Humans submission path

The hackathon path uses:

```text
Strands Agents
→ Amazon Bedrock
→ Amazon Nova Micro
→ ROSIE capability adapters
→ ROSIE runtime dispatch
→ local machine
```

The verified live model is:

```text
us.amazon.nova-micro-v1:0
```

Strands owns the agent turn. ROSIE owns the local capability boundary.

The model can select exposed ROSIE tools, but execution still routes through ROSIE's runtime/session ownership, approval policy, and executor.

## Standalone ROSIE path

ROSIE can also operate independently through the local CLI using LiteLLM as a provider abstraction.

```text
local operator
→ LiteLLM/model
→ ROSIE local tools
→ local machine
```

Select a standalone model with:

```bash
python -m wrapper.cli . --model <litellm-model-string>
```

Example:

```bash
python -m wrapper.cli . --model ollama/qwen2.5-coder:7b
```

Disable standalone fallback models with:

```bash
python -m wrapper.cli . --no-fallback
```

## Provider independence

Provider-specific logic is kept outside the core local-action contracts.

ROSIE's core semantics are:

- bind the correct workspace;
- expose bounded local capabilities;
- enforce approval policy;
- execute through the owned runtime/executor; and
- return truthful evidence.

The reasoning provider can change without redefining those responsibilities.

## Credentials

The Strands submission path requires AWS credentials/configuration that can access the selected Bedrock model.

Standalone providers use the credentials required by their configured LiteLLM provider.

Credentials are runtime configuration, not model-visible data and not part of ROSIE's architectural identity.

## Legacy provider assets

The repository also contains older Google ADK / Gemini hackathon assets from prior development. They are not the model/framework path submitted for the AWS Agents for Humans Hackathon.
