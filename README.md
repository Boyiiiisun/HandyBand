# HandyBand

HandyBand is a gesture-controlled music platform that lets one person perform like a full band by using intuitive hand movements to control different instruments and sounds in real time.

https://boyiiiisun.github.io/HandyBand/

## Run locally

HandyBand requires Python 3.12, a webcam, and an audio output device. Run all
commands from the repository root so the bundled audio files can be found.

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

If the repository is already cloned, update and refresh the environment with:

```powershell
git pull
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python scripts/download_models.py
python -m handyband
```

Use the menu in the upper-right corner of the camera window to switch music
styles. Press `Q`, `Esc`, or close the window to exit. If the default camera is
not available, try `python -m handyband --camera 1`.

## Interstellar guided performance

Select **Interstellar** in the camera window's style menu, or start directly:

```powershell
python -m handyband --style Interstellar
```

Follow the pictured hand shape with your selected hand (palm toward the camera).
The next two cards preview upcoming shapes. Hold the current shape until its
duration bar ends. One successful card plays one musical unit; the lower
accompaniment runs independently. Missing a card never auto-plays its melody.

| Key | Action |
| --- | --- |
| Space | Start / pause / resume; replay after finishing |
| T | Learn each hand shape, with sound |
| P | Practice the selected phrase; waits for the correct shape |
| E | Perform the full excerpt on a continuous timeline |
| L / R | Select the anatomical left / right hand and reset |
| B / N | Previous / next practice phrase |
| A | Practice the first missed or prematurely released phrase |
| Q / Esc | Exit |

Every start/resume has a four-beat visual count-in. Hold a shape steadily for
150 ms to confirm it. You can prepare early; performance allows 200 ms late.
Adjacent identical cards require a brief relaxation (100 ms) and re-formation.
Short tracking flicker is tolerated; after 350 ms without the selected hand,
both timeline and sound pause. Show your hand again for a recovery count-in.
Manual pauses require Space to resume.

The locally downloaded Cornfield Chase MIDI and prepared score are excluded
from Git. A fresh clone shows a clearly marked gesture exercise until a score is
imported. See [music sources, cutoff and import commands](HandyBand_Audio/Interstellar/README.md).

## Development checks

Install the development dependencies and run the checks from the repository
root:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

## License

This project is licensed under the [MIT License](LICENSE).
