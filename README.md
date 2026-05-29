# GramStitch

GramStitch is a small Windows-friendly Python GUI for stitching separate Instagram scroll images into one long lossless PNG.

## Run

```powershell
pip install -r requirements.txt
python app.py
```

## Build an EXE

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name GramStitch app.py
```

The executable will be created at `dist\GramStitch.exe`.

## Current Features

- Add a folder of images or pick individual image files.
- Reorder images manually with move up/down.
- Sort images by filename.
- Stitch vertically into a PNG.
- Optional top/bottom crop for repeated browser or Instagram UI areas.
- Optional centering for images that do not all share the same width.

