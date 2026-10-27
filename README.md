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
| `backend/app/` | FastAPI app: content loader, auth, progress database, local runner |
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
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt pyyaml

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
`node scripts/check_math.mjs` after `npm ci` in `frontend/`.

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
pairs, comma separated) maps portal usernames to progress identities.

## Deploy

The app is one container (`docker-compose.yml`, project `os`, container `os`),
joined to the external `edge` network and published only on
`127.0.0.1:8098`. Caddy terminates TLS for `os.ifkash.dev` and proxies
`os:8000`, behind Authelia forward auth, and sends `X-SSO-Proxy`. See
`Caddyfile.example`. Copy `.env.example` to `.env`, fill it in, then:

```sh
./scripts/deploy.sh     # git pull, then docker compose up -d --build
```

Progress lives in the `os-data` volume.

## Licence

See `LICENSE`.
