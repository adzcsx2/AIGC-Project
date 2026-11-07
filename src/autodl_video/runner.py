"""YAML-to-video orchestration, with a durable record before every paid submission."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .catalog import entry_from_detail, get_workflow, utc_now
from .client import SUCCESS, AutoDLClient, safe_id, task_status
from .config import atomic_json, load_token, load_yaml, project_root
from .errors import AutoDLError, SubmissionUncertain
from .materials import check_config_materials
from .schema import estimate_cost, validate_inputs
from .storage import TaskStore, download_results


def budget_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        budget = Decimal(str(value))
    except InvalidOperation:
        raise AutoDLError("max_cost_cny must be a nonnegative decimal number") from None
    if not budget.is_finite() or budget < 0:
        raise AutoDLError("max_cost_cny must be a finite, nonnegative number")
    return budget


class VideoProject:
    def __init__(self, root: str | Path | None = None):
        self.root = project_root(root)
        self.store = TaskStore(self.root)

    def generate(
        self,
        config_path: str | Path,
        *,
        dry_run: bool = False,
        wait: bool = True,
        max_cost_cny: str | Decimal | None = None,
        on_update: Callable[[dict], None] | None = None,
    ) -> dict:
        """Run a YAML configuration; dry_run never contacts the network or loads the Token."""
        config_path = Path(config_path).resolve()
        config = load_yaml(config_path)
        allowed = {
            "workflow_id",
            "inputs",
            "output_dir",
            "timeout",
            "poll_interval",
            "max_cost_cny",
            "materials_manifest",
            "shot_id",
        }
        if config.keys() - allowed:
            raise AutoDLError(f"Unknown config key(s): {sorted(config.keys() - allowed, key=str)}")
        workflow_id = safe_id(config.get("workflow_id", ""))
        if not workflow_id:
            raise AutoDLError("workflow_id is required")
        local = get_workflow(self.root, workflow_id)
        inputs = config.get("inputs", {})
        check_config_materials(config, local["input_rules"], config_path.parent)
        preview = validate_inputs(
            inputs, local["input_rules"], base_dir=config_path.parent, encode_media=False
        )
        budget = budget_decimal(
            max_cost_cny if max_cost_cny is not None else config.get("max_cost_cny")
        )
        timeout = config.get("timeout", 1800)
        interval = config.get("poll_interval", 3)
        for key, value in {"timeout": timeout, "poll_interval": interval}.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 < value < float("inf")
            ):
                raise AutoDLError(f"{key} must be a positive finite number")
        output_dir = config.get("output_dir", "outputs")
        if not isinstance(output_dir, str) or not output_dir.strip():
            raise AutoDLError("output_dir must be a nonempty path string")
        destination = Path(output_dir)
        if not destination.is_absolute():
            destination = self.root / destination
        estimate = estimate_cost(local, inputs)
        if dry_run:
            self._check_budget(budget, estimate)
            return {
                "dry_run": True,
                "workflow_id": workflow_id,
                "inputs": preview,
                "estimated_max_cost_cny": str(estimate) if estimate is not None else None,
                "max_cost_cny": str(budget) if budget is not None else None,
                "output_dir": str(destination.resolve()),
            }

        with AutoDLClient() as public:
            live = entry_from_detail(public.workflow(workflow_id))
        check_config_materials(config, live["input_rules"], config_path.parent)
        payload = validate_inputs(inputs, live["input_rules"], base_dir=config_path.parent)
        estimate = estimate_cost(live, inputs)
        self._check_budget(budget, estimate)
        token = load_token(self.root)
        attempt_id = str(uuid.uuid4())
        attempt_path = self.root / ".autodl" / "attempts" / f"{attempt_id}.json"
        attempt = {
            "attempt_id": attempt_id,
            "workflow_id": workflow_id,
            "config_path": str(config_path),
            "created_at": utc_now(),
            "state": "SUBMITTING",
            "estimated_max_cost_cny": str(estimate) if estimate is not None else None,
        }
        atomic_json(attempt_path, attempt)
        with AutoDLClient(token) as client:
            try:
                data = client.submit(workflow_id, payload)
            except AutoDLError as exc:
                attempt["state"] = (
                    "UNCERTAIN" if isinstance(exc, SubmissionUncertain) else "REJECTED"
                )
                atomic_json(attempt_path, attempt)
                raise
            task_id = data["task_id"]
            # Save the ID before polling, downloading, or reporting progress.
            try:
                self.store.save(
                    task_id,
                    workflow_id=workflow_id,
                    config_path=str(config_path),
                    output_dir=str(destination.resolve()),
                    submitted_at=utc_now(),
                    response=data,
                    estimated_max_cost_cny=attempt["estimated_max_cost_cny"],
                )
                attempt.update(state="SUBMITTED", task_id=task_id)
                atomic_json(attempt_path, attempt)
            except OSError:
                raise AutoDLError(
                    f"Task was submitted: {task_id}, but its local record could not be saved. "
                    f"Do not submit again; resume with: autodl task wait {task_id}"
                ) from None
            if on_update:
                on_update(data)
            if not wait:
                return {"task_id": task_id, "status": data.get("status"), "files": []}
            data = self._wait(client, task_id, timeout, interval, on_update)
        return self._download(data, destination)

    @staticmethod
    def _check_budget(budget: Decimal | None, estimate: Decimal | None) -> None:
        if budget is not None and estimate is None:
            raise AutoDLError("Cannot estimate this workflow's cost; no task was submitted")
        if budget is not None and estimate is not None and estimate > budget:
            raise AutoDLError(
                f"Estimated CNY {estimate} exceeds budget CNY {budget}; not submitted"
            )

    def _wait(
        self,
        client: AutoDLClient,
        task_id: str,
        timeout: float,
        interval: float,
        on_update: Callable[[dict], None] | None,
    ) -> dict:
        def update(data: dict) -> None:
            self.store.save(task_id, response=data)
            if on_update:
                on_update(data)

        return client.wait(task_id, timeout=timeout, poll_interval=interval, on_update=update)

    def _download(self, data: dict, destination: Path) -> dict:
        files = download_results(data, destination)
        self.store.save(data["task_id"], files=[str(path.resolve()) for path in files])
        return {
            "task_id": data["task_id"],
            "status": task_status(data),
            "files": [str(path.resolve()) for path in files],
        }

    def status(self, task_id: str) -> dict:
        with AutoDLClient(load_token(self.root)) as client:
            data = client.query(task_id)
        self.store.save(task_id, response=data)
        return data

    def resume(
        self,
        task_id: str,
        *,
        output_dir: str | Path | None = None,
        timeout: float = 1800,
        poll_interval: float = 3,
        on_update: Callable[[dict], None] | None = None,
    ) -> dict:
        record_path = self.store.directory / f"{safe_id(task_id)}.json"
        record = self.store.read(task_id) if record_path.exists() else {}
        destination = Path(output_dir or record.get("output_dir") or self.root / "outputs")
        if not destination.is_absolute():
            destination = self.root / destination
        self.store.save(task_id, output_dir=str(destination.resolve()))
        with AutoDLClient(load_token(self.root)) as client:
            data = self._wait(client, task_id, timeout, poll_interval, on_update)
        return self._download(data, destination)

    def download(self, task_id: str, *, output_dir: str | Path | None = None) -> dict:
        data = self.status(task_id)
        if task_status(data) not in SUCCESS:
            raise AutoDLError(f"Task {task_id} is not complete; use autodl task wait")
        record = self.store.read(task_id)
        destination = Path(output_dir or record.get("output_dir") or self.root / "outputs")
        if not destination.is_absolute():
            destination = self.root / destination
        return self._download(data, destination)
