"""The HTTP surface: public health/session status, and SSO-protected course data.

Everything under `/api` needs a vetted proxy identity except `/api/health` and
`/api/session`.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import curriculum, db
from .auth import current_user
from .config import Settings, get_settings
from .runner import RunRequest, RunnerError, run_local

app = FastAPI(title="Operating Systems", docs_url=None, redoc_url=None)


@app.on_event("startup")
def startup() -> None:
    db.init()


# Models -----------------------------------------------------------------




class DraftBody(BaseModel):
    code: str = Field(max_length=200_000)


class ProgressBody(BaseModel):
    status: str = Field(pattern="^(started|solved)$")


class RunBody(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=128)
    mode: str = Field(pattern="^(run|check)$")
    code: str = Field(max_length=200_000)


# Health and session -----------------------------------------------------


@app.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    lessons = curriculum.lesson_list()
    return {
        "ok": True,
        "commit": settings.git_sha,
        "lessons": len(lessons),
        "exercises": len(curriculum.load_exercises()),
    }


@app.get("/api/session")
def session_state(request: Request, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    try:
        name = current_user(request, settings)
    except HTTPException:
        return {"signed_in": False, "username": None}
    return {"signed_in": True, "username": name}





# Content ----------------------------------------------------------------


@app.get("/api/lessons")
def lessons(user: str = Depends(current_user)) -> dict[str, Any]:
    return {"parts": curriculum.parts(), "progress": db.get_progress(user)}


@app.get("/api/lessons/{slug}")
def lesson(slug: str, user: str = Depends(current_user)) -> dict[str, Any]:
    found = curriculum.get_lesson(slug)
    if found is None:
        raise HTTPException(status_code=404, detail="No such lesson")

    payload: dict[str, Any] = dict(found)
    exercise_id = found.get("exercise")
    if exercise_id:
        exercise = curriculum.get_exercise(str(exercise_id))
        if exercise:
            payload["exercise_detail"] = curriculum.public_exercise(exercise)
            payload["draft"] = db.get_draft(user, str(exercise_id))
    db.set_progress(user, slug, "started")
    return payload


@app.get("/api/exercises/{exercise_id}/solution")
def solution(exercise_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    exercise = curriculum.get_exercise(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="No such exercise")
    return {"id": exercise_id, "solution": exercise["solution"]}


# Drafts and progress ----------------------------------------------------


@app.put("/api/drafts/{exercise_id}")
def put_draft(
    exercise_id: str, body: DraftBody, user: str = Depends(current_user)
) -> dict[str, Any]:
    if curriculum.get_exercise(exercise_id) is None:
        raise HTTPException(status_code=404, detail="No such exercise")
    db.save_draft(user, exercise_id, body.code)
    return {"saved": True}


@app.delete("/api/drafts/{exercise_id}")
def drop_draft(exercise_id: str, user: str = Depends(current_user)) -> dict[str, Any]:
    db.delete_draft(user, exercise_id)
    return {"saved": False}


@app.put("/api/progress/{slug}")
def put_progress(
    slug: str, body: ProgressBody, user: str = Depends(current_user)
) -> dict[str, Any]:
    db.set_progress(user, slug, body.status)
    return {"slug": slug, "status": body.status}


@app.get("/api/me")
def me(user: str = Depends(current_user)):
    return {
        "username": user,
        "stats": db.stats(user),
        "runs": db.recent_runs(user),
    }


@app.get("/api/me/export")
def export(user: str = Depends(current_user)) -> PlainTextResponse:
    return PlainTextResponse(
        db.export_all(user),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{user}-os.json"'},
    )


@app.get("/api/compute")
def compute(
    user: str = Depends(current_user), settings: Settings = Depends(get_settings)
) -> dict[str, Any]:
    return {
        "local": {
            "workers": settings.local_workers,
            "memory_mb": settings.local_memory_mb,
            "timeout_ceiling": settings.local_timeout_ceiling,
        },
    }


# The run stream ---------------------------------------------------------


@app.post("/api/run")
async def run(
    body: RunBody,
    user: str = Depends(current_user),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    exercise = curriculum.get_exercise(body.exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="No such exercise")

    request = RunRequest(
        exercise_id=body.exercise_id,
        mode=body.mode,
        code=body.code,
        timeout=int(exercise["timeout"]),
    )
    backend = "local"

    # A draft is saved on every run, so a closed tab never loses work.
    db.save_draft(user, body.exercise_id, body.code)

    async def stream() -> AsyncIterator[bytes]:
        summary: dict[str, Any] = {"ok": False}
        yield _sse({"type": "begin", "backend": backend, "mode": body.mode})
        try:
            source = run_local(request, Path(exercise["directory"]), settings)
            async for event in source:
                if event.get("type") == "done":
                    summary = event
                yield _sse(event)
        except RunnerError as exc:
            yield _sse({"type": "error", "message": str(exc)})
            yield _sse({"type": "done", "ok": False})
        except asyncio.CancelledError:
            # The reader navigated away. Nothing to report, and the local runner
            # kills its process group on the way out.
            raise
        except Exception as exc:  # noqa: BLE001 - the stream must always close
            yield _sse({"type": "error", "message": f"The runner failed: {exc}"})
            yield _sse({"type": "done", "ok": False})
        else:
            db.record_run(user, body.exercise_id, body.mode, backend, summary)
            if body.mode == "check" and summary.get("ok"):
                for lesson in curriculum.lesson_list():
                    if lesson.get("exercise") == body.exercise_id:
                        db.set_progress(user, lesson["slug"], "solved")

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse(event: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(event, default=str)}\n\n".encode()


# Static assets ----------------------------------------------------------


def _mount_frontend() -> None:
    dist = get_settings().frontend_dist.resolve()
    if not dist.is_dir():
        return
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Any:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        candidate = dist / path
        if path and candidate.is_file() and dist in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(index)


_mount_frontend()
