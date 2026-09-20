"""Build a portable Windows folder containing only published project assets."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    subprocess.run([sys.executable, "scripts/download_models.py"], cwd=ROOT, check=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
         "--name", "HandyBand", "--specpath", "build", "--paths", "src",
         "--collect-all", "mediapipe", "scripts/desktop_entry.py"],
        cwd=ROOT, check=True,
    )
    destination = ROOT / "dist/HandyBand"
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "HandyBand_Audio"], cwd=ROOT,
    ).decode().split("\0")
    assets = [Path(p) for p in tracked if p and Path(p).suffix in {".wav", ".md"}]
    assets += [Path("models/hand_landmarker.task"), Path("models/pose_landmarker_lite.task")]
    assets += [Path("LICENSE"), Path("README.md")]
    for relative in assets:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    subprocess.run([str(destination / "HandyBand.exe"), "--self-test"], cwd=ROOT.parent,
                   check=True)


if __name__ == "__main__":
    main()
