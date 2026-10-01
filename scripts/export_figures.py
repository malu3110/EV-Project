"""Copy selected figures out of the executed notebook into docs/figures/ (used by the README)."""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "ev_adoption_india.ipynb"
OUT = ROOT / "docs" / "figures"

# Each figure is identified by a string unique to the code cell that draws it
FIGURES = {
    "barriers_motivators.png": 'title in [(axes[0], concerns.drop("none_not_sure")',
    "chargers_vs_registrations.png": 'ax.set_title("Larger EV markets have more chargers")',
    "forecast_check.png": 'ax.set_title("Neither simple trend model forecasts well")',
    "tco_breakeven.png": 'ax.set_title(f"Cumulative cost advantage of the EV',
}

cells = json.loads(NB.read_text())["cells"]
OUT.mkdir(parents=True, exist_ok=True)
for name, marker in FIGURES.items():
    matches = [c for c in cells if c["cell_type"] == "code" and marker in "".join(c["source"])]
    assert len(matches) == 1, f"{name}: expected 1 matching cell, found {len(matches)}"
    pngs = [o["data"]["image/png"] for o in matches[0].get("outputs", []) if "image/png" in o.get("data", {})]
    assert pngs, f"{name}: cell has no image output; execute the notebook first"
    (OUT / name).write_bytes(base64.b64decode(pngs[-1]))
    print("wrote", (OUT / name).relative_to(ROOT))
