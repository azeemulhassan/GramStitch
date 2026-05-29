from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import (
    BooleanVar,
    END,
    Frame,
    IntVar,
    Label,
    Listbox,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    ttk,
)

from PIL import Image


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True)
class StitchOptions:
    output_path: Path
    crop_top: int
    crop_bottom: int
    center_images: bool
    white_background: bool


class GramStitchApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("GramStitch")
        self.root.geometry("820x560")
        self.root.minsize(720, 480)

        self.files: list[Path] = []
        self.status = StringVar(value="Add images or a folder to begin.")
        self.crop_top = IntVar(value=0)
        self.crop_bottom = IntVar(value=0)
        self.center_images = BooleanVar(value=True)
        self.white_background = BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        title = ttk.Label(main, text="GramStitch", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        content = ttk.Frame(main)
        content.grid(row=1, column=0, sticky="nsew", pady=(12, 8))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0)
        content.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(content)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        ttk.Label(list_frame, text="Images, top to bottom").grid(row=0, column=0, sticky="w")

        self.listbox = Listbox(list_frame, selectmode="extended", activestyle="dotbox")
        self.listbox.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.listbox.bind("<<ListboxSelect>>", lambda _event: self._update_status())

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        self.listbox.configure(yscrollcommand=scrollbar.set)

        controls = ttk.Frame(content)
        controls.grid(row=0, column=1, sticky="ns", padx=(12, 0))

        self._button(controls, "Add Folder", self.add_folder).pack(fill="x", pady=(0, 6))
        self._button(controls, "Add Images", self.add_images).pack(fill="x", pady=6)
        self._button(controls, "Remove", self.remove_selected).pack(fill="x", pady=6)
        ttk.Separator(controls).pack(fill="x", pady=10)
        self._button(controls, "Move Up", lambda: self.move_selected(-1)).pack(fill="x", pady=6)
        self._button(controls, "Move Down", lambda: self.move_selected(1)).pack(fill="x", pady=6)
        self._button(controls, "Sort A-Z", self.sort_files).pack(fill="x", pady=6)
        ttk.Separator(controls).pack(fill="x", pady=10)

        options = ttk.LabelFrame(controls, text="Options", padding=10)
        options.pack(fill="x", pady=(0, 10))
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="Crop top").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Spinbox(options, from_=0, to=5000, textvariable=self.crop_top, width=8).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(options, text="Crop bottom").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(options, from_=0, to=5000, textvariable=self.crop_bottom, width=8).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Checkbutton(options, text="Center narrower images", variable=self.center_images).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        ttk.Checkbutton(options, text="White background", variable=self.white_background).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=2
        )

        self.stitch_button = self._button(controls, "Stitch to PNG", self.stitch)
        self.stitch_button.pack(fill="x", pady=(4, 0))

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew")

        status_bar = ttk.Frame(main)
        status_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        status_bar.columnconfigure(0, weight=1)

        Label(status_bar, textvariable=self.status, anchor="w").grid(row=0, column=0, sticky="ew")

    def _button(self, parent: Frame, text: str, command) -> ttk.Button:
        return ttk.Button(parent, text=text, command=command)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose image folder")
        if not folder:
            return

        new_files = [
            path
            for path in sorted(Path(folder).iterdir(), key=lambda item: item.name.lower())
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        self._add_files(new_files)

    def add_images(self) -> None:
        filenames = filedialog.askopenfilenames(
            title="Choose images",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        self._add_files([Path(filename) for filename in filenames])

    def _add_files(self, paths: list[Path]) -> None:
        existing = {path.resolve() for path in self.files}
        added = 0

        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in existing:
                continue
            self.files.append(path)
            existing.add(resolved)
            added += 1

        self._refresh_list()
        self.status.set(f"Added {added} image{'s' if added != 1 else ''}.")

    def remove_selected(self) -> None:
        selected = set(self.listbox.curselection())
        if not selected:
            return

        self.files = [path for index, path in enumerate(self.files) if index not in selected]
        self._refresh_list()

    def move_selected(self, direction: int) -> None:
        selected = list(self.listbox.curselection())
        if not selected:
            return

        if direction < 0:
            indexes = selected
        else:
            indexes = list(reversed(selected))

        for index in indexes:
            target = index + direction
            if target < 0 or target >= len(self.files):
                continue
            self.files[index], self.files[target] = self.files[target], self.files[index]

        self._refresh_list()
        for index in selected:
            moved = index + direction
            if 0 <= moved < len(self.files):
                self.listbox.selection_set(moved)

    def sort_files(self) -> None:
        self.files.sort(key=lambda path: path.name.lower())
        self._refresh_list()
        self.status.set("Sorted by filename.")

    def stitch(self) -> None:
        if not self.files:
            messagebox.showwarning("No images", "Add at least one image first.")
            return

        output = filedialog.asksaveasfilename(
            title="Save stitched image",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
            initialfile="stitched.png",
        )
        if not output:
            return

        try:
            options = StitchOptions(
                output_path=Path(output),
                crop_top=max(0, int(self.crop_top.get())),
                crop_bottom=max(0, int(self.crop_bottom.get())),
                center_images=bool(self.center_images.get()),
                white_background=bool(self.white_background.get()),
            )
        except ValueError:
            messagebox.showerror("Invalid crop", "Crop values must be whole numbers.")
            return

        self._set_busy(True)
        worker = threading.Thread(target=self._stitch_worker, args=(self.files.copy(), options), daemon=True)
        worker.start()

    def _stitch_worker(self, files: list[Path], options: StitchOptions) -> None:
        try:
            stitch_images(files, options)
        except Exception as exc:
            self.root.after(0, lambda: self._finish_stitch(error=exc))
        else:
            self.root.after(0, lambda: self._finish_stitch(output_path=options.output_path))

    def _finish_stitch(self, output_path: Path | None = None, error: Exception | None = None) -> None:
        self._set_busy(False)

        if error is not None:
            messagebox.showerror("Stitch failed", str(error))
            self.status.set("Stitch failed.")
            return

        self.status.set(f"Saved {output_path}")
        messagebox.showinfo("Done", f"Saved stitched image:\n{output_path}")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.stitch_button.configure(state=state)

        if busy:
            self.status.set("Stitching images...")
            self.progress.start(10)
        else:
            self.progress.stop()

    def _refresh_list(self) -> None:
        self.listbox.delete(0, END)
        for index, path in enumerate(self.files, start=1):
            self.listbox.insert(END, f"{index:03d}  {path.name}")
        self._update_status()

    def _update_status(self) -> None:
        total = len(self.files)
        selected = len(self.listbox.curselection())
        if total == 0:
            self.status.set("Add images or a folder to begin.")
        elif selected:
            self.status.set(f"{total} image{'s' if total != 1 else ''}, {selected} selected.")
        else:
            self.status.set(f"{total} image{'s' if total != 1 else ''} ready.")


def stitch_images(files: list[Path], options: StitchOptions) -> None:
    prepared: list[Image.Image] = []

    try:
        for file in files:
            image = Image.open(file)
            image.load()

            left = 0
            top = min(options.crop_top, image.height)
            right = image.width
            bottom = max(top, image.height - options.crop_bottom)
            image = image.crop((left, top, right, bottom))

            if image.height <= 0 or image.width <= 0:
                raise ValueError(f"Crop removed all pixels from {file.name}.")

            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            prepared.append(image.convert("RGBA" if has_alpha else "RGB"))

        if not prepared:
            raise ValueError("No readable images were selected.")

        output_width = max(image.width for image in prepared)
        output_height = sum(image.height for image in prepared)
        has_alpha_output = any(image.mode == "RGBA" for image in prepared) and not options.white_background
        output_mode = "RGBA" if has_alpha_output else "RGB"
        background = (255, 255, 255, 0) if output_mode == "RGBA" else (255, 255, 255)
        result = Image.new(output_mode, (output_width, output_height), background)

        y = 0
        for image in prepared:
            x = (output_width - image.width) // 2 if options.center_images else 0
            paste_image = image
            if output_mode == "RGB" and image.mode == "RGBA":
                flattened = Image.new("RGB", image.size, (255, 255, 255))
                flattened.paste(image, mask=image.getchannel("A"))
                paste_image = flattened
            result.paste(paste_image, (x, y))
            y += image.height

        options.output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(options.output_path, format="PNG", optimize=True)
    finally:
        for image in prepared:
            image.close()


def main() -> None:
    root = Tk()
    ttk.Style().theme_use("clam")
    GramStitchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
