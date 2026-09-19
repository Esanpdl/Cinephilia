"""Verify Lightning credentials through its SDK without creating compute resources."""
import os
from pathlib import Path

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / "training" / ".env", override=False)
    if not all(os.environ.get(key) for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY")):
        raise SystemExit("Set LIGHTNING_USER_ID and LIGHTNING_API_KEY in training/.env.")

    from lightning_sdk.lightning_cloud.openapi import AuthServiceApi
    from lightning_sdk.lightning_cloud.openapi.rest import ApiException
    from lightning_sdk.lightning_cloud.rest_client import create_swagger_client
    from urllib3.exceptions import HTTPError

    client = create_swagger_client(check_context=False)
    try:
        user = AuthServiceApi(client).auth_service_get_user(_request_timeout=(10, 20))
    except ApiException as error:
        raise SystemExit(f"Lightning authentication check failed (HTTP {error.status}).") from None
    except (HTTPError, OSError):
        raise SystemExit("Lightning could not be reached. Check network access and retry.") from None
    if user.id != os.environ["LIGHTNING_USER_ID"]:
        raise SystemExit("Lightning returned an account different from the configured user ID.")
    print("Lightning credentials verified with a read-only account request. No compute started.")


if __name__ == "__main__":
    main()
