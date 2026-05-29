# GramStitch

GramStitch is a lightweight Windows-friendly Python GUI for combining separate Instagram scroll screenshots or ripped image slices into one long lossless PNG. It lets users add images, arrange their order, crop repeated top/bottom UI areas, and stitch everything vertically into a clean continuous image.

## Run

```powershell
pip install -r requirements.txt
python app.py
```

## Current Features

- Add a folder of images or pick individual image files.
- Reorder images manually with move up/down.
- Sort images by filename.
- Stitch vertically into a PNG.
- Optional top/bottom crop for repeated browser or Instagram UI areas.
- Optional centering for images that do not all share the same width.
