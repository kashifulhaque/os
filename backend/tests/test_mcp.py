"""The MCP endpoint, its bearer tokens, and the token management API."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SECRET = "test-proxy-secret"
SIGNED_IN = {"Remote-User": "Portal", "X-SSO-Proxy": SECRET}
OTHER = {"Remote-User": "other", "X-SSO-Proxy": SECRET}
ACCEPT = "application/json, text/event-stream"

LESSON = """---
title: Processes and the process table
slug: 001-alpha
part: "Part 1 — Processes"
summary: What the kernel keeps for every running program.
minutes: 20
gpu: false
objectives:
  - State one fact.
  - State a second fact.
  - State a third fact.
exercise: 001-alpha
---

# Processes and the process table

A process is a running program with its own record in the kernel.

## The zombie state

A zombie is a process that exited but whose parent has not called wait.

```python
# Reap the child so it is not left as a zombie
os.wait()
```
"""

SECOND = LESSON.replace("001-alpha", "002-beta").replace("Part 1 — Processes", "Part 2 — Signals").replace(
    "Processes and the process table", "Signals"
).replace("The zombie state", "Handlers").replace(
    "A zombie is a process that exited", "A handler is a function the kernel calls"
)

TESTS = """from oscheck import check, equal


@check("add returns the sum")
def _(sub):
    equal(sub.add(2, 3), 5)
"""


class MCPTests(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        lessons = self.root / "content" / "lessons"
        lessons.mkdir(parents=True)
        (lessons / "001-alpha.md").write_text(LESSON, encoding="utf-8")
        (lessons / "002-beta.md").write_text(SECOND, encoding="utf-8")
        for slug in ("001-alpha", "002-beta"):
            exercise = self.root / "content" / "exercises" / slug
            exercise.mkdir(parents=True)
            (exercise / "meta.json").write_text(
                json.dumps({"id": slug, "title": slug, "brief": "Add two numbers.", "hints": ["Use +."], "timeout": 30}),
                encoding="utf-8",
            )
            (exercise / "starter.py").write_text("def add(a, b):\n    raise NotImplementedError\n")
            (exercise / "solution.py").write_text("def add(a, b):\n    return a + b\n")
            (exercise / "tests.py").write_text(TESTS)
        self._env = {
            "DATA_DIR": str(self.root / "data"),
            "CONTENT_DIR": str(self.root / "content"),
            "FRONTEND_DIST": str(self.root / "missing-dist"),
            "SSO_PROXY_SECRET": SECRET,
            "SSO_USERS": "portal:reader",
        }
        os.environ.update(self._env)
        from fastapi.testclient import TestClient
        from backend.app import curriculum, db
        from backend.app.config import get_settings
        from backend.app.main import app

        self.get_settings = get_settings
        self.curriculum = curriculum
        self.db = db
        get_settings.cache_clear()
        curriculum.reload_content()
        # Entering the client runs the lifespan, which starts the MCP session manager.
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        for key in self._env:
            os.environ.pop(key, None)
        os.environ.pop("MCP_PUBLIC_URL", None)
        self.get_settings.cache_clear()
        self.curriculum.reload_content()
        self._dir.cleanup()

    # Helpers ------------------------------------------------------------

    def _new_token(self, name: str = "laptop", headers: dict | None = None) -> dict:
        response = self.client.post(
            "/api/mcp/tokens", json={"name": name}, headers=headers or SIGNED_IN
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _rpc(self, token: str | None, method: str, params: dict | None = None,
             path: str = "/mcp", extra: dict | None = None):
        headers = {"Accept": ACCEPT, "Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        headers.update(extra or {})
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        return self.client.post(path, headers=headers, json=body, follow_redirects=False)

    def _call(self, token: str, tool: str, **arguments):
        response = self._rpc(token, "tools/call", {"name": tool, "arguments": arguments})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        text = result["content"][0]["text"]
        return result.get("isError", False), (text if result.get("isError") else json.loads(text))

    # Token management ---------------------------------------------------

    def test_token_api_needs_sso(self) -> None:
        self.assertEqual(self.client.get("/api/mcp/tokens").status_code, 401)
        self.assertEqual(self.client.post("/api/mcp/tokens", json={"name": "x"}).status_code, 401)
        self.assertEqual(self.client.delete("/api/mcp/tokens/1").status_code, 401)

    def test_create_list_and_revoke(self) -> None:
        listed = self.client.get("/api/mcp/tokens", headers=SIGNED_IN).json()
        self.assertEqual(listed, {"url": "http://testserver/mcp", "tokens": []})

        created = self._new_token()
        self.assertEqual(set(created), {"id", "name", "prefix", "created_at", "token"})
        self.assertTrue(created["token"].startswith("osmcp_"))
        self.assertEqual(created["prefix"], created["token"][:12])
        self.assertEqual(created["name"], "laptop")

        tokens = self.client.get("/api/mcp/tokens", headers=SIGNED_IN).json()["tokens"]
        self.assertEqual(
            tokens,
            [
                {
                    "id": created["id"],
                    "name": "laptop",
                    "prefix": created["prefix"],
                    "created_at": created["created_at"],
                    "last_used_at": None,
                }
            ],
        )
        # The secret itself is never stored, only its hash.
        with self.db.session() as connection:
            row = dict(connection.execute("SELECT * FROM mcp_tokens").fetchone())
        self.assertNotIn(created["token"], json.dumps(row))
        self.assertEqual(row["username"], "reader")  # after SSO_USERS mapping
        self.assertEqual(len(row["token_hash"]), 64)

        # Another reader neither sees nor revokes it.
        self.assertEqual(self.client.get("/api/mcp/tokens", headers=OTHER).json()["tokens"], [])
        response = self.client.delete(f"/api/mcp/tokens/{created['id']}", headers=OTHER)
        self.assertEqual(response.status_code, 404)

        response = self.client.delete(f"/api/mcp/tokens/{created['id']}", headers=SIGNED_IN)
        self.assertEqual(response.json(), {"revoked": True})
        self.assertEqual(self.client.get("/api/mcp/tokens", headers=SIGNED_IN).json()["tokens"], [])
        response = self.client.delete(f"/api/mcp/tokens/{created['id']}", headers=SIGNED_IN)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self._rpc(created["token"], "ping").status_code, 401)

    def test_public_url_setting(self) -> None:
        os.environ["MCP_PUBLIC_URL"] = "https://os.ifkash.dev/mcp"
        self.get_settings.cache_clear()
        listed = self.client.get("/api/mcp/tokens", headers=SIGNED_IN).json()
        self.assertEqual(listed["url"], "https://os.ifkash.dev/mcp")

    def test_name_is_validated(self) -> None:
        for name in ("", "   ", "x" * 65):
            response = self.client.post(
                "/api/mcp/tokens", json={"name": name}, headers=SIGNED_IN
            )
            self.assertEqual(response.status_code, 422, name)

    def test_at_most_ten_active_tokens(self) -> None:
        for i in range(10):
            self._new_token(f"t{i}")
        response = self.client.post("/api/mcp/tokens", json={"name": "t10"}, headers=SIGNED_IN)
        self.assertEqual(response.status_code, 409)

    def test_cli_creates_lists_and_revokes(self) -> None:
        from backend.app import mcp_tokens

        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(mcp_tokens.main(["create", "reader", "--name", "vm"]), 0)
        token = out.getvalue().strip().splitlines()[-1]
        self.assertTrue(token.startswith("osmcp_"))
        self.assertEqual(self._rpc(token, "ping").status_code, 200)

        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(mcp_tokens.main(["list", "reader"]), 0)
        self.assertIn(token[:12], out.getvalue())
        self.assertNotIn(token, out.getvalue())

        token_id = self.db.list_tokens("reader")[0]["id"]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(mcp_tokens.main(["revoke", str(token_id)]), 0)
        self.assertEqual(self._rpc(token, "ping").status_code, 401)

    # Authentication on /mcp ---------------------------------------------

    def test_mcp_rejects_missing_and_bad_tokens(self) -> None:
        response = self._rpc(None, "ping")
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.headers["www-authenticate"].startswith("Bearer"))

        response = self._rpc("osmcp_not-a-real-token", "ping")
        self.assertEqual(response.status_code, 401)
        self.assertIn('error="invalid_token"', response.headers["www-authenticate"])

        response = self._rpc(None, "ping", extra={"Authorization": "Basic cmVhZGVyOng="})
        self.assertEqual(response.status_code, 401)

    def test_mcp_ignores_sso_headers(self) -> None:
        response = self._rpc(None, "ping", extra=SIGNED_IN)
        self.assertEqual(response.status_code, 401)

        # With a valid token, SSO headers can't change who the caller is.
        token = self._new_token(headers=OTHER)["token"]
        _, progress = self._call_with(token, SIGNED_IN, "get_progress")
        self.assertEqual(progress["reader"], "other")

    def test_hub_secret_acts_as_the_named_reader(self) -> None:
        hub = {"X-MCP-Hub-Secret": "hub-secret", "X-MCP-Hub-User": "Portal"}

        # Off by default: without MCP_HUB_SECRET the headers grant nothing.
        self.assertEqual(self._rpc(None, "ping", extra=hub).status_code, 401)

        os.environ["MCP_HUB_SECRET"] = "hub-secret"
        self.get_settings.cache_clear()
        try:
            wrong = {**hub, "X-MCP-Hub-Secret": "guess"}
            self.assertEqual(self._rpc(None, "ping", extra=wrong).status_code, 401)
            no_user = {"X-MCP-Hub-Secret": "hub-secret"}
            self.assertEqual(self._rpc(None, "ping", extra=no_user).status_code, 401)

            response = self._rpc(
                None, "tools/call", {"name": "get_progress", "arguments": {}}, extra=hub
            )
            self.assertEqual(response.status_code, 200, response.text)
            progress = json.loads(response.json()["result"]["content"][0]["text"])
            # The Authelia name maps through SSO_USERS, as a browser session does.
            self.assertEqual(progress["reader"], "reader")
        finally:
            os.environ.pop("MCP_HUB_SECRET", None)
            self.get_settings.cache_clear()

    def _call_with(self, token: str, headers: dict, tool: str, **arguments):
        response = self._rpc(
            token, "tools/call", {"name": tool, "arguments": arguments}, extra=headers
        )
        result = response.json()["result"]
        return result.get("isError", False), json.loads(result["content"][0]["text"])

    # The protocol and the tools -----------------------------------------

    def test_initialize_and_list_tools(self) -> None:
        token = self._new_token()["token"]
        for path in ("/mcp", "/mcp/"):
            response = self._rpc(
                token,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
                path=path,
            )
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()["result"]
            self.assertEqual(result["protocolVersion"], "2025-06-18")
            self.assertIn("tools", result["capabilities"])

        response = self.client.post(
            "/mcp",
            headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        self.assertEqual(response.status_code, 202)

        tools = {tool["name"] for tool in self._rpc(token, "tools/list").json()["result"]["tools"]}
        self.assertTrue(
            {
                "course_overview", "list_lessons", "get_lesson", "search", "list_exercises",
                "get_exercise", "get_solution", "get_document", "get_progress", "get_draft",
                "save_draft", "reset_draft", "set_progress", "get_runner_info",
                "run_exercise",
            }
            <= tools
        )
        templates = self._rpc(token, "resources/templates/list").json()["result"]
        self.assertIn(
            "os://lessons/{slug}", [t["uriTemplate"] for t in templates["resourceTemplates"]]
        )

    def test_last_used_is_recorded(self) -> None:
        token = self._new_token()["token"]
        self.assertEqual(self._rpc(token, "ping").status_code, 200)
        tokens = self.client.get("/api/mcp/tokens", headers=SIGNED_IN).json()["tokens"]
        self.assertIsNotNone(tokens[0]["last_used_at"])

    def test_get_lesson_does_not_mark_progress(self) -> None:
        token = self._new_token()["token"]
        error, lesson = self._call(token, "get_lesson", slug="001-alpha")
        self.assertFalse(error)
        self.assertIn("running program", lesson["body"])
        self.assertEqual(lesson["next"], "002-beta")
        self.assertEqual(lesson["exercise"], "001-alpha")
        self.assertIsNone(lesson["status"])
        self.assertEqual(self.db.get_progress("reader"), {})

        error, message = self._call(token, "get_lesson", slug="nope")
        self.assertTrue(error)
        self.assertIn("No lesson", message)

        response = self._rpc(token, "resources/read", {"uri": "os://lessons/002-beta"})
        self.assertIn("handler", response.json()["result"]["contents"][0]["text"])

    def test_search(self) -> None:
        token = self._new_token()["token"]
        error, found = self._call(token, "search", query="ZOMBIE state")
        self.assertFalse(error)
        lessons = [r for r in found["results"] if r["kind"] == "lesson"]
        self.assertEqual([r["slug"] for r in lessons], ["001-alpha"])
        hit = lessons[0]
        self.assertEqual(hit["section"], "The zombie state")
        self.assertIn("zombie", hit["snippet"].lower())

        # A Python comment in a code block is not a section heading.
        _, found = self._call(token, "search", query="reap the child")
        self.assertEqual(found["results"][0]["section"], "The zombie state")

        _, found = self._call(token, "search", query="kernel", limit=1)
        self.assertGreaterEqual(found["total"], 2)
        self.assertEqual(len(found["results"]), 1)

        # Exercises are searched by brief and hints.
        _, found = self._call(token, "search", query="Add two numbers")
        self.assertEqual(
            {(r["kind"], r["slug"]) for r in found["results"]},
            {("exercise", "001-alpha"), ("exercise", "002-beta")},
        )

    def test_overview_exercise_and_documents(self) -> None:
        token = self._new_token()["token"]
        _, overview = self._call(token, "course_overview")
        self.assertEqual(overview["reader"], "reader")
        self.assertEqual(overview["counts"], {"parts": 2, "lessons": 2, "exercises": 2})
        self.assertEqual(overview["parts"][0]["lessons"][0]["slug"], "001-alpha")

        _, exercise = self._call(token, "get_exercise", exercise_id="001-alpha")
        self.assertIn("NotImplementedError", exercise["starter"])
        self.assertIn("@check", exercise["tests"])
        self.assertNotIn("solution", exercise)
        self.assertEqual(exercise["lessons"], ["001-alpha"])
        _, solution = self._call(token, "get_solution", exercise_id="001-alpha")
        self.assertIn("return a + b", solution["solution"])

        _, document = self._call(token, "get_document", name="curriculum")
        self.assertEqual(document["name"], "CURRICULUM.md")
        error, _ = self._call(token, "get_document", name="../README")
        self.assertTrue(error)

    def test_drafts_progress_and_runs_act_as_the_token_owner(self) -> None:
        token = self._new_token()["token"]
        _, saved = self._call(token, "save_draft", exercise_id="001-alpha", code="x = 1\n")
        self.assertTrue(saved["saved"])
        self.assertEqual(self.db.get_draft("reader", "001-alpha"), "x = 1\n")
        _, draft = self._call(token, "get_draft", exercise_id="001-alpha")
        self.assertEqual(draft["code"], "x = 1\n")

        _, marked = self._call(token, "set_progress", slug="002-beta", status="started")
        self.assertEqual(marked["status"], "started")

        code = "def add(a, b):\n    print('adding')\n    return a + b\n"
        error, result = self._call(token, "run_exercise", exercise_id="001-alpha", code=code)
        self.assertFalse(error, result)
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["passed"], result["total"]), (1, 1))
        self.assertEqual(result["checks"][0]["status"], "passed")
        self.assertEqual(result["lessons_solved"], ["001-alpha"])
        self.assertEqual(self.db.get_progress("reader")["001-alpha"]["status"], "solved")
        self.assertEqual(self.db.get_draft("reader", "001-alpha"), code)

        _, progress = self._call(token, "get_progress")
        self.assertEqual(progress["summary"]["done"], 1)
        self.assertEqual(progress["runs"][0]["exercise_id"], "001-alpha")
        self.assertEqual(
            [(row["slug"], row["status"]) for row in progress["lessons"]],
            [("001-alpha", "solved"), ("002-beta", "started")],
        )

        error, result = self._call(
            token, "run_exercise", exercise_id="002-beta", code="print('hi')\n", mode="run"
        )
        self.assertFalse(error, result)
        self.assertIn("hi", result["stdout"])
        self.assertEqual(self.db.get_progress("reader")["002-beta"]["status"], "started")

    def test_lists_exercises_runner_and_resources(self) -> None:
        token = self._new_token()["token"]
        _, lessons = self._call(token, "list_lessons", part="part 2")
        self.assertEqual([entry["slug"] for entry in lessons["lessons"]], ["002-beta"])
        # The Python comment in the code block is not a heading.
        _, lessons = self._call(token, "list_lessons")
        self.assertEqual(lessons["lessons"][0]["headings"], ["The zombie state"])

        _, listed = self._call(token, "list_exercises")
        self.assertEqual([e["id"] for e in listed["exercises"]], ["001-alpha", "002-beta"])
        self.assertEqual(listed["exercises"][0]["lessons"], ["001-alpha"])
        self.assertFalse(listed["exercises"][0]["has_draft"])
        self.assertNotIn("solution", json.dumps(listed))

        _, runner = self._call(token, "get_runner_info")
        self.assertEqual(runner["backend"], "local")
        self.assertEqual(runner["exercises"], 2)

        response = self._rpc(token, "resources/read", {"uri": "os://exercises/001-alpha"})
        text = response.json()["result"]["contents"][0]["text"]
        self.assertIn("Add two numbers.", text)
        self.assertIn("NotImplementedError", text)
        self.assertNotIn("return a + b", text)
        templates = self._rpc(token, "resources/templates/list").json()["result"]
        self.assertEqual(
            {t["uriTemplate"] for t in templates["resourceTemplates"]},
            {"os://lessons/{slug}", "os://exercises/{exercise_id}"},
        )

    def test_reset_draft(self) -> None:
        token = self._new_token()["token"]
        self._call(token, "save_draft", exercise_id="001-alpha", code="x = 1\n")
        _, listed = self._call(token, "list_exercises")
        self.assertTrue(listed["exercises"][0]["has_draft"])
        _, reset = self._call(token, "reset_draft", exercise_id="001-alpha")
        self.assertFalse(reset["saved"])
        self.assertIsNone(self.db.get_draft("reader", "001-alpha"))
        error, _ = self._call(token, "reset_draft", exercise_id="nope")
        self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()
