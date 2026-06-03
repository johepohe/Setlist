#!/usr/bin/env python3
"""Simple fullscreen PDF setlist viewer."""

from __future__ import annotations

import json
import locale
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any


SOURCE_DIR = Path(__file__).resolve().parent


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_user_data_dir() -> Path:
    if not is_packaged():
        return SOURCE_DIR

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "Setlist"


APP_DIR = Path(sys.executable).resolve().parent if is_packaged() else SOURCE_DIR
SETLISTS_FILE = get_user_data_dir() / "setlists.json"


def restart_in_local_venv() -> None:
    if Path(sys.argv[0]).resolve() != Path(__file__).resolve():
        return

    venv_dir = Path(__file__).resolve().parent / ".venv"
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists() and Path(sys.prefix).resolve() != venv_dir.resolve():
        os.execv(venv_python, [str(venv_python), *sys.argv])


restart_in_local_venv()

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - handled in main()
    try:
        import fitz  # type: ignore[no-redef]
    except ImportError:
        fitz = None


class SetlistApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Setlist")
        self.root.geometry("900x650")
        self.root.minsize(480, 320)

        self.folder_path: Path | None = None
        self.available_pdf_files: list[Path] = []
        self.setlist_pdf_files: list[Path] = []
        self.viewer_pdf_files: list[Path] = []
        self.current_setlist_name: str | None = None
        self.annotations: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
        self.saved_setlists: dict[str, list[Path]] = self.load_setlists()
        self.current_index: int | None = None
        self.current_page_index = 0
        self.current_document: fitz.Document | None = None
        self.current_photo: tk.PhotoImage | None = None
        self.view_orientation = tk.StringVar(value="portrait")
        self.fullscreen = False
        self.viewer_is_setlist = False
        self.annotation_mode = False
        self.current_stroke_points: list[tuple[float, float]] = []
        self.current_stroke_item: int | None = None
        self.current_render_bounds: tuple[float, float, float, float] | None = None
        self.current_render_rotation = 0
        self.render_after_id: str | None = None

        self._build_menu()
        self._build_list_view()
        self._bind_keys()

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        self.menu_bar = menu_bar
        archive_menu = tk.Menu(menu_bar, tearoff=False)
        archive_menu.add_command(label="Öppna folder med PDF...", command=self.open_folder)
        archive_menu.add_separator()
        archive_menu.add_command(label="Avsluta", command=self.root.destroy)
        menu_bar.add_cascade(label="Arkiv", menu=archive_menu)

        self.setlist_menu = tk.Menu(menu_bar, tearoff=False)
        self.setlist_menu.add_command(label="Ny setlist...", command=self.new_setlist)
        self.setlist_menu.add_command(label="Spara setlist", command=self.save_current_setlist)
        self.setlist_menu.add_command(label="Byt namn på setlist...", command=self.rename_saved_setlist)
        self.setlist_menu.add_command(label="Anteckningsläge", command=self.toggle_annotation_mode)
        self.setlist_menu.add_command(label="Ångra senaste anteckning", command=self.undo_last_annotation)
        self.setlist_menu.add_command(label="Ta bort anteckning", command=self.delete_current_page_annotations)
        self.setlist_menu.add_separator()
        self.saved_setlists_menu = tk.Menu(self.setlist_menu, tearoff=False)
        self.setlist_menu.add_cascade(label="Sparade", menu=self.saved_setlists_menu)
        menu_bar.add_cascade(label="Setlist", menu=self.setlist_menu)
        self.refresh_saved_setlists_menu()

        self.setlist_name_menu_index = menu_bar.index(tk.END) + 1
        menu_bar.add_command(label="Ingen setlist", state=tk.DISABLED)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        view_menu.add_radiobutton(
            label="Stående",
            variable=self.view_orientation,
            value="portrait",
            command=self.set_view_orientation,
        )
        view_menu.add_radiobutton(
            label="Liggande",
            variable=self.view_orientation,
            value="landscape",
            command=self.set_view_orientation,
        )
        menu_bar.add_cascade(label="Vy", menu=view_menu)

        self.root.config(menu=menu_bar)

    def _build_list_view(self) -> None:
        self.main_frame = ttk.Frame(self.root, padding=16)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.folder_label = ttk.Label(
            self.main_frame,
            text="Välj Arkiv -> Öppna folder med PDF...",
            anchor=tk.W,
        )
        self.folder_label.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            self.main_frame,
            text="",
            anchor=tk.W,
        )
        self.status_label.pack(fill=tk.X, pady=(0, 10))

        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        content_frame.columnconfigure(0, weight=1)
        content_frame.columnconfigure(2, weight=1)
        content_frame.rowconfigure(1, weight=1)

        ttk.Label(content_frame, text="Titlar").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(content_frame, text="Setlist").grid(row=0, column=2, sticky=tk.W)

        available_frame = ttk.Frame(content_frame)
        available_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        setlist_frame = ttk.Frame(content_frame)
        setlist_frame.grid(row=1, column=2, sticky="nsew", pady=(4, 0))

        self.title_list = tk.Listbox(
            available_frame,
            activestyle="none",
            bg="white",
            fg="black",
            font=("TkDefaultFont", 15),
            exportselection=False,
            selectbackground="#2d79ff",
            selectforeground="white",
        )
        self.title_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.title_list.bind("<Return>", self.show_selected_pdf)
        self.title_list.bind("<Double-Button-1>", self.add_selected_title)

        scrollbar = ttk.Scrollbar(available_frame, orient=tk.VERTICAL, command=self.title_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.title_list.config(yscrollcommand=scrollbar.set)

        control_frame = ttk.Frame(content_frame)
        control_frame.grid(row=1, column=1, sticky="ns", padx=12, pady=(4, 0))
        ttk.Button(control_frame, text="Lägg till >",
                   command=self.add_selected_title).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(control_frame, text="< Ta bort",
                   command=self.remove_selected_setlist_title).pack(fill=tk.X, pady=(0, 18))
        ttk.Button(control_frame, text="Upp",
                   command=lambda: self.move_selected_setlist_title(-1)).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(control_frame, text="Ner",
                   command=lambda: self.move_selected_setlist_title(1)).pack(fill=tk.X)

        self.setlist_list = tk.Listbox(
            setlist_frame,
            activestyle="none",
            bg="white",
            fg="black",
            font=("TkDefaultFont", 15),
            exportselection=False,
            selectbackground="#2d79ff",
            selectforeground="white",
        )
        self.setlist_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.setlist_list.bind("<Return>", self.show_selected_setlist_pdf)
        self.setlist_list.bind("<Double-Button-1>", self.show_selected_setlist_pdf)
        self.setlist_list.bind("<Delete>", self.remove_selected_setlist_title)

        setlist_scrollbar = ttk.Scrollbar(setlist_frame, orient=tk.VERTICAL, command=self.setlist_list.yview)
        setlist_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.setlist_list.config(yscrollcommand=setlist_scrollbar.set)

    def _bind_keys(self) -> None:
        self.root.bind("<Escape>", lambda _event: self.exit_fullscreen())
        self.root.bind("<Left>", lambda _event: self.show_previous_page())
        self.root.bind("<Right>", lambda _event: self.show_next_page())
        self.root.bind("<space>", lambda _event: self.show_next_page())
        self.root.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.root.bind("s", lambda _event: self.set_view_orientation("portrait"))
        self.root.bind("l", lambda _event: self.set_view_orientation("landscape"))
        self.root.bind("a", lambda _event: self.toggle_annotation_mode())
        self.root.bind("<Control-z>", lambda _event: self.undo_last_annotation())

    def open_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Välj folder med PDF-filer",
            initialdir=APP_DIR,
        )
        if not folder:
            return

        folder_path = Path(folder)
        self.folder_path = folder_path
        self.available_pdf_files = self.find_pdf_files(folder_path)
        self.current_index = None
        self.close_current_document()
        self.refresh_available_list()

        self.folder_label.config(text=str(folder_path))
        self.update_status()
        self.root.deiconify()
        self.root.lift()
        self.title_list.focus_set()

        if not self.available_pdf_files:
            messagebox.showinfo("Inga PDF-filer", "Foldern innehåller inga PDF-filer.")
        else:
            self.title_list.selection_set(0)
            self.title_list.see(0)

    def find_pdf_files(self, folder_path: Path) -> list[Path]:
        pdf_files = [
            path
            for path in folder_path.rglob("*")
            if path.is_file() and path.suffix.lower() == ".pdf" and ".venv" not in path.parts
        ]
        return sorted(
            pdf_files,
            key=lambda path: locale.strxfrm(str(path.relative_to(folder_path)).casefold()),
        )

    def get_display_title(self, folder_path: Path, pdf_file: Path) -> str:
        relative_path = pdf_file.relative_to(folder_path)
        if len(relative_path.parts) == 1:
            return pdf_file.stem
        return str(relative_path.with_suffix(""))

    def get_title(self, pdf_file: Path) -> str:
        if self.folder_path:
            try:
                return self.get_display_title(self.folder_path, pdf_file)
            except ValueError:
                pass
        return pdf_file.stem

    def refresh_available_list(self) -> None:
        self.title_list.delete(0, tk.END)
        for pdf_file in self.available_pdf_files:
            self.title_list.insert(tk.END, self.get_title(pdf_file))

    def refresh_setlist_view(self, selected_index: int | None = None) -> None:
        self.setlist_list.delete(0, tk.END)
        for pdf_file in self.setlist_pdf_files:
            self.setlist_list.insert(tk.END, self.get_title(pdf_file))
        if selected_index is not None and self.setlist_pdf_files:
            selected_index = max(0, min(selected_index, len(self.setlist_pdf_files) - 1))
            self.setlist_list.selection_set(selected_index)
            self.setlist_list.see(selected_index)
        self.update_status()

    def update_status(self) -> None:
        pdf_count = len(self.available_pdf_files)
        setlist_count = len(self.setlist_pdf_files)
        setlist_name = self.current_setlist_name or "Ingen setlist"
        self.status_label.config(
            text=f"{pdf_count} PDF-filer. {setlist_name}: {setlist_count} titlar."
        )
        if hasattr(self, "setlist_name_menu_index"):
            self.menu_bar.entryconfig(self.setlist_name_menu_index, label=f"     {setlist_name}     ")

    def load_setlists(self) -> dict[str, list[Path]]:
        if not SETLISTS_FILE.exists():
            return {}
        try:
            data = json.loads(SETLISTS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        raw_setlists = data.get("setlists", {})
        if not isinstance(raw_setlists, dict):
            return {}

        setlists: dict[str, list[Path]] = {}
        for name, paths in raw_setlists.items():
            if isinstance(name, str) and isinstance(paths, list):
                setlists[name] = [Path(path) for path in paths if isinstance(path, str)]
        self.annotations = self.parse_annotations(data.get("annotations", {}))
        return setlists

    def parse_annotations(self, raw_annotations: object) -> dict[str, dict[str, dict[str, list[dict[str, Any]]]]]:
        if not isinstance(raw_annotations, dict):
            return {}

        annotations: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = {}
        for setlist_name, pdf_notes in raw_annotations.items():
            if not isinstance(setlist_name, str) or not isinstance(pdf_notes, dict):
                continue
            valid_pdf_notes: dict[str, dict[str, list[dict[str, Any]]]] = {}
            for pdf_path, page_notes in pdf_notes.items():
                if not isinstance(pdf_path, str) or not isinstance(page_notes, dict):
                    continue
                valid_page_notes: dict[str, list[dict[str, Any]]] = {}
                for page_number, strokes in page_notes.items():
                    if isinstance(page_number, str) and isinstance(strokes, list):
                        valid_strokes = [
                            stroke
                            for stroke in strokes
                            if isinstance(stroke, dict) and isinstance(stroke.get("points"), list)
                        ]
                        if valid_strokes:
                            valid_page_notes[page_number] = valid_strokes
                if valid_page_notes:
                    valid_pdf_notes[pdf_path] = valid_page_notes
            if valid_pdf_notes:
                annotations[setlist_name] = valid_pdf_notes
        return annotations

    def write_setlists(self) -> None:
        data = {
            "setlists": {
                name: [str(path) for path in paths]
                for name, paths in sorted(self.saved_setlists.items())
            },
            "annotations": self.annotations,
        }
        SETLISTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETLISTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def refresh_saved_setlists_menu(self) -> None:
        self.saved_setlists_menu.delete(0, tk.END)
        if not self.saved_setlists:
            self.saved_setlists_menu.add_command(label="Inga sparade", state=tk.DISABLED)
            return
        for name in sorted(self.saved_setlists):
            self.saved_setlists_menu.add_command(
                label=name,
                command=lambda setlist_name=name: self.load_saved_setlist(setlist_name),
            )

    def show_selected_pdf(self, _event: tk.Event | None = None) -> None:
        selection = self.title_list.curselection()
        if not selection:
            return
        self.show_pdf(selection[0], self.available_pdf_files, viewer_is_setlist=False)

    def show_selected_setlist_pdf(self, _event: tk.Event | None = None) -> None:
        selection = self.setlist_list.curselection()
        if not selection:
            return
        self.show_pdf(selection[0], self.setlist_pdf_files, viewer_is_setlist=True)

    def new_setlist(self) -> None:
        name = simpledialog.askstring("Ny setlist", "Namn på setlist:")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        self.current_setlist_name = name
        self.setlist_pdf_files = []
        self.refresh_setlist_view()

    def load_saved_setlist(self, name: str) -> None:
        self.current_setlist_name = name
        self.setlist_pdf_files = list(self.saved_setlists.get(name, []))
        self.current_index = None
        self.viewer_is_setlist = True
        self.close_current_document()
        self.refresh_setlist_view(0 if self.setlist_pdf_files else None)
        if self.setlist_pdf_files:
            self.show_pdf(0, self.setlist_pdf_files, viewer_is_setlist=True)

    def save_current_setlist(self) -> None:
        if self.current_setlist_name is None:
            name = simpledialog.askstring("Spara setlist", "Namn på setlist:")
            if not name:
                return
            self.current_setlist_name = name.strip()
        if not self.current_setlist_name:
            self.current_setlist_name = None
            return

        self.saved_setlists[self.current_setlist_name] = list(self.setlist_pdf_files)
        try:
            self.write_setlists()
        except OSError as exc:
            messagebox.showerror("Kunde inte spara setlist", str(exc))
            return
        self.refresh_saved_setlists_menu()
        self.update_status()

    def rename_saved_setlist(self) -> None:
        if not self.saved_setlists:
            messagebox.showinfo("Byt namn på setlist", "Det finns inga sparade setlists.")
            return

        old_name = self.current_setlist_name
        if old_name not in self.saved_setlists:
            old_name = simpledialog.askstring("Byt namn på setlist", "Nuvarande namn:")
            if not old_name:
                return
            old_name = old_name.strip()

        if not old_name:
            return
        if old_name not in self.saved_setlists:
            messagebox.showerror("Byt namn på setlist", f"'{old_name}' finns inte.")
            return

        new_name = simpledialog.askstring(
            "Byt namn på setlist",
            "Nytt namn:",
            initialvalue=old_name,
        )
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        if new_name in self.saved_setlists:
            messagebox.showerror("Byt namn på setlist", f"'{new_name}' finns redan.")
            return

        self.saved_setlists[new_name] = self.saved_setlists.pop(old_name)
        if old_name in self.annotations:
            self.annotations[new_name] = self.annotations.pop(old_name)
        if self.current_setlist_name == old_name:
            self.current_setlist_name = new_name

        try:
            self.write_setlists()
        except OSError as exc:
            self.saved_setlists[old_name] = self.saved_setlists.pop(new_name)
            if new_name in self.annotations:
                self.annotations[old_name] = self.annotations.pop(new_name)
            if self.current_setlist_name == new_name:
                self.current_setlist_name = old_name
            messagebox.showerror("Kunde inte byta namn på setlist", str(exc))
            return

        self.refresh_saved_setlists_menu()
        self.update_status()

    def add_selected_title(self, _event: tk.Event | None = None) -> None:
        if self.current_setlist_name is None:
            self.new_setlist()
            if self.current_setlist_name is None:
                return

        selection = self.title_list.curselection()
        if not selection:
            return
        pdf_file = self.available_pdf_files[selection[0]]
        self.setlist_pdf_files.append(pdf_file)
        self.refresh_setlist_view(len(self.setlist_pdf_files) - 1)

    def remove_selected_setlist_title(self, _event: tk.Event | None = None) -> None:
        selection = self.setlist_list.curselection()
        if not selection:
            return
        index = selection[0]
        del self.setlist_pdf_files[index]
        self.refresh_setlist_view(index if self.setlist_pdf_files else None)

    def move_selected_setlist_title(self, direction: int) -> None:
        selection = self.setlist_list.curselection()
        if not selection:
            return
        index = selection[0]
        new_index = index + direction
        if not (0 <= new_index < len(self.setlist_pdf_files)):
            return
        self.setlist_pdf_files[index], self.setlist_pdf_files[new_index] = (
            self.setlist_pdf_files[new_index],
            self.setlist_pdf_files[index],
        )
        self.refresh_setlist_view(new_index)

    def set_view_orientation(self, orientation: str | None = None) -> None:
        if orientation is not None:
            self.view_orientation.set(orientation)
        self.render_current_pdf()
        self.focus_viewer()
        self.root.after_idle(self.focus_viewer)

    def show_pdf(
        self,
        index: int,
        pdf_files: list[Path] | None = None,
        viewer_is_setlist: bool | None = None,
    ) -> None:
        if pdf_files is not None:
            self.viewer_pdf_files = list(pdf_files)
        if viewer_is_setlist is not None:
            self.viewer_is_setlist = viewer_is_setlist
        if not (0 <= index < len(self.viewer_pdf_files)):
            return

        self.current_index = index
        self.current_page_index = 0
        self.current_stroke_points = []
        self.current_stroke_item = None

        try:
            self.close_current_document()
            self.current_document = fitz.open(self.viewer_pdf_files[index])
        except Exception as exc:
            messagebox.showerror("Kunde inte öppna PDF", f"{self.viewer_pdf_files[index].name}\n\n{exc}")
            return

        self.enter_fullscreen()
        self.render_current_pdf()

    def enter_fullscreen(self) -> None:
        if hasattr(self, "viewer_frame"):
            self.viewer_frame.destroy()

        self.main_frame.pack_forget()
        self.viewer_frame = tk.Frame(self.root, bg="black")
        self.viewer_frame.pack(fill=tk.BOTH, expand=True)

        self.pdf_canvas = tk.Canvas(
            self.viewer_frame,
            bg="black",
            highlightthickness=0,
            cursor="none",
            takefocus=True,
        )
        self.pdf_canvas.pack(fill=tk.BOTH, expand=True)
        self.pdf_canvas.bind("<ButtonPress-1>", self.start_annotation_stroke)
        self.pdf_canvas.bind("<B1-Motion>", self.extend_annotation_stroke)
        self.pdf_canvas.bind("<ButtonRelease-1>", self.finish_annotation_stroke)
        self.pdf_canvas.bind("<Configure>", self.schedule_render)
        self.pdf_canvas.config(cursor="crosshair" if self.annotation_mode else "none")

        self.fullscreen = True
        self.root.attributes("-fullscreen", True)
        self.focus_viewer()
        self.root.after_idle(self.focus_viewer)

    def exit_fullscreen(self) -> None:
        if not self.fullscreen:
            return

        self.fullscreen = False
        self.root.attributes("-fullscreen", False)
        if hasattr(self, "viewer_frame"):
            self.viewer_frame.destroy()
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def focus_viewer(self) -> None:
        if self.fullscreen and hasattr(self, "pdf_canvas"):
            self.pdf_canvas.focus_set()

    def toggle_fullscreen(self) -> None:
        if self.fullscreen:
            self.exit_fullscreen()
        elif self.current_index is not None:
            self.show_pdf(self.current_index)

    def handle_canvas_click(self, event: tk.Event) -> None:
        if self.annotation_mode:
            return
        width = self.pdf_canvas.winfo_width()
        if event.x >= width / 2:
            self.show_next_page()
        else:
            self.show_previous_page()

    def toggle_annotation_mode(self) -> None:
        if not self.fullscreen:
            messagebox.showinfo("Anteckningsläge", "Öppna en PDF i helskärm först.")
            return
        if (
            not self.current_setlist_name
            or self.current_setlist_name not in self.saved_setlists
            or not self.viewer_is_setlist
        ):
            messagebox.showinfo(
                "Anteckningsläge",
                "Öppna en sparad setlist och välj en PDF i setlisten för att anteckna.",
            )
            return

        self.annotation_mode = not self.annotation_mode
        if hasattr(self, "pdf_canvas"):
            self.pdf_canvas.config(cursor="crosshair" if self.annotation_mode else "none")
        self.render_current_pdf()
        self.focus_viewer()

    def start_annotation_stroke(self, event: tk.Event) -> None:
        if not self.annotation_mode or not self.current_render_bounds:
            return
        point = self.canvas_to_note_point(event.x, event.y)
        if point is None:
            self.current_stroke_points = []
            self.current_stroke_item = None
            return
        self.current_stroke_points = [point]
        self.current_stroke_item = None

    def extend_annotation_stroke(self, event: tk.Event) -> None:
        if not self.annotation_mode or not self.current_stroke_points:
            return
        point = self.canvas_to_note_point(event.x, event.y)
        if point is None:
            return
        self.current_stroke_points.append(point)
        canvas_points = self.note_points_to_canvas(self.current_stroke_points)
        if len(canvas_points) < 4:
            return
        if self.current_stroke_item is not None:
            self.pdf_canvas.delete(self.current_stroke_item)
        self.current_stroke_item = self.pdf_canvas.create_line(
            *canvas_points,
            fill="#e5322d",
            width=4,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
            smooth=True,
            tags=("annotation",),
        )

    def finish_annotation_stroke(self, event: tk.Event) -> None:
        if not self.annotation_mode:
            self.handle_canvas_click(event)
            return
        if not self.annotation_mode or len(self.current_stroke_points) < 2:
            self.current_stroke_points = []
            self.current_stroke_item = None
            return

        page_strokes = self.get_current_page_annotations(create=True)
        if page_strokes is None:
            return
        page_strokes.append(
            {
                "coordinate_space": "page",
                "color": "#e5322d",
                "width": 4,
                "points": [[round(x, 5), round(y, 5)] for x, y in self.current_stroke_points],
            }
        )
        self.current_stroke_points = []
        self.current_stroke_item = None
        try:
            self.write_setlists()
        except OSError as exc:
            page_strokes.pop()
            messagebox.showerror("Kunde inte spara anteckning", str(exc))
            return
        self.render_current_pdf()

    def canvas_to_note_point(self, x: int, y: int) -> tuple[float, float] | None:
        if not self.current_render_bounds:
            return None
        left, top, width, height = self.current_render_bounds
        if not (left <= x <= left + width and top <= y <= top + height):
            return None
        visual_x = (x - left) / width
        visual_y = (y - top) / height
        return self.visual_to_page_point(visual_x, visual_y)

    def note_points_to_canvas(self, points: list[tuple[float, float]]) -> list[float]:
        if not self.current_render_bounds:
            return []
        left, top, width, height = self.current_render_bounds
        canvas_points: list[float] = []
        for x, y in points:
            visual_x, visual_y = self.page_to_visual_point(x, y)
            canvas_points.extend([left + visual_x * width, top + visual_y * height])
        return canvas_points

    def visual_to_page_point(self, x: float, y: float) -> tuple[float, float]:
        rotation = self.current_render_rotation % 360
        if rotation == 90:
            return (y, 1 - x)
        if rotation == 180:
            return (1 - x, 1 - y)
        if rotation == 270:
            return (1 - y, x)
        return (x, y)

    def page_to_visual_point(self, x: float, y: float) -> tuple[float, float]:
        rotation = self.current_render_rotation % 360
        if rotation == 90:
            return (1 - y, x)
        if rotation == 180:
            return (1 - x, 1 - y)
        if rotation == 270:
            return (y, 1 - x)
        return (x, y)

    def get_current_page_annotations(self, create: bool = False) -> list[dict[str, Any]] | None:
        if (
            self.current_setlist_name is None
            or self.current_index is None
            or self.current_setlist_name not in self.saved_setlists
            or not self.viewer_is_setlist
            or not (0 <= self.current_index < len(self.viewer_pdf_files))
        ):
            return None

        setlist_notes = self.annotations.get(self.current_setlist_name)
        if setlist_notes is None:
            if not create:
                return None
            setlist_notes = self.annotations.setdefault(self.current_setlist_name, {})

        pdf_key = str(self.viewer_pdf_files[self.current_index])
        pdf_notes = setlist_notes.get(pdf_key)
        if pdf_notes is None:
            if not create:
                return None
            pdf_notes = setlist_notes.setdefault(pdf_key, {})

        page_key = str(self.current_page_index)
        page_strokes = pdf_notes.get(page_key)
        if page_strokes is None:
            if not create:
                return None
            page_strokes = pdf_notes.setdefault(page_key, [])
        return page_strokes

    def draw_current_annotations(self) -> None:
        page_strokes = self.get_current_page_annotations()
        if not page_strokes:
            return
        for stroke in page_strokes:
            raw_points = stroke.get("points")
            if not isinstance(raw_points, list):
                continue
            points: list[tuple[float, float]] = []
            for raw_point in raw_points:
                if (
                    isinstance(raw_point, list)
                    and len(raw_point) == 2
                    and isinstance(raw_point[0], (int, float))
                    and isinstance(raw_point[1], (int, float))
                ):
                    points.append((float(raw_point[0]), float(raw_point[1])))
            canvas_points = self.note_points_to_canvas(points)
            if len(canvas_points) < 4:
                continue
            self.pdf_canvas.create_line(
                *canvas_points,
                fill=str(stroke.get("color", "#e5322d")),
                width=int(stroke.get("width", 4)),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
                smooth=True,
                tags=("annotation",),
            )

    def undo_last_annotation(self) -> None:
        page_strokes = self.get_current_page_annotations()
        if not page_strokes:
            return
        removed_stroke = page_strokes.pop()
        try:
            self.write_setlists()
        except OSError as exc:
            page_strokes.append(removed_stroke)
            messagebox.showerror("Kunde inte ångra anteckning", str(exc))
            return
        self.render_current_pdf()

    def delete_current_page_annotations(self) -> None:
        page_strokes = self.get_current_page_annotations()
        if not page_strokes:
            return

        removed_strokes = list(page_strokes)
        page_strokes.clear()
        try:
            self.write_setlists()
        except OSError as exc:
            page_strokes.extend(removed_strokes)
            messagebox.showerror("Kunde inte ta bort anteckning", str(exc))
            return
        self.render_current_pdf()

    def show_next_page(self) -> None:
        if not self.fullscreen or self.current_document is None:
            return
        if self.current_page_index < self.current_document.page_count - 1:
            self.current_page_index += 1
            self.render_current_pdf()
            return
        self.show_next_pdf()

    def show_previous_page(self) -> None:
        if not self.fullscreen or self.current_document is None:
            return
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.render_current_pdf()
            return
        self.show_previous_pdf(last_page=True)

    def show_next_pdf(self) -> None:
        if self.current_index is None or not self.viewer_pdf_files:
            return
        if self.current_index < len(self.viewer_pdf_files) - 1:
            self.show_pdf(self.current_index + 1)

    def show_previous_pdf(self, last_page: bool = False) -> None:
        if self.current_index is None or not self.viewer_pdf_files:
            return
        if self.current_index > 0:
            self.show_pdf(self.current_index - 1)
            if last_page and self.current_document is not None:
                self.current_page_index = self.current_document.page_count - 1
                self.render_current_pdf()

    def schedule_render(self, _event: tk.Event | None = None) -> None:
        if self.render_after_id:
            self.root.after_cancel(self.render_after_id)
        self.render_after_id = self.root.after(120, self.render_current_pdf)

    def render_current_pdf(self) -> None:
        self.render_after_id = None
        if not self.current_document or not self.fullscreen:
            return

        canvas_width = max(self.pdf_canvas.winfo_width(), 1)
        canvas_height = max(self.pdf_canvas.winfo_height(), 1)
        page_index = max(0, min(self.current_page_index, self.current_document.page_count - 1))
        self.current_page_index = page_index
        page = self.current_document.load_page(page_index)
        page_rect = page.rect
        rotation = self.get_render_rotation(page_rect)
        self.current_render_rotation = rotation
        render_width, render_height = page_rect.width, page_rect.height
        if rotation in (90, 270):
            render_width, render_height = render_height, render_width

        scale = min(canvas_width / render_width, canvas_height / render_height)
        matrix = fitz.Matrix(scale, scale).prerotate(rotation)

        try:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            self.current_photo = tk.PhotoImage(data=pixmap.tobytes("ppm"))
        except Exception as exc:
            messagebox.showerror("Kunde inte visa PDF", str(exc))
            return

        self.pdf_canvas.delete("all")
        x = canvas_width // 2
        y = canvas_height // 2
        self.pdf_canvas.create_image(x, y, image=self.current_photo, anchor=tk.CENTER)
        image_width = self.current_photo.width()
        image_height = self.current_photo.height()
        self.current_render_bounds = (
            x - image_width / 2,
            y - image_height / 2,
            image_width,
            image_height,
        )
        self.draw_current_annotations()
        if self.annotation_mode:
            self.pdf_canvas.create_text(
                18,
                18,
                text="Anteckningsläge",
                anchor=tk.NW,
                fill="#ffffff",
                font=("TkDefaultFont", 16, "bold"),
            )

    def get_render_rotation(self, page_rect: object) -> int:
        page_is_landscape = page_rect.width > page_rect.height
        wants_landscape = self.view_orientation.get() == "landscape"
        if page_is_landscape == wants_landscape:
            return 0
        return 90

    def close_current_document(self) -> None:
        if self.current_document is not None:
            self.current_document.close()
            self.current_document = None


def main() -> int:
    try:
        locale.setlocale(locale.LC_COLLATE, "")
    except locale.Error:
        pass

    if fitz is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "PyMuPDF saknas",
            "Installera PDF-stödet med:\n\n"
            f"{sys.executable} -m pip install PyMuPDF\n\n"
            "Obs: paketet heter PyMuPDF, inte PyMyPDF.",
        )
        return 1

    root = tk.Tk()
    app = SetlistApp(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    app.close_current_document()
    return 0


if __name__ == "__main__":
    sys.exit(main())
