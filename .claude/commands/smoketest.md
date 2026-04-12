---
description: Run end-to-end ContractTwin smoke test against Flask test_client
allowed-tools: Bash(python3:*)
---

Run this smoke test from the repo root. It verifies the ContractTwin subsystem end-to-end via Flask's `test_client` without needing a browser. Print pass/fail for each assertion and exit non-zero on any failure.

```bash
python3 - <<'PY'
import io, json, sys

from app import app

client = app.test_client()
failures = []

SAMPLE_CLAUSE = (
    "1. Forecast. Buyer shall provide Supplier with a rolling twelve (12) month "
    "forecast of anticipated purchase orders, updated monthly. Supplier shall use "
    "commercially reasonable efforts to maintain capacity consistent with forecasts."
)

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)

# 1. Demo endpoint — calibration sanity
r = client.get("/contracttwin/demo")
check("demo returns 200", r.status_code == 200, f"got {r.status_code}")
demo = r.get_json() or {}
clauses = demo.get("clauses", [])
check("demo has ~27 clauses", 20 <= len(clauses) <= 40, f"got {len(clauses)}")
portfolio = demo.get("portfolio_summary", {})
ram = portfolio.get("risk_adjusted_margin")
check(
    "risk_adjusted_margin in [0.03, 0.15]",
    ram is not None and 0.03 <= ram <= 0.15,
    f"got {ram}",
)

# 2. ContractTwin page shell — DOM hooks for the frontend
r = client.get("/contracttwin")
check("page returns 200", r.status_code == 200)
body = r.get_data(as_text=True)
for hook in ("twinCanvas", "contractFile", "statCeiling"):
    check(f"page contains {hook}", hook in body)

# 3. /parse — JSON body
r = client.post(
    "/contracttwin/parse",
    data=json.dumps({"text": SAMPLE_CLAUSE}),
    content_type="application/json",
)
check("parse accepts JSON body", r.status_code == 200, f"got {r.status_code}")

# 4. /parse — .txt multipart upload
r = client.post(
    "/contracttwin/parse",
    data={"file": (io.BytesIO(SAMPLE_CLAUSE.encode()), "sample.txt")},
    content_type="multipart/form-data",
)
check("parse accepts .txt upload", r.status_code == 200, f"got {r.status_code}")

# 5. /parse — .docx multipart upload (generated inline)
try:
    from docx import Document  # type: ignore
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph(SAMPLE_CLAUSE)
    doc.save(buf)
    buf.seek(0)
    r = client.post(
        "/contracttwin/parse",
        data={"file": (buf, "sample.docx")},
        content_type="multipart/form-data",
    )
    check("parse accepts .docx upload", r.status_code == 200, f"got {r.status_code}")
except ImportError:
    print("  [SKIP] parse .docx upload — python-docx not installed")

# 6. /parse — rejects .pdf
r = client.post(
    "/contracttwin/parse",
    data={"file": (io.BytesIO(b"%PDF-1.4"), "sample.pdf")},
    content_type="multipart/form-data",
)
check("parse rejects .pdf", r.status_code == 400, f"got {r.status_code}")

# 7. Scenario engine — forecast_collapse
r = client.get("/contracttwin/scenarios/forecast_collapse")
check("forecast_collapse returns 200", r.status_code == 200)
scen = r.get_json() or {}
check("forecast_collapse has activations", bool(scen.get("activations")))
total_ev = scen.get("total_ev", 0)
check("forecast_collapse total_ev > 0", total_ev > 0, f"got {total_ev}")

print()
if failures:
    print(f"FAILED ({len(failures)}): " + ", ".join(failures))
    sys.exit(1)
print("ALL SMOKE TESTS PASSED")
PY
```

Report the output to the user. If any test fails, investigate the root cause before proposing fixes — do not auto-repair a failing smoke test without first understanding why it broke.
