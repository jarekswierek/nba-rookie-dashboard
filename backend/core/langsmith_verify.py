"""LangSmith connection verification script.

Run this AFTER filling in .env with real LANGCHAIN_API_KEY:

    make verify-langsmith

Expected output:
    [OK] Env vars present
    [OK] LangSmith client created
    [OK] Test run submitted — run_id: <uuid>
    [OK] Visible in dashboard: https://smith.langchain.com/...

If you see [FAIL], check your LANGCHAIN_API_KEY and LANGCHAIN_PROJECT.
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import langsmith

_REQUIRED_VARS = (
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_PROJECT",
    "LANGCHAIN_ENDPOINT",
)


def main() -> None:
    """Run end-to-end LangSmith connectivity check."""
    # Step 1: confirm env vars are set
    missing = [v for v in _REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print(f"[FAIL] Missing env vars: {', '.join(missing)}")
        print("       Hint: copy .env.example to .env and fill in the values.")
        sys.exit(1)

    api_key = os.environ["LANGCHAIN_API_KEY"]
    endpoint = os.environ["LANGCHAIN_ENDPOINT"]
    project = os.environ["LANGCHAIN_PROJECT"]

    print("[OK] Env vars present")
    print(f"     project  : {project}")
    print(f"     endpoint : {endpoint}")
    print(f"     tracing  : {os.environ['LANGCHAIN_TRACING_V2']}")

    # Step 2: create LangSmith client
    try:
        client = langsmith.Client(api_url=endpoint, api_key=api_key)
        print("[OK] LangSmith client created")
    except Exception as exc:
        print(f"[FAIL] LangSmith client — {exc}")
        sys.exit(1)

    # Step 3: submit a minimal test run to verify key and project exist
    try:
        run_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)
        client.create_run(
            id=run_id,
            name="langsmith-verify",
            run_type="chain",
            project_name=project,
            inputs={"message": "NBA Rookie Dashboard — connectivity check"},
            start_time=now,
        )
        client.update_run(
            run_id=run_id,
            outputs={"result": "ok"},
            end_time=now,
        )
        print(f"[OK] Test run submitted — run_id: {run_id}")
        print(
            f"[OK] Visible in dashboard: https://smith.langchain.com/o/projects/{project}"
        )
    except Exception as exc:
        print(f"[FAIL] Run submission — {exc}")
        print("       Hint: check LANGCHAIN_API_KEY and LANGCHAIN_PROJECT.")
        sys.exit(1)


if __name__ == "__main__":
    main()
