# Legal-Work

Flask web application with two loosely-coupled subsystems that share one `app.py`.

## Project overview

### Subsystem 1 — Outlook-to-PDF converter
The original product. Drag-and-drop `.msg` / `.docx` / `.pdf` / `.ppt` files, get back a zip of PDFs. All work happens in a background thread.

- **Routes:** `/`, `/convert`, `/status/<job_id>`, `/download/<job_id>`, `/jobs`, `/dashboard`
- **Entry module:** `converter.py` — `msg_to_pdf()` and `convert_standalone()`
- **Heavy dependencies:** `extract_msg`, `mammoth`, `weasyprint`, `reportlab`, `pypdf`, `python-docx`, `python-pptx`, `pillow`, `beautifulsoup4`, `olefile`, `compressed-rtf`, `tzlocal`, `RTFDE`, `red-black-tree-mod`
- **Requirements file:** `requirements-converter.txt`

### Subsystem 2 — ContractTwin 3D
EMS contract intelligence engine. Parses contract text into clauses, builds a dependency graph, computes probabilistic economics, runs scenario simulations, and serves a Three.js-rendered 3D visualization.

- **Routes:** `/contracttwin`, `/contracttwin/demo`, `/contracttwin/parse`, `/contracttwin/scenarios/<id>`
- **Dependencies:** `flask`, `mammoth` only
- **Requirements file:** `requirements-contracttwin.txt`

## Module map

| File | Role |
|---|---|
| `app.py` | Flask routes for both subsystems |
| `converter.py` | Outlook/Office to PDF conversion |
| `ems_ontology.py` | 25 EMS clause families, 6 zones, dependency rules, recommendation templates |
| `contract_parser.py` | Regex clause splitting + obligation/actor/trigger extraction |
| `plain_english.py` | Clause-to-plain-English translation with role views |
| `graph_builder.py` | Builds clause dependency graph from ontology rules |
| `economics_engine.py` | Clause economics, Monte Carlo, portfolio summary, recommendations |
| `scenario_engine.py` | Named scenario simulations (forecast collapse, quality failure, etc.) |
| `demo_contract.py` | Sample 27-clause EMS MSA for the demo endpoint |
| `templates/contracttwin.html` | ContractTwin 3D page shell |
| `static/js/contracttwin.js` | Three.js scene, controls, scenario playback |
| `static/css/contracttwin.css` | Dark theme for ContractTwin |

## Running locally

```bash
./run.sh
```

Creates `uploads/` and `output/`, then starts Flask on `http://localhost:5000`.

## Sandbox pip quirk

**Important:** In this sandbox, packages were installed via the system package manager, so plain `pip install` fails with a `blinker` RECORD error. Always use:

```bash
pip install --break-system-packages --ignore-installed <pkg>
```

## SessionStart hook

`.claude/hooks/session-start.sh` runs automatically at the start of every remote Claude Code session. It:

1. Installs ContractTwin deps from `requirements-contracttwin.txt`
2. Best-effort installs converter deps from `requirements-converter.txt` (wheel-only; some packages may not be available)
3. Exports `FLASK_APP=app.py`

The hook is registered in `.claude/settings.json` and only activates when `CLAUDE_CODE_REMOTE=true`.

## Smoke testing

Run the `/smoketest` slash command to execute end-to-end verification via Flask `test_client`. It asserts:

- `/contracttwin/demo` returns 200 with ~27 clauses and a `risk_adjusted_margin` between 0.03 and 0.15 (calibration sanity)
- `/contracttwin` page contains the expected DOM hooks (`twinCanvas`, `contractFile`, `statCeiling`)
- `/contracttwin/parse` accepts JSON body, `.txt` multipart upload, and `.docx` multipart upload
- `/contracttwin/parse` rejects `.pdf` with 400
- `/contracttwin/scenarios/forecast_collapse` returns activations and a positive `total_ev`

## Sandbox limitations

- **No browser.** Three.js visual verification is out of scope — rely on Flask `test_client` and HTML content assertions instead.
- **No network except pip + git.** External APIs and webhooks won't reach the outside world.

## Commit conventions

See the environment system prompt for git safety rules and the required development branch (`claude/contracttwin-3d-agent-Nz15G`).
