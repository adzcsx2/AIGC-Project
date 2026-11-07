"""Local Midjourney proxy: YAML jobs, single submissions and resumable downloads."""

from __future__ import annotations

import math
import os
import re
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

from .catalog import utc_now
from .client import safe_id
from .config import atomic_json, load_yaml, project_root
from .errors import AutoDLError, SubmissionUncertain, TaskFailed, TaskTimeout
from .schema import validate_inputs
from .storage import TaskStore, download_results

DEFAULT_SERVER = "http://127.0.0.1:6013"
PENDING = {"NOT_START", "SUBMITTED", "IN_PROGRESS"}


def _origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        raise AutoDLError("MJ_SERVER 不是有效地址") from None
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise AutoDLError("MJ_SERVER 应为本机 HTTP 或 HTTPS 根地址，不带路径和凭据")
    return value.rstrip("/")


def _settings(root: Path) -> tuple[str, str]:
    values = dotenv_values(root / ".env", interpolate=False)
    server = os.environ.get("MJ_SERVER") or values.get("MJ_SERVER") or DEFAULT_SERVER
    secret = (os.environ.get("MJ_API_SECRET") or values.get("MJ_API_SECRET") or "").strip()
    if not secret:
        raise AutoDLError("请在项目 .env 中填写 MJ_API_SECRET（本地代理密钥）")
    if any(character.isspace() for character in secret):
        raise AutoDLError("MJ_API_SECRET 不能包含空白字符")
    return _origin(server), secret


def _positive(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise AutoDLError(f"{name} 必须为正的有限数值")
    return float(value)


class MidjourneyClient:
    def __init__(
        self,
        secret: str,
        *,
        server: str = DEFAULT_SERVER,
        transport: httpx.BaseTransport | None = None,
        read_retries: int = 2,
    ):
        if not secret or any(character.isspace() for character in secret):
            raise AutoDLError("请填写有效的本地代理密钥")
        if isinstance(read_retries, bool) or not isinstance(read_retries, int) or read_retries < 0:
            raise AutoDLError("read_retries 必须为非负整数")
        self._secret = secret
        self.read_retries = read_retries
        self.http = httpx.Client(
            base_url=_origin(server),
            timeout=30,
            transport=transport,
            follow_redirects=False,
            trust_env=False,
        )

    @classmethod
    def from_project(cls, root: Path) -> MidjourneyClient:
        server, secret = _settings(root)
        return cls(secret, server=server)

    def __enter__(self) -> MidjourneyClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.http.close()

    def _message(self, value: object) -> str:
        text = str(value).replace(self._secret, "[REDACTED]")
        return re.sub(r"data:[^\s\"']+", "[MEDIA]", text)[:300]

    def _request(self, method: str, path: str, payload: dict | None = None) -> object:
        submitting = method == "POST"
        attempts = 1 if submitting else self.read_retries + 1
        for attempt in range(attempts):
            try:
                response = self.http.request(
                    method, path, json=payload, headers={"mj-api-secret": self._secret}
                )
            except httpx.RequestError as exc:
                if submitting:
                    raise SubmissionUncertain(
                        "MJ 提交连接中断，任务可能已创建；"
                        "先查 Discord 历史及本地 attempts，不要重发"
                    ) from None
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise AutoDLError(f"MJ 代理连接失败：{type(exc).__name__}") from None
            if not submitting and (response.status_code == 429 or response.status_code >= 500):
                if attempt + 1 < attempts:
                    time.sleep(0.5 * (attempt + 1))
                    continue
            if submitting and (
                response.is_redirect or response.status_code == 408 or response.status_code >= 500
            ):
                raise SubmissionUncertain("MJ 提交结果不确定；已停止，未自动重试，请先核对任务记录")
            if not response.is_success:
                raise AutoDLError(
                    f"MJ 代理返回 HTTP {response.status_code}，请检查本机服务与代理密钥"
                )
            try:
                return response.json()
            except ValueError:
                error = SubmissionUncertain if submitting else AutoDLError
                raise error("MJ 代理未返回有效 JSON，请先核对任务记录") from None
        raise AutoDLError("MJ 查询重试次数耗尽")

    def submit(self, path: str, payload: dict) -> dict:
        if path not in {"/mj/submit/imagine", "/mj/submit/simple-change"}:
            raise AutoDLError("不支持的 MJ 提交接口")
        data = self._request("POST", path, payload)
        if not isinstance(data, dict) or type(data.get("code")) is not int:
            raise SubmissionUncertain("MJ 提交响应结构不明，请先核对 Discord 和本地 attempts")
        if data["code"] not in {1, 21, 22}:
            message = self._message(data.get("description", data["code"]))
            raise AutoDLError(f"MJ 拒绝提交：{message}")
        task_id = data.get("result")
        try:
            safe_id(task_id)
        except AutoDLError:
            raise SubmissionUncertain("MJ 返回的任务 ID 缺失或无效，请先核对任务记录") from None
        return {"task_id": task_id, "status": "SUBMITTED", "code": data["code"]}

    def query(self, task_id: str) -> dict:
        task_id = safe_id(task_id)
        data = self._request("GET", f"/mj/task/{task_id}/fetch")
        if not isinstance(data, dict):
            raise AutoDLError(
                "MJ 任务不存在或代理重启后记录丢失；请查 Discord 历史，勿自动重新生成"
            )
        if data.get("id") != task_id or data.get("status") not in {*PENDING, "SUCCESS", "FAILURE"}:
            raise AutoDLError("MJ 返回的任务 ID 或状态无效")
        return {**data, "task_id": task_id}

    def doctor(self) -> dict:
        data = self._request("GET", "/mj/task/list")
        if not isinstance(data, list):
            raise AutoDLError("MJ 代理任务列表格式不正确")
        return {
            "本机代理": "可访问，鉴权通过",
            "代理任务记录数": len(data),
            "Discord连接": "此接口不证明实时连接，需核对代理账号初始化日志",
            "生图验证": "本次检查未提交生成任务",
        }

    def wait(
        self,
        task_id: str,
        *,
        timeout: float = 1800,
        poll_interval: float = 3,
        on_update: Callable[[dict], None] | None = None,
    ) -> dict:
        timeout = _positive(timeout, "timeout")
        poll_interval = _positive(poll_interval, "poll_interval")
        deadline = time.monotonic() + timeout
        while True:
            data = self.query(task_id)
            if on_update:
                on_update(data)
            if data["status"] == "SUCCESS":
                return data
            if data["status"] == "FAILURE":
                message = self._message(data.get("failReason") or "未知原因")
                raise TaskFailed(f"MJ 任务失败：{message}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TaskTimeout(f"MJ 等待超时，可用 autodl mj wait {task_id} 继续查询")
            time.sleep(min(poll_interval, remaining))


class MidjourneyProject:
    def __init__(self, root: str | Path | None = None):
        self.root = project_root(root)
        self.store = TaskStore(self.root)
        self.store.directory = self.root / ".autodl" / "midjourney" / "tasks"

    def _destination(self, value: str | Path) -> Path:
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise AutoDLError("output_dir 必须为非空目录路径")
        path = Path(value)
        path = (path if path.is_absolute() else self.root / path).resolve()
        if path.is_relative_to((self.root / "assets").resolve()):
            raise AutoDLError("原始结果请下载到 outputs；审核后按中文名称归档进 assets")
        return path

    def generate(
        self, config_path: str | Path, *, dry_run: bool = False, wait: bool = True
    ) -> dict:
        path = Path(config_path).resolve()
        config = load_yaml(path)
        allowed = {"prompt", "reference_images", "output_dir", "timeout", "poll_interval"}
        if config.keys() - allowed:
            raise AutoDLError("MJ YAML 包含未知字段")
        prompt = validate_inputs(
            {"prompt": config.get("prompt")},
            {"prompt": {"type": "prompt", "required": True}},
            base_dir=path.parent,
        )["prompt"]
        references = config.get("reference_images", [])
        if not isinstance(references, list):
            raise AutoDLError("reference_images 必须为本地图片路径列表")
        media = {}
        for index, value in enumerate(references):
            if not isinstance(value, str) or value.startswith(("http://", "https://")):
                raise AutoDLError("reference_images 请使用本地图片路径或图片 Base64 data URL")
            media[str(index)] = value
        rules = {
            key: {"type": "image", "accept_types": ["image/png", "image/jpeg", "image/webp"]}
            for key in media
        }
        images = validate_inputs(media, rules, base_dir=path.parent, encode_media=not dry_run)
        timeout = _positive(config.get("timeout", 1800), "timeout")
        interval = _positive(config.get("poll_interval", 3), "poll_interval")
        destination = self._destination(config.get("output_dir", "outputs/midjourney"))
        if dry_run:
            return {
                "dry_run": True,
                "prompt": prompt,
                "reference_images": list(images.values()),
                "output_dir": str(destination),
                "说明": "仅离线检查，未加载凭据、未联网、未提交任务；不估算会员分钟消耗",
            }
        payload = {"prompt": prompt, "base64Array": list(images.values()), "notifyHook": ""}
        return self._submit("/mj/submit/imagine", payload, destination, wait, timeout, interval)

    def change(self, task_id: str, operation: str, *, wait: bool = True) -> dict:
        task_id = safe_id(task_id)
        if not re.fullmatch(r"[UV][1-4]|R", operation):
            raise AutoDLError("变更操作应为 U1～U4、V1～V4 或 R")
        return self._submit(
            "/mj/submit/simple-change",
            {"content": f"{task_id} {operation}", "notifyHook": ""},
            self._destination("outputs/midjourney"),
            wait,
            1800,
            3,
        )

    def _submit(
        self,
        endpoint: str,
        payload: dict,
        destination: Path,
        wait: bool,
        timeout: float,
        interval: float,
    ) -> dict:
        # State is a correlation marker only; it does not provide server-side idempotency.
        attempt_id = str(uuid.uuid4())
        payload = {**payload, "state": attempt_id}
        attempt = {
            "attempt_id": attempt_id,
            "endpoint": endpoint,
            "created_at": utc_now(),
            "state": "SUBMITTING",
        }
        attempt_path = self.root / ".autodl" / "midjourney" / "attempts" / f"{attempt_id}.json"
        with MidjourneyClient.from_project(self.root) as client:
            atomic_json(attempt_path, attempt)
            try:
                data = client.submit(endpoint, payload)
            except AutoDLError as exc:
                attempt["state"] = (
                    "UNCERTAIN" if isinstance(exc, SubmissionUncertain) else "REJECTED"
                )
                atomic_json(attempt_path, attempt)
                raise
            task_id = data["task_id"]
            try:
                atomic_json(attempt_path, {**attempt, "state": "SUBMITTED", "task_id": task_id})
                self.store.save(task_id, response=data, output_dir=str(destination))
            except OSError:
                raise AutoDLError(
                    f"MJ 任务已提交但记录保存失败：{task_id}；勿重新生成，使用 autodl mj wait 恢复"
                ) from None
            if not wait:
                return {**data, "files": []}
            data = client.wait(
                task_id,
                timeout=timeout,
                poll_interval=interval,
                on_update=lambda update: self.store.save(task_id, response=update),
            )
        return self._download(data, destination)

    def status(self, task_id: str) -> dict:
        with MidjourneyClient.from_project(self.root) as client:
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
    ) -> dict:
        safe_id(task_id)
        record_path = self.store.directory / f"{task_id}.json"
        record = self.store.read(task_id) if record_path.exists() else {}
        destination = self._destination(
            output_dir or record.get("output_dir") or "outputs/midjourney"
        )
        with MidjourneyClient.from_project(self.root) as client:
            data = client.wait(
                task_id,
                timeout=timeout,
                poll_interval=poll_interval,
                on_update=lambda update: self.store.save(task_id, response=update),
            )
        self.store.save(task_id, output_dir=str(destination))
        return self._download(data, destination)

    def download(self, task_id: str, *, output_dir: str | Path | None = None) -> dict:
        data = self.status(task_id)
        record = self.store.read(task_id)
        destination = self._destination(
            output_dir or record.get("output_dir") or "outputs/midjourney"
        )
        return self._download(data, destination)

    def _download(self, data: dict, destination: Path) -> dict:
        if data["status"] != "SUCCESS":
            raise AutoDLError("MJ 任务尚未成功，不能下载最终结果")
        url = data.get("imageUrl")
        if not isinstance(url, str) or not url:
            raise AutoDLError("MJ 成功任务没有图片 URL")
        # Use the same independent unauthenticated download client as AutoDL.
        files = download_results(
            {"task_id": data["task_id"], "results": [{"url": url, "type": "image"}]}, destination
        )
        self.store.save(data["task_id"], files=[str(path.resolve()) for path in files])
        return {
            "task_id": data["task_id"],
            "status": data["status"],
            "files": [str(p) for p in files],
        }
