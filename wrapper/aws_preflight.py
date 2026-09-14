"""AWS/Bedrock readiness preflight for the real M1 run.

Checks, in dependency order, without ever printing credential material:

    AWS_CREDENTIALS  - botocore credential chain resolves
    AWS_REGION       - an effective region is configured
    BEDROCK_CLIENT   - a Bedrock-Runtime client constructs successfully
    MODEL_ACCESS     - the configured model can be addressed (minimal one-user-
                       message Converse probe; rejects-in-shape errors are
                       surfaced verbatim as the next blocker)

Dependent checks are skipped cleanly once an earlier one fails.  No success
is invented: a check that cannot be performed is reported as FAIL/SKIPPED
with the exact AWS error, which is precisely the "next blocker" evidence M1
needs.  This module contains no fallbacks and performs no generation.
"""
from __future__ import annotations

__all__ = ["MODEL_ID", "run_preflight"]

MODEL_ID = "us.amazon.nova-micro-v1:0"


def _short(exc: Exception) -> str:
    """Compact single-line AWS error string (no credential material)."""
    return str(exc).replace("\n", " ")[:300]


def run_preflight() -> bool:
    """Run all preflight checks.  Returns True only when fully ready."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    ready = True

    # --- credentials ---------------------------------------------------
    try:
        session = boto3.session.Session()
        creds = session.get_credentials()
        if creds is None:
            print("AWS_CREDENTIALS: FAIL - botocore credential chain resolved no credentials")
            ready = False
        else:
            print("AWS_CREDENTIALS: PASS (values not printed)")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"AWS_CREDENTIALS: FAIL - {type(exc).__name__}: {_short(exc)}")
        return False

    # --- region ----------------------------------------------------------
    region = session.region_name
    if region:
        print(f"AWS_REGION: PASS ({region})")
    else:
        print("AWS_REGION: FAIL - no region configured (set AWS_REGION or a profile)")
        ready = False

    # --- Bedrock client --------------------------------------------------
    try:
        client = session.client("bedrock-runtime", region_name=region)
        print("BEDROCK_CLIENT: PASS")
    except Exception as exc:
        print(f"BEDROCK_CLIENT: FAIL - {type(exc).__name__}: {_short(exc)}")
        return False

    # --- model access ------------------------------------------------------
    # Minimal valid Converse probe (Nova rejects an empty conversation, so a
    # one-user-message request is the smallest shape that reaches the model).
    try:
        client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": "ping"}]}],
        )
        print(f"MODEL_ACCESS: PASS ({MODEL_ID})")
    except (ClientError, BotoCoreError) as exc:
        print(f"MODEL_ACCESS: FAIL ({MODEL_ID}) - {type(exc).__name__}: {_short(exc)}")
        ready = False
    except Exception as exc:  # unexpected shape - still truthful
        print(f"MODEL_ACCESS: FAIL ({MODEL_ID}) - unexpected {type(exc).__name__}: {_short(exc)}")
        ready = False

    return ready


if __name__ == "__main__":
    ok = run_preflight()
    print("PREFLIGHT:", "READY" if ok else "NOT READY")
    raise SystemExit(0 if ok else 1)
