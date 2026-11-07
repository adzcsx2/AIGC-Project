import httpx
import pytest

from autodl_video.client import AutoDLClient, safe_id
from autodl_video.errors import AutoDLError, SubmissionUncertain, TaskFailed, TaskTimeout


def response(data):
    return httpx.Response(200, json={"code": "Success", "data": data})


def test_raw_auth_submit_and_query():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == "test-token"
        return response({"task_id": "task-1", "status": "SUCCESS"})

    with AutoDLClient("test-token", transport=httpx.MockTransport(handler)) as client:
        assert client.submit("demo", {"prompt": "x"})["task_id"] == "task-1"
        assert client.query("task-1")["status"] == "SUCCESS"
    assert requests[0].method == "POST"
    assert requests[1].method == "GET"
    assert requests[0].url.path.endswith("/demo")


@pytest.mark.parametrize("mode", ["network", "server", "timeout", "invalid-json", "missing-id"])
def test_billable_requests_are_not_retried(mode):
    calls = []

    def handler(request):
        calls.append(request)
        if mode == "network":
            raise httpx.ReadTimeout("test")
        if mode == "server":
            return httpx.Response(503)
        if mode == "timeout":
            return httpx.Response(408)
        if mode == "invalid-json":
            return httpx.Response(200, text="not-json")
        return response({"status": "QUEUED"})

    with AutoDLClient("token", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SubmissionUncertain):
            client.submit("demo", {})
    assert len(calls) == 1


def test_safe_read_retries_and_secret_redaction(monkeypatch):
    monkeypatch.setattr("autodl_video.client.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(401, json={"code": "AuthError", "msg": "secret-token invalid"})

    with AutoDLClient("secret-token", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AutoDLError) as exc:
            client.query("task-1")
    assert len(calls) == 3
    assert "secret-token" not in str(exc.value)
    assert "[REDACTED]" in str(exc.value)


@pytest.mark.parametrize("terminal", ["SUCCESS", "completed", "SUCCEEDED", "FAILED", "mystery"])
def test_polling_states(monkeypatch, terminal):
    monkeypatch.setattr("autodl_video.client.time.sleep", lambda _: None)
    states = iter(["QUEUED", "RUNNING", terminal])
    transport = httpx.MockTransport(lambda request: response({"status": next(states)}))
    with AutoDLClient("token", transport=transport) as client:
        if terminal == "FAILED":
            with pytest.raises(TaskFailed):
                client.wait("task-1")
        elif terminal == "mystery":
            with pytest.raises(AutoDLError, match="Unknown task status"):
                client.wait("task-1")
        else:
            assert client.wait("task-1")["status"] == terminal


def test_poll_timeout(monkeypatch):
    times = iter([0, 2])
    monkeypatch.setattr("autodl_video.client.time.monotonic", lambda: next(times))
    with AutoDLClient(
        "token", transport=httpx.MockTransport(lambda request: response({"status": "RUNNING"}))
    ) as client:
        with pytest.raises(TaskTimeout, match="task wait task-1"):
            client.wait("task-1", timeout=1)


def test_public_metadata_has_no_token_and_paginates(detail):
    calls = []

    def handler(request):
        assert "authorization" not in request.headers
        calls.append(request)
        if request.method == "POST":
            return response(
                {"list": [{"uuid": "demo" if len(calls) == 1 else "other"}], "result_total": 2}
            )
        return response(detail)

    with AutoDLClient("should-not-leak", transport=httpx.MockTransport(handler)) as client:
        assert len(client.workflows()) == 2
        assert client.workflow("demo") == detail


@pytest.mark.parametrize("value", ["../task", "..", ".", "/absolute", "abc?query=bad", ""])
def test_id_validation(value):
    with pytest.raises(AutoDLError):
        safe_id(value)


def test_no_token_no_request():
    with AutoDLClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("network used"))
    ) as client:
        with pytest.raises(AutoDLError, match="Token"):
            client.submit("demo", {})


def test_nested_auth_error_is_actionable_and_redacted():
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            401,
            json={
                "error": {
                    "message": "Invalid authentication credentials: secret-test",
                    "type": "auth",
                }
            },
        )
    )
    with AutoDLClient("secret-test", transport=transport) as client:
        with pytest.raises(AutoDLError) as error:
            client.query("task-1")
    assert "Invalid authentication credentials" in str(error.value)
    assert "ComfyUI Token group" in str(error.value)
    assert "secret-test" not in str(error.value)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_invalid_poll_time_is_rejected_without_request(timeout):
    with AutoDLClient(
        "token", transport=httpx.MockTransport(lambda _: pytest.fail("network used"))
    ) as client:
        with pytest.raises(AutoDLError, match="positive finite"):
            client.wait("task-1", timeout=timeout)


@pytest.mark.parametrize(
    "data",
    [
        {"list": [], "result_total": 0},
        {"list": [], "result_total": 3},
        {"list": "wrong", "result_total": 1},
        {"list": [{"uuid": "demo"}, {"uuid": "demo"}], "result_total": 2},
    ],
)
def test_corrupt_catalog_is_rejected(data):
    with AutoDLClient(transport=httpx.MockTransport(lambda _: response(data))) as client:
        with pytest.raises(AutoDLError):
            client.workflows()
