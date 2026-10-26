"""Reproducible corrected successor to the synthetic flawed filing."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/examples/clean"
TARGET = ROOT / "data/workflow/revised"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in ("rates.csv", "rates.xlsx", "narrative.md"):
        shutil.copyfile(SOURCE / name, TARGET / name)
    metadata = json.loads((SOURCE / "filing.json").read_text(encoding="utf-8"))
    metadata["scenario_id"] = "revised_flawed"
    for document in metadata["documents"]:
        if document["document_id"] == "DOC-RATES":
            document["text"] = document["text"].replace("rates.csv and rates.xlsx show", "uploaded rate exhibit shows")
    (TARGET / "filing.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print("Built corrected synthetic revision with its own scenario ID.")


if __name__ == "__main__":
    main()
