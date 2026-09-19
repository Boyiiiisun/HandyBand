"""Download and verify the official MediaPipe models used by HandyBand."""

import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIRECTORY = PROJECT_ROOT / "models"


@dataclass(frozen=True, slots=True)
class ModelDownload:
    name: str
    url: str
    sha256: str
    destination: Path


MODELS = (
    ModelDownload(
        name="Hand Landmarker",
        url=(
            "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
            "hand_landmarker/float16/1/hand_landmarker.task"
        ),
        sha256="fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
        destination=MODELS_DIRECTORY / "hand_landmarker.task",
    ),
    ModelDownload(
        name="Pose Landmarker Lite",
        url=(
            "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
            "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
        ),
        sha256="59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
        destination=MODELS_DIRECTORY / "pose_landmarker_lite.task",
    ),
)


def _checksum(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as model_file:
        while chunk := model_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _download(model: ModelDownload) -> bool:
    if model.destination.exists():
        if _checksum(model.destination) == model.sha256:
            print(f"{model.name} already exists and passed checksum verification.")
            return True
        print(
            f"Existing {model.name} failed checksum verification: {model.destination}",
            file=sys.stderr,
        )
        return False

    model.destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = model.destination.with_suffix(".tmp")
    request = Request(model.url, headers={"User-Agent": "HandyBand model downloader"})
    print(f"Downloading {model.name} from {model.url}")
    try:
        with urlopen(request, timeout=60) as response, temporary_path.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        temporary_path.unlink(missing_ok=True)
        print(f"Download failed: {error}", file=sys.stderr)
        return False

    if _checksum(temporary_path) != model.sha256:
        temporary_path.unlink(missing_ok=True)
        print(f"{model.name} failed checksum verification.", file=sys.stderr)
        return False

    temporary_path.replace(model.destination)
    print(f"Saved {model.name} to {model.destination}")
    return True


def main() -> int:
    return 0 if all(_download(model) for model in MODELS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
