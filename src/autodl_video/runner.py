"""YAML-to-video orchestration, with a durable record before every paid submission."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .catalog import entry_from_detail, get_workflow, utc_now
from .characters import validate_voice_payload
from .client import SUCCESS, AutoDLClient, safe_id, task_status
from .config import atomic_json, load_token, load_yaml, project_root
from .errors import AutoDLError, SubmissionUncertain
from .materials import check_config_materials, local_path
from .paths import ensure_project_output, project_owner, resolve_media_path
from .schema import MEDIA_TYPES, estimate_cost, validate_inputs
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
        config_path = resolve_media_path(Path(config_path).resolve(), self.root)
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
        check_config_materials(config, local["input_rules"], config_path.parent, root=self.root)
        preview = validate_inputs(
            inputs, local["input_rules"], base_dir=config_path.parent, encode_media=False,
            root=self.root,
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
        work = project_owner(config_path, root=self.root)
        default_output = str(
            (work or self.root / "projects" / "工具验证")
            / "04-输出"
            / "原始片段"
            / config_path.stem
        )
        output_dir = config.get("output_dir", default_output)
        if not isinstance(output_dir, str) or not output_dir.strip():
            raise AutoDLError("output_dir must be a nonempty path string")
        destination = Path(output_dir)
        if not destination.is_absolute():
            destination = self.root / destination
        destination = self._generation_destination(destination, config_path, config, local)
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
        voice_approvals = check_config_materials(
            config, live["input_rules"], config_path.parent, root=self.root
        )
        destination = self._generation_destination(destination, config_path, config, live)
        payload = validate_inputs(
            inputs, live["input_rules"], base_dir=config_path.parent, root=self.root
        )
        validate_voice_payload(payload, voice_approvals)
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

    def _generation_destination(
        self, destination: Path, config_path: Path, config: dict, workflow: dict
    ) -> Path:
        sources = [config_path]
        if "materials_manifest" in config:
            sources.append(local_path(
                config_path.parent, config["materials_manifest"], root=self.root
            ))
        for field, value in config.get("inputs", {}).items():
            if workflow["input_rules"].get(field, {}).get("type") not in MEDIA_TYPES:
                continue
            # Remote and inline media have no local project owner. Their format is
            # still validated by validate_inputs before any submission.
            if not isinstance(value, str) or value.startswith(("http://", "https://", "data:")):
                continue
            sources.append(config_path.parent / Path(value).expanduser())
        destination = self._check_destination(destination, *sources)
        owner = project_owner(config_path, root=self.root)
        if owner and any(
            not resolve_media_path(source, self.root).is_relative_to(owner)
            for source in sources[1:]
        ):
            raise AutoDLError("本作品的素材清单与本地媒体必须先归档到同一作品内")
        return destination

    def _check_destination(self, destination: Path, *sources: Path) -> Path:
        destination = ensure_project_output(destination, *sources, root=self.root)
        if (
            destination.is_relative_to(self.root)
            and project_owner(destination, root=self.root) is None
        ):
            raise AutoDLError(
                "仓库内输出必须归档到含 project.yaml 的作品内；独立临时输出请使用仓库外目录"
            )
        return destination

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

    def _download(self, data: dict, destination: Path, *, reuse_archives: bool = False) -> dict:
        task_id = data["task_id"]
        with self.store.lock(task_id, download=True):
            # Another download may have finished after our query. Recheck ownership
            # and read its durable partial results only after acquiring the lock.
            destination = self._task_destination(task_id, destination)
            record = self.store.read(task_id)
            known = [path for path in self.store.recovery_files(record) if path.is_file()]
            restricted = not reuse_archives or record.get("download_scope") == str(destination)
            if restricted:
                known = [path for path in known if path.parent == destination]
            journal = record.get("download_journal", [])

            def journal_entry(path: Path, size: int, digest: str, state: str) -> None:
                journal[:] = [entry for entry in journal if Path(entry["path"]) != path]
                journal.append({"path": str(path), "size": size, "sha256": digest, "state": state})

            def intend(path: Path, size: int, digest: str) -> None:
                journal_entry(path, size, digest, "pending")
                self.store.save(
                    task_id, output_dir=str(destination), download_journal=journal,
                    download_scope=str(destination) if restricted else None,
                )

            def remember(path: Path, size: int, digest: str) -> None:
                journal_entry(path, size, digest, "published")
                if path not in known:
                    known.append(path)
                self.store.save(
                    task_id, output_dir=str(destination), files=[str(p) for p in known],
                    download_journal=journal,
                    download_scope=str(destination) if restricted else None,
                )

            files = download_results(
                data, destination, root=self.root, existing_files=known,
                on_publish=intend, on_result=remember,
            )
            self.store.save(
                task_id, output_dir=str(destination),
                files=[str(path.resolve()) for path in files],
            )
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
        destination = self._task_destination(task_id, output_dir)
        self.store.save(task_id, output_dir=str(destination.resolve()))
        with AutoDLClient(load_token(self.root)) as client:
            data = self._wait(client, task_id, timeout, poll_interval, on_update)
        return self._download(data, destination, reuse_archives=output_dir is None)

    def download(self, task_id: str, *, output_dir: str | Path | None = None) -> dict:
        destination = self._task_destination(task_id, output_dir)
        data = self.status(task_id)
        if task_status(data) not in SUCCESS:
            raise AutoDLError(f"Task {task_id} is not complete; use autodl task wait")
        return self._download(data, destination, reuse_archives=output_dir is None)

    def _task_destination(self, task_id: str, output_dir: str | Path | None) -> Path:
        record_path = self.store.directory / f"{safe_id(task_id)}.json"
        record = self.store.read(task_id) if record_path.exists() else {}
        config = record.get("config_path")
        source = resolve_media_path(Path(config), self.root) if config else None
        recorded = record.get("output_dir")
        previous = resolve_media_path(Path(recorded), self.root) if recorded else None
        archives = [path for path in self.store.recovery_files(record) if path.is_file()]
        sources = [path for path in (source, previous, *archives) if path is not None]
        owners = {owner for path in sources if (owner := project_owner(path, root=self.root))}
        if len(owners) > 1:
            raise AutoDLError("任务记录包含不同作品的配置、输出或已归档文件；请先核对归属")
        owner = next(iter(owners), None)
        if output_dir is not None:
            if not str(output_dir).strip():
                raise AutoDLError("output_dir must be a nonempty path string")
            destination = Path(output_dir)
        elif owner and (previous is None or project_owner(previous, root=self.root) is None):
            # An unmapped historical directory must not recreate the old asset tree.
            archive_folders = {
                path.parent for path in archives if project_owner(path, root=self.root) == owner
            }
            if source and project_owner(source, root=self.root) == owner:
                destination = owner / "04-输出" / "原始片段" / source.stem
            elif len(archive_folders) == 1:
                destination = archive_folders.pop()
            else:
                destination = owner / "04-输出" / "原始片段" / task_id
        elif previous is not None and (
            project_owner(previous, root=self.root) is not None
            or not previous.is_relative_to(self.root)
        ):
            # An unowned historical directory inside this repo needs an explicit
            # project destination, regardless of its old folder name.
            destination = previous
        else:
            raise AutoDLError("无法确定历史任务所属作品；请用 --output-dir 指定归档目录")
        if not destination.is_absolute():
            destination = self.root / destination
        return self._check_destination(destination, *sources)
