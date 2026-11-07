"""Thin HTTP client. Only read operations are retried."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

from .errors import AutoDLError, SubmissionUncertain, TaskFailed, TaskTimeout

BASE_URL = "https://autodl.art"
SUCCESS = {"SUCCESS", "COMPLETED", "SUCCEEDED"}
FAILURE = {"FAILED", "ERROR", "CANCELLED", "CANCELED"}
PENDING = {"QUEUED", "RUNNING", "PENDING", "PROCESSING", "EXECUTING", "SUBMITTED"}


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", value):
        raise AutoDLError("Invalid workflow/task ID")
    if value in {".", ".."}:
        raise AutoDLError("Invalid workflow/task ID")
    return value


def task_status(data: dict) -> str:
    value = data.get("status")
    if not isinstance(value, str):
        raise AutoDLError("Task response is missing a status")
    return value.upper()


class AutoDLClient:
    def __init__(
        self,
        token: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 60,
        read_retries: int = 2,
    ):
        self._token = token
        self.read_retries = read_retries
        self.http = httpx.Client(
            base_url=BASE_URL, timeout=timeout, transport=transport, follow_redirects=False
        )

    def __enter__(self) -> AutoDLClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self.http.close()

    def _message(self, value: Any) -> str:
        message = str(value)
        if self._token:
            message = message.replace(self._token, "[REDACTED]")
        message = re.sub(r"data:[^\s\"']+", "[MEDIA]", message)
        return message[:400]

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        authenticated: bool = False,
        billable: bool = False,
    ) -> dict:
        if authenticated and not self._token:
            raise AutoDLError("A ComfyUI Token is required")
        headers = {"Authorization": self._token} if authenticated else {}
        attempts = 1 if billable else self.read_retries + 1
        for attempt in range(attempts):
            try:
                response = self.http.request(method, path, json=payload, headers=headers)
            except httpx.RequestError as exc:
                if billable:
                    raise SubmissionUncertain(
                        "Submission connection failed; the task may already exist. "
                        "Check AutoDL calling logs before submitting again."
                    ) from None
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise AutoDLError(f"API connection failed: {type(exc).__name__}") from None
            if (response.status_code == 429 or response.status_code >= 500) and not billable:
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (attempt + 1))
                    continue
            if (response.status_code >= 500 or response.status_code == 408) and billable:
                raise SubmissionUncertain(
                    f"Submission returned HTTP {response.status_code}; check AutoDL calling "
                    "logs before submitting again. No automatic retry was made."
                )
            try:
                body = response.json()
            except ValueError:
                error = SubmissionUncertain if billable and response.is_success else AutoDLError
                raise error(f"API returned non-JSON data (HTTP {response.status_code})") from None
            if not isinstance(body, dict):
                error = SubmissionUncertain if billable and response.is_success else AutoDLError
                raise error("API returned an invalid envelope")
            if not response.is_success or body.get("code") != "Success":
                nested = body.get("error")
                if isinstance(nested, dict):
                    nested = nested.get("message") or nested.get("type")
                message = self._message(
                    body.get("msg") or body.get("message") or nested or "API error"
                )
                if response.status_code in {401, 403}:
                    message += "; check .env and the AutoDL ComfyUI Token group/permissions"
                raise AutoDLError(
                    f"HTTP {response.status_code}, code={self._message(body.get('code'))}: "
                    f"{message}"
                )
            data = body.get("data")
            if not isinstance(data, dict):
                error = SubmissionUncertain if billable else AutoDLError
                raise error("API response is missing its data mapping")
            return data
        raise AutoDLError("Read retries exhausted")

    def workflows(self) -> list[dict]:
        items: list[dict] = []
        seen: set[str] = set()
        page = 1
        while page <= 1000:
            data = self._request(
                "POST", "/api/v1/comfyui/workflows", payload={"page_size": 100, "page_index": page}
            )
            batch = data.get("list")
            if not isinstance(batch, list):
                raise AutoDLError("Invalid catalog page; keeping the existing catalog")
            total = data.get("result_total")
            if not isinstance(total, int) or isinstance(total, bool) or total < 1:
                raise AutoDLError("Empty or invalid catalog; keeping the existing catalog")
            for item in batch:
                if not isinstance(item, dict) or not item.get("uuid"):
                    raise AutoDLError("Invalid workflow in catalog")
                workflow_id = safe_id(item["uuid"])
                if workflow_id in seen:
                    raise AutoDLError("Duplicate catalog entry; refusing an incomplete sync")
                seen.add(workflow_id)
                items.append(item)
            if len(items) == total:
                return items
            if not batch or len(items) > total:
                raise AutoDLError("Catalog pagination is inconsistent")
            page += 1
        raise AutoDLError("Catalog pagination limit reached")

    def workflow(self, workflow_id: str) -> dict:
        workflow_id = safe_id(workflow_id)
        data = self._request("GET", f"/api/v1/comfyui/workflows/{workflow_id}")
        if data.get("uuid") != workflow_id or not isinstance(data.get("input_rules"), dict):
            raise AutoDLError(f"Incomplete workflow metadata: {workflow_id}")
        return data

    def submit(self, workflow_id: str, inputs: dict) -> dict:
        workflow_id = safe_id(workflow_id)
        data = self._request(
            "POST",
            f"/api/v1/comfyui/comfyui_workflow/{workflow_id}",
            payload=inputs,
            authenticated=True,
            billable=True,
        )
        if not isinstance(data.get("task_id"), str) or not data["task_id"]:
            raise SubmissionUncertain("Submission returned no task ID; check AutoDL calling logs")
        safe_id(data["task_id"])
        return data

    def query(self, task_id: str) -> dict:
        task_id = safe_id(task_id)
        data = self._request(
            "GET", f"/api/v1/comfyui/comfyui_workflow/result/{task_id}", authenticated=True
        )
        if data.get("task_id") is not None and data["task_id"] != task_id:
            raise AutoDLError("Query returned a different task ID")
        return {**data, "task_id": task_id}

    def wait(
        self,
        task_id: str,
        *,
        timeout: float = 1800,
        poll_interval: float = 3,
        on_update: Callable[[dict], None] | None = None,
    ) -> dict:
        for value in (timeout, poll_interval):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise AutoDLError("timeout and poll_interval must be positive finite numbers")
        deadline = time.monotonic() + timeout
        while True:
            data = self.query(task_id)
            if on_update:
                on_update(data)
            status = task_status(data)
            if status in SUCCESS:
                return data
            if status in FAILURE:
                message = self._message(data.get("message") or data.get("error") or status)
                raise TaskFailed(f"Task {task_id}: {message}")
            if status not in PENDING:
                raise AutoDLError(f"Unknown task status {status}; resume task {task_id} later")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TaskTimeout(f"Polling timed out; resume with: autodl task wait {task_id}")
            time.sleep(min(poll_interval, remaining))
