"""LangSmith connection verification script.

Run this AFTER filling in .env with real LANGCHAIN_API_KEY:

    make verify-langsmith

Expected output:
    [OK] Settings loaded
    [OK] LangSmith client created
    [OK] Test run submitted — run_id: <uuid>
    [OK] Visible in dashboard: https://smith.langchain.com/...

If you see [FAIL], check your LANGCHAIN_API_KEY and LANGCHAIN_PROJECT.
"""

import sys
import uuid
from datetime import datetime, timezone

import langsmith

from backend.core.config import get_settings


def main() -> None:
    """Run end-to-end LangSmith connectivity check."""
    # Step 1: validate settings load
    try:
        settings = get_settings()
        print("[OK] Settings loaded")
        print(f"     project  : {settings.langchain_project}")
        print(f"     endpoint : {settings.langchain_endpoint}")
        print(f"     tracing  : {settings.langchain_tracing_v2}")
    except Exception as exc:
        print(f"[FAIL] Settings — {exc}")
        print("       Hint: copy .env.example to .env and fill in the values.")
        sys.exit(1)

    # Step 2: create LangSmith client
    try:
        client = langsmith.Client(
            api_url=settings.langchain_endpoint,
            api_key=settings.langchain_api_key,
        )
        print("[OK] LangSmith client created")
    except Exception as exc:
        print(f"[FAIL] LangSmith client — {exc}")
        sys.exit(1)

    # Step 3: submit a minimal test run
    # We create a run manually (no LangChain chain needed) to verify
    # that the API key is valid and the project exists.
    try:
        run_id = uuid.uuid4()
        now = datetime.now(tz=timezone.utc)

        client.create_run(
            id=run_id,
            name="langsmith-verify",
            run_type="chain",
            project_name=settings.langchain_project,
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
            f"[OK] Visible in dashboard: "
            f"https://smith.langchain.com/o/projects/{settings.langchain_project}"
        )
    except Exception as exc:
        print(f"[FAIL] Run submission — {exc}")
        print("       Hint: check LANGCHAIN_API_KEY and LANGCHAIN_PROJECT.")
        sys.exit(1)


if __name__ == "__main__":
    main()
