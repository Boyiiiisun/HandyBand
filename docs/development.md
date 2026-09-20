# Developing HandyBand

For the project overview, landmark diagrams, and playing instructions, see the [README](../README.md).

## Desktop setup

The desktop application requires **Python 3.12**, a webcam, and audio output. Run commands from the repository root so the model and audio paths resolve correctly.

### One-click setup on Windows

Double-click **Start HandyBand.cmd**. The launcher installs a local copy of uv, obtains Python 3.12 if needed, creates `.venv`, installs the locked dependencies, and downloads checksum-verified models. The first launch requires internet; subsequent launches reuse the local files.

After `git pull`, run the same launcher to refresh and start the application. To select another camera from Command Prompt:

```bat
"Start HandyBand.cmd" --camera 1
```

### Manual Python setup

In PowerShell:

```powershell
git clone https://github.com/Boyiiiisun/HandyBand.git
cd HandyBand
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/download_models.py
python -m handyband
```

The `python` command used to create the environment must resolve to Python 3.12. The pip installation follows the dependency ranges in `pyproject.toml`; use uv for the exact versions in `uv.lock`.

To refresh an existing checkout:

```powershell
git pull
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python scripts/download_models.py
python -m handyband
```

Launch a specific style or camera:

```powershell
python -m handyband --style Odysseus
python -m handyband --style Piano
python -m handyband --camera 1
```

## Serve the browser application locally

From the repository root:

```powershell
python -m http.server 8000
```

Open [localhost:8000](http://localhost:8000) in a browser and allow camera access. Use localhost rather than opening `index.html` as a file. Remote camera access requires HTTPS. The page still downloads MediaPipe libraries and models from external hosts and loads audio from this repository; internet access is required.

No frontend build step is needed. The page is [index.html](../index.html), and the browser logic is [web/handyband.js](../web/handyband.js).

## Development checks

With uv installed:

```powershell
uv sync --locked --extra dev
uv run pytest
uv run ruff check .
```

If uv was installed by the Windows launcher, its repository-local executable is `.tools\uv.exe`.

Alternatively, in the activated Python environment:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

The tests cover Python recognition, audio handling, and application behavior. They do not replace a browser or physical camera/speaker check. For a manual check, try both styles, both hands, sound enable/mute, style switching, and pause/resume. Confirm that Piano uses different left/right clips and that Odysseus drums respond to deliberate downstrokes.

## Build the Windows app

On Windows with uv and Git installed:

```powershell
uv sync --locked --extra build
uv run --locked python scripts/build_windows.py
```

The portable folder is `dist/HandyBand`. The build copies Git-tracked published audio assets and the downloaded models, then runs `HandyBand.exe --self-test` from outside the project directory. This verifies bundled model inference and style initialization with dummy audio; it does not test physical camera or speaker hardware.

The Windows release workflow tests and packages the application when a version tag is pushed, then publishes the ZIP and SHA-256 checksum to GitHub Releases.

## Implementation map

| File | Responsibility |
| --- | --- |
| [hand_tracking.py](../src/handyband/hand_tracking.py) | Hand landmarks and handedness |
| [finger_state.py](../src/handyband/finger_state.py) | Extended/bent finger classification |
| [finger_gesture.py](../src/handyband/finger_gesture.py) | Numbered shapes, stability, and retrigger timing |
| [pose_tracking.py](../src/handyband/pose_tracking.py), [forearm.py](../src/handyband/forearm.py) | Pose detection and forearm anchors |
| [drum_gesture.py](../src/handyband/drum_gesture.py) | Downstroke detection and volume mapping |
| [styles.py](../src/handyband/styles.py) | Odysseus and Piano sound mappings |
| [finger_audio.py](../src/handyband/finger_audio.py), [drum_audio.py](../src/handyband/drum_audio.py) | Desktop sample playback |
| [web/handyband.js](../web/handyband.js) | Browser tracking, recognition, drawing, and audio |

The README diagrams describe the hand shapes shared by the browser and desktop. Check both implementations when documenting behavior: their gesture-3 alternatives and audio transitions differ.
