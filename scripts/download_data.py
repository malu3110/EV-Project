"""Fetch the third-party datasets the notebook uses into data/external/.

These files are not redistributed in this repository because their
redistribution terms could not be confirmed (see README, "Data terms").

    python scripts/download_data.py          # download what can be automated, then verify
    python scripts/download_data.py --check  # only verify what is already present

Kaggle datasets are downloaded with the Kaggle API, which needs an API token
(https://www.kaggle.com/docs/api: put kaggle.json in ~/.kaggle/ or set
KAGGLE_USERNAME and KAGGLE_KEY). The data.gov.in and IEA files are behind those
sites' own download pages; the script prints where to get them and where to put
them, then verifies them.

Each file is checked against the SHA-256 of the copy the published analysis
used. A mismatch is reported as a warning, not an error: the source may have
been updated, in which case the notebook will still run but its numbers may
differ from the published version.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "external"

DATASETS = [
    {
        "file": "EV_Dataset.csv",
        "sha256": "dc56c6a47344bf3189bc0a5e251f886fa353c939639662d286845818c543ccbb",
        "source": "Kaggle: Electric Vehicle Sales by State in India (mafzal19)",
        "url": "https://www.kaggle.com/datasets/mafzal19/electric-vehicle-sales-by-state-in-india",
        "kaggle": "mafzal19/electric-vehicle-sales-by-state-in-india",
    },
    {
        "file": "ev_sales_by_makers_and_cat_15-24.csv",
        "sha256": "fd4a2f3c3a8cd75684990993af76d6055307f3ff9e994991571e97cc4da0ddb9",
        "source": "Kaggle: Detailed India EV Market Data 2001-2024 (srinrealyf)",
        "url": "https://www.kaggle.com/datasets/srinrealyf/india-ev-market-data",
        "kaggle": "srinrealyf/india-ev-market-data",
    },
    {
        "file": "OperationalPC.csv",
        "sha256": "0279a85d54aa985984d66cbf6be86eb340c2ff8cd5353f5fad2da93f7be57cfb",
        "source": "Kaggle: Detailed India EV Market Data 2001-2024 (srinrealyf)",
        "url": "https://www.kaggle.com/datasets/srinrealyf/india-ev-market-data",
        "kaggle": "srinrealyf/india-ev-market-data",
    },
    {
        "file": "RS_Session_259_AU_3475_1.csv",
        "sha256": "4af008a523f87a23cc4a230c724f8537229dfaf1406c4405e94ba43434ef6abf",
        "source": "data.gov.in: Rajya Sabha Session 259, USQ 3475 — State/UT-wise registered EVs (e-Vahan, as on 06-03-2023)",
        "url": "https://www.data.gov.in/resource/stateut-wise-details-registered-electric-vehicles-india-e-vahan-portal-ministry-road",
    },
    {
        "file": "RS_Session_265_AU_1355_A_and_B.csv",
        "sha256": "9973482ba2975541acbed399dcf6029c23a436529a2ae895fd57f1835228d519",
        "source": "data.gov.in: Rajya Sabha Session 265, USQ 1355 — Year-wise registered EVs (e-Vahan), 2019-20 to 2023-24",
        "url": "https://www.data.gov.in/resource/year-wise-number-registered-electric-vehicles-e-vahan-portal-2019-20-2023-24",
    },
    {
        "file": "IEA Global EV Data 2024.csv",
        "sha256": "292b9ad2c38a1571546396b8fcf0a57f1918421725c7892e8d3eb32a406c4951",
        "source": "IEA: Global EV Outlook 2024 data product ('EV data by country' CSV)",
        "url": "https://www.iea.org/data-and-statistics/data-product/global-ev-outlook-2024",
    },
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_kaggle(slug, wanted):
    """Download a Kaggle dataset and copy the wanted files into DEST."""
    if shutil.which("kaggle") is None:
        print(f"  ! Kaggle CLI not found (pip install kaggle); skipping {slug}")
        return
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["kaggle", "datasets", "download", "-d", slug, "-p", tmp, "--unzip", "-q"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ! Kaggle download failed for {slug}:\n    {result.stderr.strip() or result.stdout.strip()}")
            return
        for name in wanted:
            found = list(Path(tmp).rglob(name))
            if found:
                shutil.copy(found[0], DEST / name)
                print(f"  downloaded {name}")
            else:
                print(f"  ! {name} not found in {slug}; the dataset may have changed")


def verify():
    missing, mismatched = [], []
    for d in DATASETS:
        path = DEST / d["file"]
        if not path.exists():
            missing.append(d)
        elif sha256(path) != d["sha256"]:
            mismatched.append(d)
    for d in DATASETS:
        status = ("MISSING" if d in missing else "CHANGED" if d in mismatched else "ok")
        print(f"  [{status:7s}] {d['file']}")
    if mismatched:
        print("\nWarning: these files differ from the versions the published analysis used;"
              "\nthe notebook will run but its numbers may not match the published results:")
        for d in mismatched:
            print(f"  - {d['file']}  ({d['url']})")
    if missing:
        print("\nStill needed. Download each from its page and save it under data/external/ with the exact name shown:")
        for d in missing:
            print(f"  - {d['file']}\n      {d['source']}\n      {d['url']}")
    return not missing


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="only verify files already present")
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)

    if not args.check:
        by_slug = {}
        for d in DATASETS:
            if "kaggle" in d and not (DEST / d["file"]).exists():
                by_slug.setdefault(d["kaggle"], []).append(d["file"])
        for slug, files in by_slug.items():
            print(f"Kaggle: {slug}")
            fetch_kaggle(slug, files)

    print(f"\nChecking {DEST.relative_to(ROOT)}/")
    sys.exit(0 if verify() else 1)


if __name__ == "__main__":
    main()
