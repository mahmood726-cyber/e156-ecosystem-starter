"""CI smoke using an exact generated grant for the existing synthetic packet."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from source_rights_fixtures import synthetic_env

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        packet = root / "packet.json"
        shutil.copyfile(ROOT / "examples/synthetic_packet.json", packet)
        subprocess.run([sys.executable, "-B", str(ROOT / "scripts/synthesis_preflight.py"),
                        "--prompt", str(ROOT / "docs/SYNTHESIS-PREFLIGHT-v1.1.md"),
                        "--packet", str(packet), "--output-dir", args.output_dir],
                       env=synthetic_env(root), check=True)


if __name__ == "__main__":
    main()
