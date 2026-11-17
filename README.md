# Operating Systems

A hands-on operating systems course, from zero. Twenty-six lessons take a reader
who has never studied how a computer works to the point where they can explain,
and build small working models of, processes, scheduling, virtual memory,
concurrency, storage, file systems, and isolation.

The app is a reader on the left, a code editor on the right, a Run button, and a
Check button. Every lesson ends in a Python exercise; Check runs the reader's
code against tests that say exactly what is right and what is not. Some
exercises are simulators (a scheduler, a page table, a file system on a
`bytearray` disk). Others call the real Linux kernel through Python's `os`
module: `fork`, `exec`, `wait`, `pipe`, `dup2`, signals, and file descriptors.

## Who it is for

Anyone who can read a little code and is curious how a computer works. No
operating systems background is assumed, and Part 0 teaches the Python the
course needs. Exercises use only the Python standard library.

## Layout

| Path | What is there |
| --- | --- |
| `backend/app/` | FastAPI app: content loader, auth, progress database, local runner, MCP server |
| `backend/tests/` | Unit tests for the MCP server and its tokens |
| `backend/app/runner/` | `local.py` runs a submission in a limited subprocess; `harness.py` and `oscheck.py` run and check it |
| `frontend/` | React and Vite single-page app (reader, editor, check console) |
| `content/lessons/` | One Markdown file per lesson, with YAML front matter |
| `content/exercises/` | One directory per exercise: `meta.json`, `starter.py`, `solution.py`, `tests.py` |
| `docs/` | `CONTENT_CONTRACT.md` (the content format) and `CURRICULUM.md` (the plan) |
| `scripts/` | `check_content.py` validates content, `check_math.mjs` compiles lesson math, `deploy.sh` redeploys |
| `Dockerfile`, `docker-compose.yml` | The single container that serves the API and the built frontend |
| `Caddyfile.example` | The reverse proxy block for the deployment |

## The curriculum

0. **Getting started**: the Python you need; how a computer runs a program (a toy
   CPU); bits, bytes, and memory.
1. **What an operating system is**: what an OS does (time-slicing and
   interrupts); kernel mode and system calls.
2. **Processes**: the process table; `fork`, `exec`, and `wait`; pipes and a tiny
   shell; signals.
3. **CPU scheduling**: FCFS, SJF, and SRTF; round robin and the MLFQ;
   lottery, stride, and CFS.
4. **Memory**: address spaces and segmentation; paging; TLBs; page replacement;
   heap allocation.
5. **Concurrency**: threads and race conditions; locks; condition variables and
   semaphores; deadlock.
6. **Storage and file systems**: disks and I/O; files and directories; building
   a file system; crash consistency and journaling.
7. **Isolation**: protection, virtual machines, and containers.

The full lesson list with exercise sketches is in `docs/CURRICULUM.md`.

## Run it locally

You need Python 3.12 and Node 22. The runner uses `os.fork`, signals, and
`sh`, so run on Linux or macOS.

```sh
uv venv --python 3.12 .venv && . .venv/bin/activate
uv pip install -r backend/requirements.txt pyyaml

cd frontend && npm ci && npm run build && cd ..
```

Authentication is by headers from a trusted proxy, so for local use set a secret
and send the headers yourself, or put the app behind any proxy that does:

```sh
export SSO_PROXY_SECRET=dev-secret
uvicorn backend.app.main:app --reload
curl -H 'X-SSO-Proxy: dev-secret' -H 'Remote-User: me' localhost:8000/api/lessons
```

For frontend work, `npm run dev` in `frontend/` serves the UI on port 5173 and
proxies `/api` to port 8000. A browser extension that adds the two headers makes
the dev server usable.

To validate content: `python3 scripts/check_content.py`, and
`node scripts/check_math.mjs` after `npm ci` in `frontend/`. To run the backend
tests: `python -m unittest discover -s backend/tests -t .`.

## How a run works

`POST /api/run` copies the reader's code and the exercise's `tests.py` into a
scratch directory and starts `harness.py` as a separate process in its own
process group, under CPU-time, file-size, and process-count limits (so `fork`
works, and a fork bomb does not). Output streams back as server-sent events.
When the wall clock runs out the whole group is killed. This is a resource
boundary, not a security boundary: the app is for signed-in readers only.

## Authentication

There is no login form. Caddy forwards every request through Authelia and, on
success, sets `Remote-User` and `X-SSO-Proxy`. The app trusts `Remote-User` only
when `X-SSO-Proxy` equals `SSO_PROXY_SECRET`. `SSO_USERS` (`portal:progress`
pairs, comma separated) maps portal usernames to progress identities. The one
exception is `/mcp`, which takes a bearer token instead. See the next section.

## MCP server for AI agents

The app serves a [Model Context Protocol](https://modelcontextprotocol.io)
server at `https://os.ifkash.dev/mcp`, over the Streamable HTTP transport. An
agent such as Claude Code can use it to read the course and work through it as
you.

The server exposes the following tools:

- `course_overview`, `list_lessons`, `get_lesson`, and `search` for the
  syllabus, lesson text, and full-text search over lessons and exercises.
- `list_exercises`, `get_exercise`, and `get_solution` for an exercise's brief,
  hints, starter code, checks, and worked solution.
- `get_document` for `docs/CURRICULUM.md` and `docs/CONTENT_CONTRACT.md`.
- `get_progress`, `get_draft`, `save_draft`, `reset_draft`, and `set_progress`
  for your progress and drafts.
- `get_runner_info` for the runner's limits and the server's build.
- `run_exercise`, which runs or checks code the same way the editor's **Run**
  and **Check** buttons do.

Lessons and exercises are also resources, at `os://lessons/SLUG` and
`os://exercises/EXERCISE_ID`. Reading a lesson through the server doesn't mark it
started.

An agent can't complete the Authelia sign-in, so Caddy routes `/mcp` without
`forward_auth`, and the server requires a bearer token instead. A token acts
as the reader who owns it. The server ignores the `Remote-User` and `X-SSO-Proxy`
headers.

**Caution:** A token can run code in the container, the same as a signed-in
reader. Treat it like a password, and revoke it when you no longer use it.

### Get a token

To create a token, do one of the following:

- On the site, open **Agent access** in the account menu, at
  `https://os.ifkash.dev/agents`. Enter a name and click **Create token**. The
  page shows the token once, with ready-to-copy client configurations.
- On the VM, run the command line in the container:

  ```bash
  docker exec os python -m backend.app.mcp_tokens create USERNAME --name NAME
  ```

  Replace the following:

  - `USERNAME`: the reader the token acts as, after `SSO_USERS` mapping, for
    example `ifkash`.
  - `NAME`: a label that tells you where the token is used, for example
    `laptop`.

To see or revoke tokens on the VM, run
`docker exec os python -m backend.app.mcp_tokens list` or
`docker exec os python -m backend.app.mcp_tokens revoke ID`. The server stores
only a SHA-256 hash of each token, so a lost token can't be recovered; revoke
it and create another.

### Connect a client

To connect Claude Code, complete the following steps:

1. Put the token in an environment variable:

   ```bash
   export TOKEN=TOKEN_VALUE
   ```

   Replace `TOKEN_VALUE` with the token, which starts with `osmcp_`.

2. Add the server:

   ```bash
   claude mcp add --transport http os https://os.ifkash.dev/mcp \
     --header "Authorization: Bearer $TOKEN"
   ```

For a client that reads an `mcpServers` configuration file, add the following
entry:

```json
{
  "mcpServers": {
    "os": {
      "type": "http",
      "url": "https://os.ifkash.dev/mcp",
      "headers": {
        "Authorization": "Bearer TOKEN_VALUE"
      }
    }
  }
}
```

The server is stateless and answers with plain JSON, so it needs no session
and works through a proxy that buffers responses. A `run_exercise` call returns
when the run finishes, which can take up to the exercise's timeout.

## Deploy

The app is one container (`docker-compose.yml`, project `os`, container `os`),
joined to the external `edge` network and published only on
`127.0.0.1:8098`. Caddy terminates TLS for `os.ifkash.dev` and proxies
`os:8000`, behind Authelia forward auth, and sends `X-SSO-Proxy`, except on
`/mcp`, which skips forward auth. See
`Caddyfile.example`. Copy `.env.example` to `.env`, fill it in, then:

```sh
./scripts/deploy.sh     # git pull, then docker compose up -d --build
```

Progress lives in the `os-data` volume.

## Licence

See `LICENSE`.
