# GramStitch

GramStitch is a lightweight Windows-friendly Python GUI for combining separate Instagram scroll screenshots or ripped image slices into one long lossless PNG. It lets users add images, arrange their order, crop repeated top/bottom UI areas, and stitch everything vertically or horizontally into a clean continuous image.

## Windows Download

Download the latest standalone Windows app: [GramStitch.exe](https://github.com/azeemulhassan/GramStitch/releases/latest/download/GramStitch.exe)

No Python installation is required. See the [latest release](https://github.com/azeemulhassan/GramStitch/releases/latest) for release details.

## Run

```powershell
pip install -r requirements.txt
python app.py
```

## Current Features

- Add a folder, pick individual image files, or drag images and folders in from Explorer.
- Reorder rendered image blocks by dragging them or using move up/down.
- Sort images by filename.
- Stitch vertically or horizontally into a PNG.
- Preview the final stitched result before export.
- Apply top/bottom crops to individual image slices.
- Optionally remove exact repeated overlaps between adjacent images.
- Save and reopen project files.
- Undo and redo edits.
- Zoom and navigate long previews with the mouse wheel.
- Optional centering for images that do not all share the same width or height.
