"""Course-wide facts shared by the REST API and the MCP server."""

from __future__ import annotations

from typing import Any

from . import curriculum, db


def progress_summary(user: str) -> dict[str, Any]:
    """Solved count, lesson total, and the most recently touched lesson.

    Only lessons in the current list count, so rows for removed lessons are
    ignored.
    """
    lessons = {lesson["slug"]: lesson for lesson in curriculum.lesson_list()}
    rows = {
        slug: row for slug, row in db.get_progress(user).items() if slug in lessons
    }
    done = sum(1 for row in rows.values() if row["status"] == "solved")
    last = None
    if rows:
        slug = max(rows, key=lambda key: rows[key]["updated_at"])
        last = {"slug": slug, "title": lessons[slug]["title"]}
    return {"done": done, "total": len(lessons), "last": last}
