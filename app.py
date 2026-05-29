from __future__ import annotations

import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import (
    BooleanVar,
    Canvas,
    Frame,
    IntVar,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    ttk,
)

from PIL import Image, ImageOps, ImageTk


SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

GITHUB_URL = "https://github.com/azeemulhassan/GramStitch"
THEMES = {
    "dark": {
        "page": "#0f172a",
        "panel": "#172033",
        "card": "#111827",
        "card_border": "#334155",
        "card_selected": "#60a5fa",
        "text": "#e5e7eb",
        "muted": "#94a3b8",
        "thumb_bg": "#1f2937",
        "button_text": "#e5e7eb",
        "button_bg": "#1f2937",
        "button_active": "#253248",
        "primary_bg": "#2563eb",
        "primary_active": "#1d4ed8",
        "primary_text": "#ffffff",
    },
    "light": {
        "page": "#f4f7fb",
        "panel": "#e8eef6",
        "card": "#ffffff",
        "card_border": "#d8dee9",
        "card_selected": "#2563eb",
        "text": "#111827",
        "muted": "#5b6472",
        "thumb_bg": "#f8fafc",
        "button_text": "#111827",
        "button_bg": "#f8fafc",
        "button_active": "#e5edf7",
        "primary_bg": "#dbeafe",
        "primary_active": "#bfdbfe",
        "primary_text": "#0f172a",
    },
}
THUMBNAIL_SIZE = (96, 96)


@dataclass(frozen=True)
class StitchOptions:
    output_path: Path
    orientation: str
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
        self.theme_name = StringVar(value="dark")
        self.orientation = StringVar(value="vertical")
        self.crop_top = IntVar(value=0)
        self.crop_bottom = IntVar(value=0)
        self.center_images = BooleanVar(value=True)
        self.white_background = BooleanVar(value=True)
        self.selected_index: int | None = None
        self.drag_index: int | None = None
        self.drag_target_index: int | None = None
        self.thumbnail_images: list[ImageTk.PhotoImage] = []

        self._build_ui()

    @property
    def colors(self) -> dict[str, str]:
        return THEMES[self.theme_name.get()]

    def _build_ui(self) -> None:
        self._configure_style()

        main = ttk.Frame(self.root, padding=16, style="App.TFrame")
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        title = ttk.Label(header, text="GramStitch", style="Title.TLabel")
        title.grid(row=0, column=0, sticky="w")
        subtitle = ttk.Label(
            header,
            text="Arrange image slices visually, then export one clean PNG.",
            style="Muted.TLabel",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Checkbutton(
            header,
            text="Dark",
            variable=self.theme_name,
            onvalue="dark",
            offvalue="light",
            command=self._on_theme_change,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        content = ttk.Frame(main, style="App.TFrame")
        content.grid(row=1, column=0, sticky="nsew", pady=(16, 10))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0)
        content.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(content, padding=12, style="Panel.TFrame")
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)

        preview_header = ttk.Frame(list_frame, style="Panel.TFrame")
        preview_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        preview_header.columnconfigure(0, weight=1)
        ttk.Label(preview_header, text="Preview order", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            preview_header,
            text="Drag thumbnails to rearrange the final stitch.",
            style="PanelMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        canvas_frame = ttk.Frame(list_frame, style="Panel.TFrame")
        canvas_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.canvas = Canvas(
            canvas_frame,
            background=self.colors["panel"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<Configure>", lambda _event: self._refresh_preview())

        y_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        controls = ttk.Frame(content, padding=(12, 0, 0, 0), style="App.TFrame")
        controls.grid(row=0, column=1, sticky="ns")

        self._button(controls, "Add Folder", self.add_folder, "Primary.TButton").pack(fill="x", pady=(0, 6))
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

        ttk.Label(options, text="Direction").grid(row=0, column=0, sticky="w", pady=2)
        direction = ttk.Frame(options)
        direction.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Radiobutton(
            direction,
            text="Vertical",
            value="vertical",
            variable=self.orientation,
            command=self._refresh_preview,
        ).pack(side="left")
        ttk.Radiobutton(
            direction,
            text="Horizontal",
            value="horizontal",
            variable=self.orientation,
            command=self._refresh_preview,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(options, text="Crop top").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(options, from_=0, to=5000, textvariable=self.crop_top, width=8).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(options, text="Crop bottom").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Spinbox(options, from_=0, to=5000, textvariable=self.crop_bottom, width=8).grid(
            row=2, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Checkbutton(options, text="Center images on cross-axis", variable=self.center_images).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        ttk.Checkbutton(options, text="White background", variable=self.white_background).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=2
        )

        self.stitch_button = self._button(controls, "Stitch to PNG", self.stitch, "Primary.TButton")
        self.stitch_button.pack(fill="x", pady=(4, 0))

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew")

        status_bar = ttk.Frame(main)
        status_bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        status_bar.columnconfigure(0, weight=1)

        ttk.Label(status_bar, textvariable=self.status, anchor="w", style="Status.TLabel").grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            status_bar,
            text="github.com/azeemulhassan",
            style="Link.TButton",
            command=lambda: webbrowser.open_new_tab(GITHUB_URL),
        ).grid(row=0, column=1, sticky="e")

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        colors = self.colors
        self.root.configure(background=colors["page"])
        style.configure("App.TFrame", background=colors["page"])
        style.configure("Panel.TFrame", background=colors["panel"])
        style.configure("TLabel", background=colors["page"], foreground=colors["text"], font=("Segoe UI", 10))
        style.configure(
            "Title.TLabel",
            background=colors["page"],
            foreground=colors["text"],
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Section.TLabel",
            background=colors["panel"],
            foreground=colors["text"],
            font=("Segoe UI", 12, "bold"),
        )
        style.configure("Muted.TLabel", background=colors["page"], foreground=colors["muted"], font=("Segoe UI", 9))
        style.configure(
            "PanelMuted.TLabel",
            background=colors["panel"],
            foreground=colors["muted"],
            font=("Segoe UI", 9),
        )
        style.configure("Status.TLabel", background=colors["page"], foreground=colors["muted"], font=("Segoe UI", 9))
        style.configure(
            "TButton",
            font=("Segoe UI", 10),
            padding=(12, 8),
            background=colors["button_bg"],
            foreground=colors["button_text"],
            bordercolor=colors["card_border"],
            lightcolor=colors["button_bg"],
            darkcolor=colors["button_bg"],
        )
        style.map(
            "TButton",
            background=[("active", colors["button_active"]), ("pressed", colors["button_active"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["button_text"])],
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 9),
            background=colors["primary_bg"],
            foreground=colors["primary_text"],
            bordercolor=colors["primary_bg"],
            lightcolor=colors["primary_bg"],
            darkcolor=colors["primary_bg"],
        )
        style.map(
            "Primary.TButton",
            background=[("active", colors["primary_active"]), ("pressed", colors["primary_active"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["primary_text"])],
        )
        style.configure(
            "Link.TButton",
            font=("Segoe UI", 9),
            padding=(8, 2),
            background=colors["page"],
            foreground=colors["muted"],
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Link.TButton",
            background=[("active", colors["page"]), ("pressed", colors["page"])],
            foreground=[("active", colors["card_selected"]), ("!disabled", colors["muted"])],
        )
        style.configure(
            "TCheckbutton",
            background=colors["page"],
            foreground=colors["text"],
            font=("Segoe UI", 10),
        )
        style.map(
            "TCheckbutton",
            background=[("active", colors["page"]), ("pressed", colors["page"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["text"])],
        )
        style.configure("TRadiobutton", background=colors["page"], foreground=colors["text"], font=("Segoe UI", 10))
        style.map(
            "TRadiobutton",
            background=[("active", colors["page"]), ("pressed", colors["page"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["text"])],
        )
        style.configure("TLabelframe", background=colors["page"], foreground=colors["text"])
        style.configure("TLabelframe.Label", background=colors["page"], foreground=colors["text"], font=("Segoe UI", 10, "bold"))

    def _on_theme_change(self) -> None:
        self._configure_style()
        self.canvas.configure(background=self.colors["panel"])
        self._refresh_preview()

    def _button(self, parent: Frame, text: str, command, style: str = "TButton") -> ttk.Button:
        return ttk.Button(parent, text=text, command=command, style=style)

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

        if added and self.selected_index is None:
            self.selected_index = 0
        self._refresh_preview()
        self.status.set(f"Added {added} image{'s' if added != 1 else ''}.")

    def remove_selected(self) -> None:
        if self.selected_index is None:
            return

        del self.files[self.selected_index]
        if not self.files:
            self.selected_index = None
        else:
            self.selected_index = min(self.selected_index, len(self.files) - 1)
        self._refresh_preview()

    def move_selected(self, direction: int) -> None:
        if self.selected_index is None:
            return

        target = self.selected_index + direction
        if target < 0 or target >= len(self.files):
            return

        self.files[self.selected_index], self.files[target] = self.files[target], self.files[self.selected_index]
        self.selected_index = target
        self._refresh_preview()

    def sort_files(self) -> None:
        self.files.sort(key=lambda path: path.name.lower())
        self.selected_index = 0 if self.files else None
        self._refresh_preview()
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
                orientation=self.orientation.get(),
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

    def _refresh_preview(self) -> None:
        if not hasattr(self, "canvas"):
            return

        self.canvas.delete("all")
        self.thumbnail_images.clear()

        if not self.files:
            self.canvas.create_text(
                max(self.canvas.winfo_width() // 2, 240),
                170,
                text="Add images to preview and arrange them here",
                fill=self.colors["muted"],
                font=("Segoe UI", 13, "bold"),
            )
            self.canvas.configure(scrollregion=(0, 0, max(self.canvas.winfo_width(), 520), 340))
            self._update_status()
            return

        if self.orientation.get() == "horizontal":
            self._draw_horizontal_preview()
        else:
            self._draw_vertical_preview()

        self._update_status()

    def _draw_vertical_preview(self) -> None:
        canvas_width = max(self.canvas.winfo_width(), 520)
        card_width = max(canvas_width - 24, 420)
        card_height = 118
        gap = 10
        y = 12

        for index, path in enumerate(self.files):
            self._draw_card(index, path, 12, y, card_width, card_height)
            y += card_height + gap

        self.canvas.configure(scrollregion=(0, 0, card_width + 24, y + 12))

    def _draw_horizontal_preview(self) -> None:
        card_width = 176
        card_height = 186
        gap = 10
        x = 12

        for index, path in enumerate(self.files):
            self._draw_card(index, path, x, 12, card_width, card_height, compact=True)
            x += card_width + gap

        self.canvas.configure(scrollregion=(0, 0, x + 12, card_height + 24))

    def _draw_card(
        self,
        index: int,
        path: Path,
        x: int,
        y: int,
        width: int,
        height: int,
        compact: bool = False,
    ) -> None:
        selected = index == self.selected_index
        colors = self.colors
        border = colors["card_selected"] if selected else colors["card_border"]
        tag = f"card:{index}"

        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill=colors["card"],
            outline=border,
            width=2 if selected else 1,
            tags=(tag, "card"),
        )

        thumb = self._make_thumbnail(path)
        self.thumbnail_images.append(thumb)

        if compact:
            thumb_x = x + (width - THUMBNAIL_SIZE[0]) // 2
            thumb_y = y + 14
            text_x = x + 14
            text_y = thumb_y + THUMBNAIL_SIZE[1] + 16
            self.canvas.create_image(thumb_x, thumb_y, image=thumb, anchor="nw", tags=(tag, "card"))
            self.canvas.create_text(
                text_x,
                text_y,
                text=f"{index + 1:02d}. {path.name}",
                fill=colors["text"],
                font=("Segoe UI", 9, "bold"),
                anchor="nw",
                width=width - 28,
                tags=(tag, "card"),
            )
        else:
            thumb_x = x + 14
            thumb_y = y + 11
            self.canvas.create_image(thumb_x, thumb_y, image=thumb, anchor="nw", tags=(tag, "card"))
            self.canvas.create_text(
                x + 128,
                y + 28,
                text=f"{index + 1:02d}. {path.name}",
                fill=colors["text"],
                font=("Segoe UI", 11, "bold"),
                anchor="nw",
                width=max(width - 154, 160),
                tags=(tag, "card"),
            )
            self.canvas.create_text(
                x + 128,
                y + 58,
                text=str(path.parent),
                fill=colors["muted"],
                font=("Segoe UI", 9),
                anchor="nw",
                width=max(width - 154, 160),
                tags=(tag, "card"),
            )

    def _make_thumbnail(self, path: Path) -> ImageTk.PhotoImage:
        try:
            with Image.open(path) as image:
                image = ImageOps.contain(image.convert("RGBA"), THUMBNAIL_SIZE)
                thumbnail = Image.new("RGBA", THUMBNAIL_SIZE, self._hex_to_rgba(self.colors["thumb_bg"]))
                x = (THUMBNAIL_SIZE[0] - image.width) // 2
                y = (THUMBNAIL_SIZE[1] - image.height) // 2
                thumbnail.alpha_composite(image, (x, y))
        except Exception:
            thumbnail = Image.new("RGBA", THUMBNAIL_SIZE, self._hex_to_rgba(self.colors["card_border"]))

        return ImageTk.PhotoImage(thumbnail)

    def _hex_to_rgba(self, color: str, alpha: int = 255) -> tuple[int, int, int, int]:
        value = color.lstrip("#")
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)

    def _on_canvas_press(self, event) -> None:
        index = self._event_index(event)
        if index is None:
            return

        self.selected_index = index
        self.drag_index = index
        self.drag_target_index = index
        self._refresh_preview()

    def _on_canvas_drag(self, event) -> None:
        if self.drag_index is None:
            return

        self.drag_target_index = self._target_index_for_event(event)
        self._refresh_preview()
        self._draw_insertion_marker(self.drag_target_index)

    def _on_canvas_release(self, event) -> None:
        if self.drag_index is None:
            return

        target = self._target_index_for_event(event)
        source = self.drag_index
        self.drag_index = None
        self.drag_target_index = None

        if target != source:
            path = self.files.pop(source)
            if target > source:
                target -= 1
            self.files.insert(target, path)
            self.selected_index = target

        self._refresh_preview()

    def _event_index(self, event) -> int | None:
        item = self.canvas.find_closest(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if not item:
            return None

        for tag in self.canvas.gettags(item[0]):
            if tag.startswith("card:"):
                index = int(tag.split(":", 1)[1])
                if 0 <= index < len(self.files):
                    return index
        return None

    def _target_index_for_event(self, event) -> int:
        if not self.files:
            return 0

        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        orientation = self.orientation.get()

        if orientation == "horizontal":
            card_width = 176
            gap = 10
            index = round((x - 12) / (card_width + gap))
        else:
            card_height = 118
            gap = 10
            index = round((y - 12) / (card_height + gap))

        return max(0, min(index, len(self.files)))

    def _draw_insertion_marker(self, index: int | None) -> None:
        if index is None:
            return

        if self.orientation.get() == "horizontal":
            card_width = 176
            gap = 10
            x = 12 + index * (card_width + gap) - gap // 2
            self.canvas.create_line(x, 12, x, 198, fill=self.colors["card_selected"], width=3, tags=("marker",))
        else:
            card_width = max(max(self.canvas.winfo_width(), 520) - 24, 420)
            card_height = 118
            gap = 10
            y = 12 + index * (card_height + gap) - gap // 2
            self.canvas.create_line(
                12,
                y,
                card_width + 12,
                y,
                fill=self.colors["card_selected"],
                width=3,
                tags=("marker",),
            )

    def _update_status(self) -> None:
        total = len(self.files)
        selected = self.selected_index is not None
        if total == 0:
            self.status.set("Add images or a folder to begin.")
        elif selected:
            self.status.set(
                f"{total} image{'s' if total != 1 else ''} ready. "
                f"Selected {self.selected_index + 1}."
            )
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

        if options.orientation == "vertical":
            output_width = max(image.width for image in prepared)
            output_height = sum(image.height for image in prepared)
        elif options.orientation == "horizontal":
            output_width = sum(image.width for image in prepared)
            output_height = max(image.height for image in prepared)
        else:
            raise ValueError(f"Unsupported stitch direction: {options.orientation}")

        has_alpha_output = any(image.mode == "RGBA" for image in prepared) and not options.white_background
        output_mode = "RGBA" if has_alpha_output else "RGB"
        background = (255, 255, 255, 0) if output_mode == "RGBA" else (255, 255, 255)
        result = Image.new(output_mode, (output_width, output_height), background)

        x = 0
        y = 0
        for image in prepared:
            paste_x = x
            paste_y = y
            if options.orientation == "vertical" and options.center_images:
                paste_x = (output_width - image.width) // 2
            elif options.orientation == "horizontal" and options.center_images:
                paste_y = (output_height - image.height) // 2

            paste_image = image
            if output_mode == "RGB" and image.mode == "RGBA":
                flattened = Image.new("RGB", image.size, (255, 255, 255))
                flattened.paste(image, mask=image.getchannel("A"))
                paste_image = flattened

            result.paste(paste_image, (paste_x, paste_y))
            if options.orientation == "vertical":
                y += image.height
            else:
                x += image.width

        options.output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(options.output_path, format="PNG", optimize=True)
    finally:
        for image in prepared:
            image.close()


def main() -> None:
    root = Tk()
    GramStitchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
