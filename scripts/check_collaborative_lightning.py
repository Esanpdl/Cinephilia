"""Read live training status and reported balances without starting/stopping a Studio."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import load_dotenv

from train_collaborative_lightning import safe_error

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio", required=True)
    args = parser.parse_args()
    load_dotenv(ROOT / "training/.env")
    from lightning_sdk import Studio, Teamspace, Status
    from lightning_sdk.lightning_cloud.openapi import AuthServiceApi, BillingServiceApi
    from lightning_sdk.lightning_cloud.rest_client import create_swagger_client

    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "studio": args.studio}
    try:
        client = create_swagger_client(check_context=False)
        user = AuthServiceApi(client).auth_service_get_user(_request_timeout=(10, 20))
        teamspace = Teamspace(name="default-project", user=user.username)
        studio = Studio(name=args.studio, teamspace=teamspace, create_ok=False, disable_secrets=True)
        status = studio.status
        result["status"] = str(status)
        billing = BillingServiceApi(client)
        for label, method, values in (
            ("user", billing.billing_service_get_user_balance, {}),
            ("project", billing.billing_service_get_project_balance, {"project_id": teamspace.id}),
        ):
            try:
                result[label + "_balance"] = method(**values, _request_timeout=(10, 20)).balance
            except Exception as error:
                result[label + "_balance_error"] = safe_error(error)
        if status == Status.Running:
            output, code = studio.run_with_exit_code("ps -eo pid,etimes,pcpu,rss,args | grep '[p]ython collaborative-training/training/collaborative/build_model.py'")
            result["training_process_columns"] = "PID, elapsed seconds, CPU percent, resident memory KiB, command"
            result["training_process"] = output.strip()
            result["process_check_exit_code"] = code
    except Exception as error:
        result["error"] = safe_error(error)
    print(json.dumps(result, indent=2), flush=True)
    (ROOT / "data/collaborative/lightning-status.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
