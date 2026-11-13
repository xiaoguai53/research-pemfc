"""Restore the pinned scientific checkout for development and reference replay."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/ECSIM/opem.git"
COMMIT = "27d343fb966361a4e6cc99650241f651778fc50f"


def main() -> None:
    destination = ROOT / "repo" / "opem"
    if destination.exists():
        actual = subprocess.check_output(
            ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != COMMIT:
            raise SystemExit(f"Existing source is {actual}; expected {COMMIT}. No files changed.")
        print(f"Pinned OPEM source already present: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--no-checkout", URL, str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "--detach", COMMIT], check=True)
    print(f"Restored {URL} at {COMMIT}")


if __name__ == "__main__":
    main()
