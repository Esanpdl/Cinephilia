"""Run the prepared, credential-free catalog bundle on a task-owned CPU Studio."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
import uuid
import zipfile
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from apps.recommendations.services.content.artifacts import DATA_FILES, sha256_file, write_json
from apps.recommendations.services.content.engine import TfidfContentService


def safe_error(error):
    # Do not log SDK HTTP headers (which can contain authentication details).
    body = getattr(error, "body", None)
    if body:
        try:
            payload = json.loads(body)
            message = payload.get("message") or payload.get("error") or "Remote API request rejected"
        except (ValueError, AttributeError):
            message = "Remote API request rejected"
    else:
        message = str(error)
    message = str(message)
    # Signed storage URLs are temporary credentials too; omit their query strings.
    message = re.sub(r"https?://[^\s'\"<>]+", lambda match: urlsplit(match.group())._replace(query="", fragment="").geturl(), message)
    for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY"):
        secret = os.environ.get(key)
        if secret:
            message = message.replace(secret, "[redacted]")
    return f"{type(error).__name__}: {message[:1600]}"


def main():
    # Pip progress output can contain Unicode even on an English Windows console.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--teamspace", default="default-project")
    parser.add_argument("--studio", help="Reuse a stopped Studio previously created by this script.")
    parser.add_argument("--recover-run", help="Download an already-built artifact from this run without fitting again.")
    args = parser.parse_args()
    load_dotenv(ROOT / "training/.env", override=False)
    if not all(os.environ.get(key) for key in ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY")):
        raise SystemExit("Set both Lightning credentials in training/.env.")
    bundle = ROOT / "data/content/cinephilia-content-training.zip"
    bundle_manifest = json.loads(bundle.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    original = None
    if args.recover_run:
        if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[a-f0-9]{6}", args.recover_run):
            raise SystemExit("Invalid recovery run ID.")
        original = json.loads((ROOT / "data/content/runs" / (args.recover_run + ".json")).read_text(encoding="utf-8"))
        if original.get("failed_stage") != "download and verify artifact":
            raise SystemExit("Recovery requires a run whose build finished before download failed.")
        bundle = Path(original["training_source_bundle"])
        bundle_manifest = {"bundle_sha256": original["bundle_sha256"]}
        args.studio = original["studio"]
    if sha256_file(bundle) != bundle_manifest["bundle_sha256"]:
        raise SystemExit("Bundle checksum mismatch. Repackage the training bundle.")

    from lightning_sdk import Studio, Teamspace, Machine, Status
    from lightning_sdk.lightning_cloud.openapi import AuthServiceApi
    from lightning_sdk.lightning_cloud.rest_client import create_swagger_client

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    name = args.studio or "cinephilia-content-" + run_id
    if not name.startswith("cinephilia-content-"):
        raise SystemExit("Only task-owned cinephilia-content Studios may be reused.")
    receipt_path = ROOT / "data/content/runs" / (run_id + ".json")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    source_bundle = receipt_path.with_suffix(".training.zip")
    source_runner = receipt_path.with_suffix(".runner.py")
    shutil.copyfile(bundle, source_bundle)
    shutil.copyfile(__file__, source_runner)
    log_path = receipt_path.with_suffix(".log")
    receipt = {"run_id": run_id, "studio": name, "machine": "CPU-4", "bundle_sha256": bundle_manifest["bundle_sha256"], "stage": "authenticate"}
    receipt.update({"training_source_bundle": str(source_bundle), "runner_sha256": sha256_file(source_runner), "log": str(log_path)})
    if original:
        receipt["recovered_from_run"] = original["run_id"]
    studio = None

    def stage(value):
        receipt["stage"] = value
        write_json(receipt_path, receipt)
        print(f"Lightning: {value}", flush=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"Lightning: {value}\n")

    def run(command):
        output, code = studio.run_with_exit_code(command)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n$ {command}\n{output}\nexit_code={code}\n")
        if output:
            print(output[-12000:], flush=True)
        if code != 0:
            raise RuntimeError(f"Remote command exited with {code}: {output[-1600:]}")

    def download(result):
        # The completed ZIP became available in blob storage after the Studio
        # stopped. Stop before download so the filesystem can synchronize.
        if studio.status in (Status.Running, Status.Pending):
            print("Stopping task-owned Studio before artifact download.", flush=True)
            studio.stop()
        for attempt in range(3):
            try:
                studio.download_file("content-result.zip", str(result))
                receipt["download_sha256"] = sha256_file(result)
                return
            except RuntimeError as error:
                if "HTTP 404" not in str(error) or attempt == 2:
                    raise
                print("Waiting for the completed artifact to appear in blob storage.", flush=True)
                time.sleep(3)

    try:
        user = AuthServiceApi(create_swagger_client(check_context=False)).auth_service_get_user(_request_timeout=(10, 20))
        if user.id != os.environ["LIGHTNING_USER_ID"]:
            raise RuntimeError("Lightning account does not match configured user.")
        teamspace = Teamspace(name=args.teamspace, user=user.username)
        receipt["teamspace_id"] = teamspace.id
        stage("create dedicated studio")
        studio = Studio(name=name, teamspace=teamspace, create_ok=not bool(args.studio), disable_secrets=True)
        if not original:
            stage("start CPU")
            studio.start(machine=Machine.CPU)
            stage("upload catalog and scripts")
            studio.upload_file(str(bundle), remote_path="content-training.zip", progress_bar=False)
            stage("prepare Python environment")
            run("python -m zipfile -e content-training.zip content-training")
            # Use the dedicated Studio's provided environment (one per account).
            run("python -c 'import sys; print(sys.version); assert (3, 11) <= sys.version_info[:2] <= (3, 12), \"Python 3.11 or 3.12 required\"'")
            run("python -m pip install -r content-training/training/content/requirements.txt")
            stage("fit TF-IDF and cache cosine neighbors")
            run("python content-training/training/content/build_index.py --snapshot content-training/data/content/catalog.json --output content-training/output")
            code = "from pathlib import Path; import zipfile; p=Path('content-training/output'); z=zipfile.ZipFile('content-result.zip','w',zipfile.ZIP_DEFLATED); [z.write(f,f.name) for f in p.iterdir() if f.is_file()]; z.close()"
            run("python -c " + shlex.quote(code))
        stage("download and verify artifact")
        result = ROOT / "data/content/runs" / (run_id + ".zip")
        download(result)
        directory = ROOT / "data/content/artifacts" / run_id
        with zipfile.ZipFile(result) as archive:
            if set(archive.namelist()) != {*DATA_FILES, "manifest.json"}:
                raise ValueError("Unexpected artifact ZIP contents.")
            directory.mkdir(parents=True)
            archive.extractall(directory)
        service = TfidfContentService(directory)
        receipt["artifact"] = str(directory)
        receipt["catalog_sha256"] = service.manifest["catalog_sha256"]
        receipt["artifact_manifest_sha256"] = sha256_file(directory / "manifest.json")
        stage("complete")
    except Exception as error:
        receipt["error"] = safe_error(error)
        receipt["failed_stage"] = receipt["stage"]
        stage("failed")
        print(receipt["error"], flush=True)
    finally:
        if studio is not None:
            try:
                if studio.status in (Status.Running, Status.Pending):
                    print("Stopping task-owned Studio.", flush=True)
                    studio.stop()
                receipt["final_studio_status"] = str(studio.status)
            except Exception as error:
                receipt["cleanup_error"] = safe_error(error)
                print("Studio cleanup needs attention: " + receipt["cleanup_error"], flush=True)
        write_json(receipt_path, receipt)
        print(f"Run receipt: {receipt_path}", flush=True)
    if receipt["stage"] != "complete" or receipt.get("cleanup_error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
