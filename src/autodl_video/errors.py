"""User-facing errors; credentials and media payloads must never appear in messages."""


class AutoDLError(Exception):
    """A recoverable configuration, API or task error."""


class SubmissionUncertain(AutoDLError):
    """A POST may have created a billable task. Never automatically retry it."""


class TaskFailed(AutoDLError):
    """The remote task reached a failure state."""


class TaskTimeout(AutoDLError):
    """Polling stopped; the remote task may still be running."""
