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
