from __future__ import annotations

import json
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
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

from PIL import Image, ImageChops, ImageOps, ImageTk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


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
APP_VERSION = "0.2.0"
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
        "block_shadow": "#0b1020",
        "block_hover": "#1e293b",
        "badge": "#334155",
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
        "block_shadow": "#cbd5e1",
        "block_hover": "#f8fafc",
        "badge": "#e2e8f0",
    },
}
THUMBNAIL_SIZE = (96, 96)


@dataclass(frozen=True)
class StitchOptions:
    output_path: Path
    orientation: str
    center_images: bool
    white_background: bool
    auto_overlap: bool = False
    max_overlap: int = 300


@dataclass
class ImageItem:
    path: Path
    crop_top: int = 0
    crop_bottom: int = 0


class GramStitchApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(f"GramStitch {APP_VERSION}")
        self.root.geometry("820x560")
        self.root.minsize(720, 480)

        self.files: list[ImageItem] = []
        self.status = StringVar(value="Add images or a folder to begin.")
        self.theme_name = StringVar(value="dark")
        self.orientation = StringVar(value="horizontal")
        self.progress_text = StringVar(value="")
        self.crop_top = IntVar(value=0)
        self.crop_bottom = IntVar(value=0)
        self.auto_overlap = BooleanVar(value=False)
        self.final_preview = BooleanVar(value=False)
        self.advanced_visible = BooleanVar(value=False)
        self.advanced_label = StringVar(value="Advanced >")
        self.zoom_percent = IntVar(value=100)
        self.center_images = BooleanVar(value=True)
        self.white_background = BooleanVar(value=True)
        self.selected_index: int | None = None
        self.hover_index: int | None = None
        self.drag_index: int | None = None
        self.drag_target_index: int | None = None
        self.thumbnail_images: list[ImageTk.PhotoImage] = []
        self.final_preview_image: ImageTk.PhotoImage | None = None
        self.undo_stack: list[list[ImageItem]] = []
        self.redo_stack: list[list[ImageItem]] = []
        self.preview_origin_x = 18
        self.preview_origin_y = 18

        self._build_ui()
        self._bind_shortcuts()
        self._register_drop_target()
        self.root.after_idle(self._fit_window_to_content)

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
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.canvas.bind("<MouseWheel>", self._on_canvas_wheel)
        self.canvas.bind("<Configure>", lambda _event: self._refresh_preview())

        controls = ttk.Frame(content, padding=(12, 0, 0, 0), style="App.TFrame")
        controls.grid(row=0, column=1, sticky="ns")

        self._button(controls, "Add Folder", self.add_folder, "Primary.TButton").pack(fill="x", pady=(0, 6))
        self._button(controls, "Add Images", self.add_images).pack(fill="x", pady=6)
        self._button(controls, "Remove", self.remove_selected).pack(fill="x", pady=6)
        ttk.Separator(controls).pack(fill="x", pady=10)
        history_actions = ttk.Frame(controls, style="App.TFrame")
        history_actions.pack(fill="x", pady=(0, 6))
        self._button(history_actions, "Undo", self.undo).pack(side="left", fill="x", expand=True)
        self._button(history_actions, "Redo", self.redo).pack(side="left", fill="x", expand=True, padx=(6, 0))
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

        ttk.Checkbutton(
            options,
            text="Center images on cross-axis",
            variable=self.center_images,
            command=self._refresh_preview,
        ).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        ttk.Checkbutton(
            options,
            text="White background",
            variable=self.white_background,
            command=self._refresh_preview,
        ).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=2
        )

        zoom = ttk.Frame(options)
        zoom.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        zoom.columnconfigure(1, weight=1)
        self._button(zoom, "-", lambda: self.adjust_zoom(-25)).grid(row=0, column=0)
        ttk.Label(zoom, textvariable=self.zoom_percent, anchor="center").grid(row=0, column=1, sticky="ew")
        self._button(zoom, "+", lambda: self.adjust_zoom(25)).grid(row=0, column=2)

        self.advanced_button = ttk.Button(
            controls,
            textvariable=self.advanced_label,
            command=self.toggle_advanced,
        )
        self.advanced_button.pack(fill="x", pady=(0, 6))
        self.advanced_frame = ttk.LabelFrame(controls, text="Advanced", padding=10)
        self.advanced_frame.columnconfigure(1, weight=1)
        ttk.Label(self.advanced_frame, text="Selected crop top").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Spinbox(self.advanced_frame, from_=0, to=5000, textvariable=self.crop_top, width=8).grid(
            row=0, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        ttk.Label(self.advanced_frame, text="Selected crop bottom").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Spinbox(self.advanced_frame, from_=0, to=5000, textvariable=self.crop_bottom, width=8).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=2
        )
        self._button(self.advanced_frame, "Apply crop", self.apply_selected_crop).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(8, 2)
        )
        ttk.Checkbutton(
            self.advanced_frame,
            text="Remove exact overlaps",
            variable=self.auto_overlap,
            command=self._refresh_preview,
        ).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 8)
        )
        project_actions = ttk.Frame(self.advanced_frame)
        project_actions.grid(row=4, column=0, columnspan=2, sticky="ew")
        self._button(project_actions, "Open project", self.open_project).pack(side="left", fill="x", expand=True)
        self._button(project_actions, "Save project", self.save_project).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )

        self.back_button = self._button(controls, "Back to arrangement", self.show_arrangement)
        self.stitch_button = self._button(controls, "Preview", self.preview_or_save, "Primary.TButton")
        self.stitch_button.pack(fill="x")

        status_bar = ttk.Frame(main)
        status_bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        status_bar.columnconfigure(0, weight=1)

        ttk.Label(status_bar, textvariable=self.status, anchor="w", style="Status.TLabel").grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            status_bar,
            text="github.com/azeemulhassan",
            style="Link.TButton",
            command=lambda: webbrowser.open_new_tab(GITHUB_URL),
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ttk.Label(status_bar, textvariable=self.progress_text, anchor="e", style="Status.TLabel").grid(
            row=0, column=2, sticky="e", padx=(10, 0)
        )

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

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _event: self.add_images())
        self.root.bind("<Control-s>", lambda _event: self.save_project())
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-y>", lambda _event: self.redo())
        self.root.bind("<Delete>", lambda _event: self.remove_selected())
        self.root.bind("<Left>", lambda _event: self.move_selected(-1))
        self.root.bind("<Right>", lambda _event: self.move_selected(1))

    def _register_drop_target(self) -> None:
        if DND_FILES is None or not hasattr(self.canvas, "drop_target_register"):
            return
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind("<<Drop>>", self._on_files_dropped)

    def _on_files_dropped(self, event) -> None:
        paths = [Path(value) for value in self.root.tk.splitlist(event.data)]
        images: list[Path] = []
        for path in paths:
            if path.is_dir():
                images.extend(
                    item
                    for item in sorted(path.iterdir(), key=lambda candidate: candidate.name.lower())
                    if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
                )
            elif path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append(path)
        self._add_files(images)

    def _fit_window_to_content(self) -> None:
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = min(max(900, self.root.winfo_reqwidth()), max(720, screen_width - 80))
        height = min(max(640, self.root.winfo_reqheight()), max(540, screen_height - 100))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _snapshot(self) -> list[ImageItem]:
        return [ImageItem(item.path, item.crop_top, item.crop_bottom) for item in self.files]

    def _remember_state(self) -> None:
        self.undo_stack.append(self._snapshot())
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.redo_stack.append(self._snapshot())
        self.files = self.undo_stack.pop()
        self.selected_index = min(self.selected_index or 0, len(self.files) - 1) if self.files else None
        self._load_selected_crop()
        self._refresh_preview()

    def redo(self) -> None:
        if not self.redo_stack:
            return
        self.undo_stack.append(self._snapshot())
        self.files = self.redo_stack.pop()
        self.selected_index = min(self.selected_index or 0, len(self.files) - 1) if self.files else None
        self._load_selected_crop()
        self._refresh_preview()

    def save_project(self) -> None:
        output = filedialog.asksaveasfilename(
            title="Save GramStitch project",
            defaultextension=".json",
            filetypes=[("GramStitch project", "*.json")],
            initialfile="gramstitch-project.json",
        )
        if not output:
            return
        payload = {
            "version": 1,
            "orientation": self.orientation.get(),
            "center_images": bool(self.center_images.get()),
            "white_background": bool(self.white_background.get()),
            "auto_overlap": bool(self.auto_overlap.get()),
            "images": [
                {"path": str(item.path), "crop_top": item.crop_top, "crop_bottom": item.crop_bottom}
                for item in self.files
            ],
        }
        Path(output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status.set(f"Saved project {Path(output).name}.")

    def open_project(self) -> None:
        filename = filedialog.askopenfilename(
            title="Open GramStitch project",
            filetypes=[("GramStitch project", "*.json"), ("JSON file", "*.json")],
        )
        if not filename:
            return
        try:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            items = [
                ImageItem(
                    Path(entry["path"]),
                    max(0, int(entry.get("crop_top", 0))),
                    max(0, int(entry.get("crop_bottom", 0))),
                )
                for entry in payload.get("images", [])
            ]
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            messagebox.showerror("Open failed", f"Could not open project:\n{exc}")
            return
        self._remember_state()
        self.files = items
        self.orientation.set(payload.get("orientation", "horizontal"))
        self.center_images.set(bool(payload.get("center_images", True)))
        self.white_background.set(bool(payload.get("white_background", True)))
        self.auto_overlap.set(bool(payload.get("auto_overlap", False)))
        self.selected_index = 0 if self.files else None
        self._load_selected_crop()
        self._refresh_preview()
        self.status.set(f"Opened project {Path(filename).name}.")

    def apply_selected_crop(self) -> None:
        if self.selected_index is None:
            return
        try:
            top = max(0, int(self.crop_top.get()))
            bottom = max(0, int(self.crop_bottom.get()))
        except ValueError:
            messagebox.showerror("Invalid crop", "Crop values must be whole numbers.")
            return
        item = self.files[self.selected_index]
        if (top, bottom) == (item.crop_top, item.crop_bottom):
            return
        self._remember_state()
        item.crop_top = top
        item.crop_bottom = bottom
        self._refresh_preview()

    def _load_selected_crop(self) -> None:
        if self.selected_index is None:
            self.crop_top.set(0)
            self.crop_bottom.set(0)
            return
        item = self.files[self.selected_index]
        self.crop_top.set(item.crop_top)
        self.crop_bottom.set(item.crop_bottom)

    def adjust_zoom(self, amount: int) -> None:
        self.zoom_percent.set(max(25, min(200, self.zoom_percent.get() + amount)))
        self._refresh_preview()

    def preview_or_save(self) -> None:
        if self.final_preview.get():
            self.stitch()
        else:
            self.show_final_preview()

    def show_final_preview(self) -> None:
        if not self.files:
            messagebox.showwarning("No images", "Add at least one image first.")
            return
        self.final_preview.set(True)
        self.stitch_button.configure(text="Save PNG")
        self.back_button.pack(fill="x", pady=(4, 6), before=self.stitch_button)
        self._refresh_preview()
        self.status.set("Final preview fitted to the playfield.")

    def show_arrangement(self) -> None:
        if self.final_preview.get():
            self.final_preview.set(False)
            self.stitch_button.configure(text="Preview")
            self.back_button.pack_forget()
            self._refresh_preview()

    def toggle_advanced(self) -> None:
        visible = not self.advanced_visible.get()
        self.advanced_visible.set(visible)
        self.advanced_label.set("Advanced v" if visible else "Advanced >")
        if visible:
            self.advanced_frame.pack(fill="x", pady=(0, 10), before=self.stitch_button)
        else:
            self.advanced_frame.pack_forget()
        self.root.after_idle(self._fit_window_to_content)

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
        self.show_arrangement()
        existing = {item.path.resolve() for item in self.files}
        new_items: list[ImageItem] = []

        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in existing:
                continue
            new_items.append(ImageItem(path))
            existing.add(resolved)
        added = len(new_items)
        if added:
            self._remember_state()
            self.files.extend(new_items)

        if added and self.selected_index is None:
            self.selected_index = 0
        if added:
            self._load_selected_crop()
        self._refresh_preview()
        self.status.set(f"Added {added} image{'s' if added != 1 else ''}.")

    def remove_selected(self) -> None:
        if self.selected_index is None:
            return

        self.show_arrangement()
        self._remember_state()
        del self.files[self.selected_index]
        if not self.files:
            self.selected_index = None
        else:
            self.selected_index = min(self.selected_index, len(self.files) - 1)
        self._load_selected_crop()
        self._refresh_preview()

    def move_selected(self, direction: int) -> None:
        if self.selected_index is None:
            return

        self.show_arrangement()
        target = self.selected_index + direction
        if target < 0 or target >= len(self.files):
            return

        self._remember_state()
        self.files[self.selected_index], self.files[target] = self.files[target], self.files[self.selected_index]
        self.selected_index = target
        self._refresh_preview()

    def sort_files(self) -> None:
        self.show_arrangement()
        self._remember_state()
        self.files.sort(key=lambda item: item.path.name.lower())
        self.selected_index = 0 if self.files else None
        self._load_selected_crop()
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
                center_images=bool(self.center_images.get()),
                white_background=bool(self.white_background.get()),
                auto_overlap=bool(self.auto_overlap.get()),
            )
        except ValueError:
            messagebox.showerror("Invalid crop", "Crop values must be whole numbers.")
            return

        width, height = estimate_output_size(self.files, options)
        if (width > 50000 or height > 50000 or width * height > 200_000_000) and not messagebox.askyesno(
            "Large output",
            f"The stitched image will be about {width:,} x {height:,} pixels.\n\nContinue exporting?",
        ):
            return

        self._set_busy(True)
        worker = threading.Thread(target=self._stitch_worker, args=(self.files.copy(), options), daemon=True)
        worker.start()

    def _stitch_worker(self, files: list[ImageItem], options: StitchOptions) -> None:
        try:
            stitch_images(files, options, self._report_progress)
        except Exception as exc:
            self.root.after(0, lambda: self._finish_stitch(error=exc))
        else:
            self.root.after(0, lambda: self._finish_stitch(output_path=options.output_path))

    def _report_progress(self, percent: int) -> None:
        self.root.after(0, lambda: self.progress_text.set(f"{percent}%"))

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
            self.progress_text.set("0%")
        else:
            self.progress_text.set("")

    def _refresh_preview(self) -> None:
        if not hasattr(self, "canvas"):
            return

        self.canvas.delete("all")
        self.thumbnail_images.clear()

        if not self.files:
            canvas_width = max(self.canvas.winfo_width(), 520)
            canvas_height = max(self.canvas.winfo_height(), 340)
            self.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="Add images to preview and arrange them here",
                fill=self.colors["muted"],
                font=("Segoe UI", 13, "bold"),
            )
            self.canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
            self._update_status()
            return

        if self.final_preview.get():
            self._draw_final_preview()
            self._update_status()
            return

        if self.orientation.get() == "horizontal":
            self._draw_horizontal_preview()
        else:
            self._draw_vertical_preview()

        self._update_status()

    def _draw_final_preview(self) -> None:
        canvas_width = max(self.canvas.winfo_width(), 520)
        canvas_height = max(self.canvas.winfo_height(), 340)
        options = StitchOptions(
            output_path=Path("preview.png"),
            orientation=self.orientation.get(),
            center_images=bool(self.center_images.get()),
            white_background=bool(self.white_background.get()),
            auto_overlap=bool(self.auto_overlap.get()),
        )
        try:
            result = build_stitched_image(self.files, options)
            available_width = max(1, canvas_width - 36)
            available_height = max(1, canvas_height - 36)
            fit_scale = min(available_width / result.width, available_height / result.height, 1.0)
            scale = fit_scale * (self.zoom_percent.get() / 100)
            width = max(1, round(result.width * scale))
            height = max(1, round(result.height * scale))
            rendered = result.resize((width, height), Image.Resampling.LANCZOS)
            self.final_preview_image = ImageTk.PhotoImage(rendered)
        except Exception as exc:
            self.canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text=f"Preview unavailable\n{exc}",
                fill=self.colors["muted"],
                font=("Segoe UI", 11, "bold"),
                justify="center",
            )
            return
        finally:
            if "result" in locals():
                result.close()

        self.preview_origin_x = max(18, (canvas_width - width) // 2)
        self.preview_origin_y = max(18, (canvas_height - height) // 2)
        self.canvas.create_image(
            self.preview_origin_x,
            self.preview_origin_y,
            image=self.final_preview_image,
            anchor="nw",
        )
        self.canvas.create_text(
            self.preview_origin_x,
            self.preview_origin_y - 8,
            text=f"Fit preview: {result.width:,} x {result.height:,} output pixels",
            fill=self.colors["muted"],
            font=("Segoe UI", 9),
            anchor="sw",
        )
        self.canvas.configure(
            scrollregion=(
                0,
                0,
                max(canvas_width, self.preview_origin_x + width + 18),
                max(canvas_height, self.preview_origin_y + height + 18),
            )
        )

    def _draw_vertical_preview(self) -> None:
        canvas_width = max(self.canvas.winfo_width(), 520)
        canvas_height = max(self.canvas.winfo_height(), 340)
        card_width = max(canvas_width - 36, 420)
        card_height = 124
        gap = 16
        content_height = len(self.files) * card_height + max(0, len(self.files) - 1) * gap
        self.preview_origin_x = max(18, (canvas_width - card_width) // 2)
        self.preview_origin_y = max(18, (canvas_height - content_height) // 2)
        y = self.preview_origin_y

        for index, item in enumerate(self.files):
            self._draw_card(index, item, self.preview_origin_x, y, card_width, card_height)
            y += card_height + gap

        self.canvas.configure(
            scrollregion=(
                0,
                0,
                max(canvas_width, self.preview_origin_x + card_width + 18),
                max(canvas_height, self.preview_origin_y + content_height + 18),
            )
        )

    def _draw_horizontal_preview(self) -> None:
        canvas_width = max(self.canvas.winfo_width(), 520)
        canvas_height = max(self.canvas.winfo_height(), 340)
        card_width = 180
        card_height = 190
        gap = 16
        content_width = len(self.files) * card_width + max(0, len(self.files) - 1) * gap
        self.preview_origin_x = max(18, (canvas_width - content_width) // 2)
        self.preview_origin_y = max(18, (canvas_height - card_height) // 2)
        x = self.preview_origin_x

        for index, item in enumerate(self.files):
            self._draw_card(index, item, x, self.preview_origin_y, card_width, card_height, compact=True)
            x += card_width + gap

        self.canvas.configure(
            scrollregion=(
                0,
                0,
                max(canvas_width, self.preview_origin_x + content_width + 18),
                max(canvas_height, self.preview_origin_y + card_height + 18),
            )
        )

    def _draw_card(
        self,
        index: int,
        item: ImageItem,
        x: int,
        y: int,
        width: int,
        height: int,
        compact: bool = False,
    ) -> None:
        selected = index == self.selected_index
        hovered = index == self.hover_index
        dragging = index == self.drag_index
        colors = self.colors
        border = colors["card_selected"] if selected else colors["card_border"]
        fill = colors["block_hover"] if hovered or dragging else colors["card"]
        tag = f"card:{index}"

        self.canvas.create_rectangle(
            x + 4,
            y + 5,
            x + width + 4,
            y + height + 5,
            fill=colors["block_shadow"],
            outline="",
            tags=(tag, "card"),
        )
        self.canvas.create_rectangle(
            x,
            y,
            x + width,
            y + height,
            fill=fill,
            outline=border,
            width=3 if dragging else 2 if selected else 1,
            tags=(tag, "card"),
        )
        self._draw_block_connectors(index, x, y, width, height, fill, border, tag)
        self._draw_order_badge(index, x, y, tag)

        thumb = self._make_thumbnail(item)
        self.thumbnail_images.append(thumb)

        if compact:
            thumb_x = x + (width - THUMBNAIL_SIZE[0]) // 2
            thumb_y = y + 24
            text_x = x + 14
            text_y = thumb_y + THUMBNAIL_SIZE[1] + 16
            self.canvas.create_image(thumb_x, thumb_y, image=thumb, anchor="nw", tags=(tag, "card"))
            self.canvas.create_text(
                text_x,
                text_y,
                text=f"{index + 1:02d}. {item.path.name}",
                fill=colors["text"],
                font=("Segoe UI", 9, "bold"),
                anchor="nw",
                width=width - 28,
                tags=(tag, "card"),
            )
        else:
            thumb_x = x + 14
            thumb_y = y + 15
            self.canvas.create_image(thumb_x, thumb_y, image=thumb, anchor="nw", tags=(tag, "card"))
            self.canvas.create_text(
                x + 128,
                y + 32,
                text=item.path.name,
                fill=colors["text"],
                font=("Segoe UI", 11, "bold"),
                anchor="nw",
                width=max(width - 154, 160),
                tags=(tag, "card"),
            )
            self.canvas.create_text(
                x + 128,
                y + 58,
                text=f"{item.path.parent}\nCrop {item.crop_top}px / {item.crop_bottom}px",
                fill=colors["muted"],
                font=("Segoe UI", 9),
                anchor="nw",
                width=max(width - 154, 160),
                tags=(tag, "card"),
            )

    def _draw_block_connectors(
        self,
        index: int,
        x: int,
        y: int,
        width: int,
        height: int,
        fill: str,
        border: str,
        tag: str,
    ) -> None:
        tab_width = 48
        tab_depth = 10

        if self.orientation.get() == "horizontal":
            tab_y = y + (height - tab_width) // 2
            if index > 0:
                self.canvas.create_rectangle(
                    x,
                    tab_y,
                    x + tab_depth,
                    tab_y + tab_width,
                    fill=self.colors["panel"],
                    outline=border,
                    tags=(tag, "card"),
                )
            if index < len(self.files) - 1:
                self.canvas.create_rectangle(
                    x + width,
                    tab_y,
                    x + width + tab_depth,
                    tab_y + tab_width,
                    fill=fill,
                    outline=border,
                    tags=(tag, "card"),
                )
        else:
            tab_x = x + (width - tab_width) // 2
            if index > 0:
                self.canvas.create_rectangle(
                    tab_x,
                    y,
                    tab_x + tab_width,
                    y + tab_depth,
                    fill=self.colors["panel"],
                    outline=border,
                    tags=(tag, "card"),
                )
            if index < len(self.files) - 1:
                self.canvas.create_rectangle(
                    tab_x,
                    y + height,
                    tab_x + tab_width,
                    y + height + tab_depth,
                    fill=fill,
                    outline=border,
                    tags=(tag, "card"),
                )

    def _draw_order_badge(self, index: int, x: int, y: int, tag: str) -> None:
        colors = self.colors
        self.canvas.create_oval(
            x + 10,
            y + 10,
            x + 34,
            y + 34,
            fill=colors["badge"],
            outline=colors["card_border"],
            tags=(tag, "card"),
        )
        self.canvas.create_text(
            x + 22,
            y + 22,
            text=str(index + 1),
            fill=colors["text"],
            font=("Segoe UI", 8, "bold"),
            tags=(tag, "card"),
        )

    def _make_thumbnail(self, item: ImageItem) -> ImageTk.PhotoImage:
        try:
            with Image.open(item.path) as image:
                image = crop_image(image, item)
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
        self._load_selected_crop()
        self._refresh_preview()

    def _on_canvas_motion(self, event) -> None:
        if self.drag_index is not None:
            return

        index = self._event_index(event)
        if index == self.hover_index:
            return

        self.hover_index = index
        self.canvas.configure(cursor="hand2" if index is not None else "")
        self._refresh_preview()

    def _on_canvas_leave(self, _event) -> None:
        if self.drag_index is not None or self.hover_index is None:
            return

        self.hover_index = None
        self.canvas.configure(cursor="")
        self._refresh_preview()

    def _on_canvas_wheel(self, event) -> None:
        steps = -1 if event.delta > 0 else 1
        if self.orientation.get() == "horizontal":
            self.canvas.xview_scroll(steps, "units")
        else:
            self.canvas.yview_scroll(steps, "units")

    def _on_canvas_drag(self, event) -> None:
        if self.drag_index is None:
            return

        self.canvas.configure(cursor="fleur")
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
        self.canvas.configure(cursor="hand2")

        if target != source:
            self._remember_state()
            item = self.files.pop(source)
            if target > source:
                target -= 1
            self.files.insert(target, item)
            self.selected_index = target
            self._load_selected_crop()

        self._refresh_preview()

    def _event_index(self, event) -> int | None:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        items = self.canvas.find_overlapping(x, y, x, y)
        if not items:
            return None

        for item in reversed(items):
            for tag in self.canvas.gettags(item):
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
            card_width = 180
            gap = 16
            index = round((x - self.preview_origin_x) / (card_width + gap))
        else:
            card_height = 124
            gap = 16
            index = round((y - self.preview_origin_y) / (card_height + gap))

        return max(0, min(index, len(self.files)))

    def _draw_insertion_marker(self, index: int | None) -> None:
        if index is None:
            return

        if self.orientation.get() == "horizontal":
            card_width = 180
            gap = 16
            x = self.preview_origin_x + index * (card_width + gap) - gap // 2
            self.canvas.create_line(
                x,
                self.preview_origin_y,
                x,
                self.preview_origin_y + 190,
                fill=self.colors["card_selected"],
                width=4,
                tags=("marker",),
            )
        else:
            card_width = max(max(self.canvas.winfo_width(), 520) - 36, 420)
            card_height = 124
            gap = 16
            y = self.preview_origin_y + index * (card_height + gap) - gap // 2
            self.canvas.create_line(
                self.preview_origin_x,
                y,
                self.preview_origin_x + card_width,
                y,
                fill=self.colors["card_selected"],
                width=4,
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


def crop_image(image: Image.Image, item: ImageItem) -> Image.Image:
    top = min(item.crop_top, image.height)
    bottom = max(top, image.height - item.crop_bottom)
    cropped = image.crop((0, top, image.width, bottom))
    if cropped.height <= 0 or cropped.width <= 0:
        raise ValueError(f"Crop removed all pixels from {item.path.name}.")
    return cropped


def detect_exact_overlap(previous: Image.Image, current: Image.Image, orientation: str, limit: int) -> int:
    if orientation == "vertical" and previous.width != current.width:
        return 0
    if orientation == "horizontal" and previous.height != current.height:
        return 0

    maximum = min(
        limit,
        previous.height if orientation == "vertical" else previous.width,
        current.height if orientation == "vertical" else current.width,
    )
    for amount in range(maximum, 0, -1):
        if orientation == "vertical":
            first = previous.crop((0, previous.height - amount, previous.width, previous.height))
            second = current.crop((0, 0, current.width, amount))
        else:
            first = previous.crop((previous.width - amount, 0, previous.width, previous.height))
            second = current.crop((0, 0, amount, current.height))
        if ImageChops.difference(first.convert("RGB"), second.convert("RGB")).getbbox() is None:
            return amount
    return 0


def estimate_output_size(items: list[ImageItem], options: StitchOptions) -> tuple[int, int]:
    sizes: list[tuple[int, int]] = []
    for item in items:
        with Image.open(item.path) as image:
            height = image.height - min(item.crop_top, image.height) - min(item.crop_bottom, image.height)
            if height <= 0:
                raise ValueError(f"Crop removed all pixels from {item.path.name}.")
            sizes.append((image.width, height))
    if options.orientation == "vertical":
        return max(width for width, _height in sizes), sum(height for _width, height in sizes)
    return sum(width for width, _height in sizes), max(height for _width, height in sizes)


def build_stitched_image(
    items: list[ImageItem],
    options: StitchOptions,
    progress_callback: Callable[[int], None] | None = None,
) -> Image.Image:
    prepared: list[Image.Image] = []
    overlaps: list[int] = []

    def report(percent: int) -> None:
        if progress_callback is not None:
            progress_callback(percent)

    report(0)
    for index, item in enumerate(items):
        with Image.open(item.path) as source:
            source.load()
            image = crop_image(source, item)
            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            prepared.append(image.convert("RGBA" if has_alpha else "RGB"))
        report(round(((index + 1) / len(items)) * 50))

    if not prepared:
        raise ValueError("No readable images were selected.")
    if options.orientation not in {"vertical", "horizontal"}:
        raise ValueError(f"Unsupported stitch direction: {options.orientation}")

    overlaps = [0]
    for index in range(1, len(prepared)):
        overlaps.append(
            detect_exact_overlap(prepared[index - 1], prepared[index], options.orientation, options.max_overlap)
            if options.auto_overlap
            else 0
        )

    if options.orientation == "vertical":
        output_width = max(image.width for image in prepared)
        output_height = sum(image.height for image in prepared) - sum(overlaps)
    else:
        output_width = sum(image.width for image in prepared) - sum(overlaps)
        output_height = max(image.height for image in prepared)

    has_alpha_output = any(image.mode == "RGBA" for image in prepared) and not options.white_background
    output_mode = "RGBA" if has_alpha_output else "RGB"
    background = (255, 255, 255, 0) if output_mode == "RGBA" else (255, 255, 255)
    result = Image.new(output_mode, (output_width, output_height), background)

    x = 0
    y = 0
    for index, image in enumerate(prepared):
        if options.orientation == "vertical":
            y -= overlaps[index]
        else:
            x -= overlaps[index]
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
        report(50 + round(((index + 1) / len(prepared)) * 45))

    for image in prepared:
        image.close()
    return result


def stitch_images(
    items: list[ImageItem],
    options: StitchOptions,
    progress_callback: Callable[[int], None] | None = None,
) -> None:
    result = build_stitched_image(items, options, progress_callback)
    try:
        options.output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(options.output_path, format="PNG", optimize=True)
        if progress_callback is not None:
            progress_callback(100)
    finally:
        result.close()


def main() -> None:
    root = TkinterDnD.Tk() if TkinterDnD is not None else Tk()
    GramStitchApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
