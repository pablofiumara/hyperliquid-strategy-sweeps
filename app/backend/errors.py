"""Structured, self-correcting API errors.

The backend is consumed by two very different callers: a human clicking in the
React UI, and an autonomous AI agent that has to decide what to do next without
a human in the loop. A bare `{"detail": "Not Found"}` forces the agent to guess
or to give up. Every failure this app raises deliberately instead answers four
questions in the body:

    code        a stable machine-readable identifier to branch on
    message     one human sentence
    what        what actually went wrong, with the offending values
    fix         the concrete corrective action
    next        a list of valid next calls, ready to be copied

The React client shows `message`; an agent parses `code` and follows `next`.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse


class ApiError(Exception):
    """An error carrying enough context for a caller to self-correct."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        what: str = "",
        fix: str = "",
        next_actions: list[str] | None = None,
        headers: dict[str, str] | None = None,
        extra: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.what = what
        self.fix = fix
        self.next_actions = next_actions or []
        self.headers = headers or {}
        self.extra = extra or {}

    def to_response(self) -> JSONResponse:
        body: dict = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.what:
            body["error"]["what_went_wrong"] = self.what
        if self.fix:
            body["error"]["how_to_fix"] = self.fix
        if self.next_actions:
            body["error"]["valid_next_actions"] = self.next_actions
        if self.extra:
            body["error"].update(self.extra)
        return JSONResponse(status_code=self.status_code, content=body, headers=self.headers)


def not_found(what: str, fix: str, next_actions: list[str] | None = None) -> ApiError:
    return ApiError(
        404,
        "not_found",
        what,
        fix=fix,
        next_actions=next_actions or [],
    )


def capacity_exhausted(
    *,
    capacity: int,
    in_use: int,
    waited_s: float,
    retry_after_s: int,
) -> ApiError:
    """429 for the AI-agent concurrency cap.

    This is the error an autonomous caller is most likely to hit, so it spells
    out the whole situation rather than just saying "try again later".
    """
    return ApiError(
        429,
        "agent_capacity_exhausted",
        "All agent slots are busy. No AI agent can start right now.",
        what=(
            f"capacity={capacity} in_use={in_use} "
            f"waited={waited_s:.1f}s. Every agent call runs a CLI subprocess "
            f"that can take up to 300s, so the server caps how many run at once."
        ),
        fix=(
            f"Wait {retry_after_s}s and retry the same request. The slot is "
            f"released automatically when the current agent finishes; there is "
            f"nothing to clean up and no state to reset."
        ),
        next_actions=[
            f"Sleep {retry_after_s} seconds, then re-issue the identical request.",
            "GET /api/capacity to check free slots before retrying.",
            "Reduce your request rate; do not increase concurrency.",
        ],
        headers={"Retry-After": str(retry_after_s)},
        extra={
            "capacity": capacity,
            "in_use": in_use,
            "free": max(0, capacity - in_use),
            "retry_after_seconds": retry_after_s,
        },
    )