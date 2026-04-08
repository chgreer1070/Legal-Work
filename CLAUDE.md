# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## Project Overview

**Outlook-to-PDF Converter** — a single-process Flask web app that accepts `.msg`, `.pdf`, `.doc/.docx`, and `.ppt/.pptx` files via drag-and-drop and returns a downloadable ZIP of converted PDFs. A second page embeds a Tableau P&L dashboard.

All file processing happens locally on the server; nothing is sent to external services (except for the Tableau iframe on `/dashboard`).

## Repository Layout

```
.
├── app.py               # Flask app: routes, job queue, zip download
├── converter.py         # All conversion logic (.msg / office / pdf → PDF)
├── requirements.txt     # Python dependencies (pinned minimums)
├── run.sh               # Entry script: mkdir uploads/output, python3 app.py
├── .gitignore           # Ignores uploads/, output/, venvs, pycache
├── templates/
│   ├── index.html       # Drag-and-drop converter UI
│   └── dashboard.html   # Tableau P&L embed page
└── static/
    ├── css/style.css    # App styles (CSS variables, flex layout)
    └── js/app.js        # Front-end: upload, polling, job cards
```

Runtime directories (gitignored, created on startup by `run.sh` and `app.py`):

- `uploads/<job_id>/` — temporary upload staging, deleted after conversion
- `output/<job_id>/` — converted PDFs, served as zip via `/download/<job_id>`
- `output/<job_id>.zip` — generated on-demand when the user downloads

## Architecture

### Request flow

1. Browser `POST /convert` with a `multipart/form-data` payload of files.
2. `app.py` filters by `ALLOWED_EXT`, saves files to `uploads/<job_id>/`, registers the job in the in-memory `_jobs` dict under `_jobs_lock`, and kicks off a daemon `threading.Thread` running `_run_conversion`.
3. The worker thread:
   - Processes `.msg` files first (so attachments land alongside the email), then other documents.
   - Each `.msg` gets its own sub-folder named after a 50-char slug of the filename stem; attachments go into `<email_dir>/attachments/`.
   - Updates `_jobs[job_id]` with `results` and `errors` when done; final status is `done` or `done_with_errors`.
4. Front-end polls `GET /status/<job_id>` every 1.5s (`static/js/app.js:131`) until status is not `processing`.
5. `GET /download/<job_id>` zips `output/<job_id>/` on the fly and streams it back.

### Routes (`app.py`)

| Method | Path                | Purpose                                        |
|--------|---------------------|------------------------------------------------|
| GET    | `/`                 | Converter UI (`templates/index.html`)          |
| GET    | `/dashboard`        | Tableau P&L embed (`templates/dashboard.html`) |
| POST   | `/convert`          | Accept files, create job, spawn worker thread  |
| GET    | `/status/<job_id>`  | Return job state JSON                          |
| GET    | `/download/<job_id>`| Stream a zip of the job's output directory    |
| GET    | `/jobs`             | List all jobs (in-memory snapshot)             |

### Concurrency & state

- Jobs are tracked in `_jobs: dict[str, dict]` guarded by `_jobs_lock` (`app.py:41`).
- Every mutation or snapshot of `_jobs` must hold `_jobs_lock`.
- **State is in-memory only** — restarting the process drops all job history. There is no database, Celery, or Redis; if persistence or multi-worker support is added, that will also need to change the lock strategy.
- `app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024` caps uploads at 200 MB.

### Conversion strategy (`converter.py`)

The module is organized into sections marked with `# ── label ──` comment banners. Respect the existing section layout when adding code.

| Input  | Primary path                          | Fallback              |
|--------|---------------------------------------|-----------------------|
| `.msg` | `extract_msg` + `reportlab` cover PDF | —                     |
| `.pdf` | `pypdf` metadata stamping + copy      | plain `shutil.copy2`  |
| `.docx`| `mammoth` → HTML → `weasyprint`       | `libreoffice --headless` |
| `.doc` | `libreoffice --headless`              | —                     |
| `.pptx`| `python-pptx` text → `reportlab`      | `libreoffice --headless` |
| `.ppt` | `libreoffice --headless`              | —                     |

Key entry points:

- `msg_to_pdf(msg_path, output_dir)` — returns `{"email_pdf", "attachments", "metadata"}`. Builds a cover page (title, From/To/CC/Date table, rendered body) via ReportLab, then stamps PDF metadata via `_stamp_pdf_metadata`. Extracts each attachment into `output_dir/attachments/` and recursively converts supported ones.
- `convert_office_to_pdf(src, output_dir, meta)` — dispatches to the right per-format converter, falling back to LibreOffice.
- `convert_standalone(src, output_dir)` — used by the web handler for non-email uploads.
- `_stamp_pdf_metadata(src, dest, meta)` — writes `/Title`, `/Author`, `/Subject`, `/Creator`, `/CreationDate`, and packs email fields (`from`, `to`, `cc`, `date_str`) into `/Keywords`. Falls back to a plain copy if pypdf fails.
- `_sanitize_filename(name, max_len=80)` — strips FS-invalid chars and caps length; use this whenever deriving a filename from user-controlled input (subject line, attachment name, etc.).

LibreOffice is optional — the code calls it via `subprocess.run` and catches `FileNotFoundError`, so the app still works without it for `.docx`/`.pptx` (pure-Python path), just not `.doc`/`.ppt`.

## Development Workflow

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`weasyprint` requires system libraries (`libcairo2`, `libpango-1.0-0`, `libpangoft2-1.0-0`, `libgdk-pixbuf2.0-0`); install via the OS package manager if `pip install` fails.

LibreOffice is optional but recommended for `.doc`/`.ppt` support:

```bash
sudo apt-get install libreoffice      # Debian/Ubuntu
```

### Run

```bash
./run.sh
# or: python3 app.py
```

Serves on `http://0.0.0.0:5000`. Debug mode is **off** by default (`app.py:228`); enable it temporarily for local dev only.

### Testing

There is currently no test suite. When adding tests, place them under a top-level `tests/` directory and use `pytest`. For manual verification:

- Drop a `.msg` file with attachments → verify `output/<job_id>/<slug>/` contains `*_email.pdf` and `attachments/*.pdf`.
- Drop a `.docx` → verify `output/<job_id>/<name>.pdf` renders with readable text and headings.
- `GET /download/<job_id>` should return a valid zip.

### Linting

No formatter/linter is configured. Match the existing style:

- 4-space indentation, double-quoted strings, type hints on public functions.
- Section banners (`# ── label ──`) to separate logical groups.
- Column-aligned assignment in dict/variable blocks where it aids readability (e.g., `msg_to_pdf` meta dict, ParagraphStyle definitions).

## Conventions

### Python

- **Imports** are grouped stdlib → third-party → local, alphabetized within each group.
- **Paths**: always use `pathlib.Path`, not string concatenation. New files should follow this.
- **Error handling** in converter functions: return `None` on failure rather than raising, so `_run_conversion` can record a per-file error without aborting the batch. Catching bare `Exception` is intentional here — the goal is to isolate one file's failure from the rest of the job.
- **Metadata dicts** use the keys: `title`, `author`, `subject`, `creator`, `date` (PDF `D:YYYYMMDDHHMMSS` form), `from`, `to`, `cc`, `date_str`. Extend this dict rather than inventing parallel structures.
- **Filename safety**: route every user-derived filename through `_sanitize_filename` before writing to disk.

### Front-end

- Plain JavaScript, no build step. `static/js/app.js` uses `'use strict'` and top-level module globals (`fileMap`, `jobTimers`).
- All user-supplied strings rendered into the DOM go through `escHtml` (`static/js/app.js:247`). Never interpolate raw values into `innerHTML`.
- The allowed extension list lives in two places that must stay in sync:
  - Python: `ALLOWED_EXT` in `app.py:38`
  - JavaScript: `ALLOWED` in `static/js/app.js:44` (plus the `accept=` attribute in `templates/index.html:47`)

### CSS

- CSS custom properties (variables) live in `:root` at the top of `static/css/style.css`. Use them (e.g. `var(--blue)`) rather than hardcoding hex values.
- Layout is flexbox-based; the app header content is capped at `max-width: 860px` except on the dashboard page which overrides to `1960px` inline.

### HTML templates

- Use `{{ url_for(...) }}` for all static assets and route links — never hardcode paths.
- Both pages share the same header/footer markup. If you change the header in one, update the other.

## Security Notes

- Uploads are validated by extension only (no content sniffing). Do not expose this app to the public internet without further hardening (auth, content-type checks, resource limits, sandboxing LibreOffice).
- The `/download/<job_id>` endpoint only serves files under `output/<job_id>/` keyed by UUID, so there is no path traversal surface, but anyone who knows a job ID can download its output. If multi-tenancy is introduced, add auth.
- Uploaded files are deleted from `uploads/<job_id>/` after conversion (`app.py:107`), but `output/<job_id>/` persists until the process restarts. Add a cleanup policy if disk usage becomes a concern.
- `dashboard.html` embeds a third-party Tableau script and iframe from `insightexec.flex.com`. This is the only outbound network call from the UI.

## Branching

Development for AI-assisted changes happens on feature branches named `claude/<description>-<suffix>`. Existing branches:

- `claude/add-claude-documentation-yOr3G`
- `claude/outlook-to-pdf-converter-q4Yr5`

Always commit to the branch specified in the task instructions; never push directly to `main`.

## Common Tasks

### Adding a new input format

1. Add the extension to `ALLOWED_EXT` in `app.py:38`.
2. Add it to `ALLOWED` in `static/js/app.js:44` and the `accept=` attribute in `templates/index.html:47`.
3. Add a handler in `converter.py` following the `_docx_to_pdf` / `_pptx_to_pdf` pattern (return `Optional[Path]`, stamp metadata, fall back gracefully).
4. Wire it into `convert_office_to_pdf` (for attachment-style usage) and/or `convert_standalone` (for top-level uploads).

### Adding a new route

1. Define the handler in `app.py` alongside the existing routes.
2. If it renders HTML, add a template in `templates/` that extends the shared header/footer markup.
3. Add a nav link in both `templates/index.html` and `templates/dashboard.html` (they don't share a base template yet).

### Changing job state shape

Any field added to `_jobs[job_id]` must be handled by both `GET /status/<job_id>` (just returns the dict) and the front-end `updateJobCard` function in `static/js/app.js:156`.
