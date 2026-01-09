from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Dict, Any, Tuple
import time
import uuid
import os
import tempfile

from PySide6.QtCore import Qt, Signal, QRectF, QSizeF
from PySide6.QtGui import QTextDocument, QPainter, QPdfWriter, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QTextEdit,
    QTextBrowser, QFileDialog
)


@dataclass
class ScratchpadEntry:
    entry_id: str
    created_ts: float
    tags: List[str]
    text: str

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.entry_id,
            "created_ts": self.created_ts,
            "tags": list(self.tags),
            "text": self.text,
        }

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "ScratchpadEntry":
        return ScratchpadEntry(
            entry_id=str(d.get("id") or uuid.uuid4().hex),
            created_ts=float(d.get("created_ts") or time.time()),
            tags=[t.strip() for t in (d.get("tags") or []) if str(t).strip()],
            text=str(d.get("text") or ""),
        )


class ScratchpadWidget(QWidget):
    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._entries: List[ScratchpadEntry] = []
        self._filtered: List[ScratchpadEntry] = []
        self._active_entry: Optional[ScratchpadEntry] = None

        # Controls
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search text…")

        self.tag_filter = QLineEdit()
        self.tag_filter.setPlaceholderText("Tags filter (comma-separated)… e.g. NPC, Rumor, Dungeon:Wake Ward")

        self.add_manual_btn = QPushButton("Add")
        self.move_up_btn = QPushButton("Up")
        self.move_down_btn = QPushButton("Down")
        self.export_pdf_btn = QPushButton("Export PDF")
        self.export_txt_btn = QPushButton("Export Text")
        self.delete_btn = QPushButton("Delete")
        self.copy_btn = QPushButton("Copy")
        self.delete_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.move_up_btn.setEnabled(False)
        self.move_down_btn.setEnabled(False)

        top = QHBoxLayout()
        top.addWidget(QLabel("Search"))
        top.addWidget(self.search_box, stretch=2)
        top.addWidget(QLabel("Tags"))
        top.addWidget(self.tag_filter, stretch=2)
        top.addWidget(self.add_manual_btn)
        top.addWidget(self.move_up_btn)
        top.addWidget(self.move_down_btn)
        top.addWidget(self.copy_btn)
        top.addWidget(self.delete_btn)
        top.addWidget(self.export_pdf_btn)
        top.addWidget(self.export_txt_btn)

        self.list = QListWidget()
        self.preview = QTextBrowser()
        self.preview.setPlaceholderText("Select an entry…")
        self.preview.setOpenExternalLinks(True)

        split = QHBoxLayout()
        split.addWidget(self.list, stretch=1)
        split.addWidget(self.preview, stretch=2)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(split)

        # Wiring
        self.search_box.textChanged.connect(self._apply_filters)
        self.tag_filter.textChanged.connect(self._apply_filters)
        self.list.currentRowChanged.connect(self._on_select)
        self.add_manual_btn.clicked.connect(self._add_manual)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.copy_btn.clicked.connect(self._copy_selected)
        self.move_up_btn.clicked.connect(lambda: self._move_selected(-1))
        self.move_down_btn.clicked.connect(lambda: self._move_selected(+1))
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        self.export_txt_btn.clicked.connect(self._export_text)

        self._apply_filters()

    # -------- persistence --------

    def set_entries(self, entries: Sequence[ScratchpadEntry]) -> None:
        self._entries = list(entries)
        self._apply_filters()

    def get_entries(self) -> List[ScratchpadEntry]:
        return list(self._entries)

    def to_json(self) -> List[Dict[str, Any]]:
        return [e.to_json() for e in self._entries]

    def load_json(self, data: Any) -> None:
        entries: List[ScratchpadEntry] = []
        if isinstance(data, list):
            for d in data:
                if isinstance(d, dict):
                    entries.append(ScratchpadEntry.from_json(d))
        self.set_entries(entries)

    # -------- API used by ctx service --------

    def add_entry(self, text: str, tags: Optional[Sequence[str]] = None) -> ScratchpadEntry:
        tags_list = []
        if tags:
            tags_list = [t.strip() for t in tags if str(t).strip()]
        e = ScratchpadEntry(entry_id=uuid.uuid4().hex, created_ts=time.time(), tags=tags_list, text=text.strip())
        self._entries.insert(0, e)
        self._apply_filters()
        self.changed.emit()
        return e

    # -------- UI handlers --------

    def _parse_tag_filter(self) -> List[str]:
        raw = self.tag_filter.text().strip()
        if not raw:
            return []
        return [t.strip().lower() for t in raw.split(",") if t.strip()]

    def _apply_filters(self) -> None:
        q = self.search_box.text().strip().lower()
        tag_q = self._parse_tag_filter()

        def matches(e: ScratchpadEntry) -> bool:
            if q and q not in e.text.lower():
                # allow searching tags too
                if all(q not in t.lower() for t in e.tags):
                    return False
            if tag_q:
                etags = [t.lower() for t in e.tags]
                for tq in tag_q:
                    if tq not in etags:
                        return False
            return True

        self._filtered = [e for e in self._entries if matches(e)]

        self.list.blockSignals(True)
        self.list.clear()
        for e in self._filtered:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.created_ts))
            tag_str = (", ".join(e.tags)) if e.tags else "untagged"
            title = e.text.strip().splitlines()[0][:60] if e.text.strip() else "(empty)"
            item = QListWidgetItem(f"[{ts}] ({tag_str}) {title}")
            item.setData(Qt.UserRole, e.entry_id)
            self.list.addItem(item)
        self.list.blockSignals(False)

        self._active_entry = None
        self._set_preview_markdown("")
        self.delete_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.move_up_btn.setEnabled(False)
        self.move_down_btn.setEnabled(False)

    def _find_entry_by_id(self, entry_id: str) -> Optional[ScratchpadEntry]:
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def _on_select(self, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            self._active_entry = None
            self._set_preview_markdown("")
            self.delete_btn.setEnabled(False)
            self.copy_btn.setEnabled(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            return

        e = self._filtered[row]
        self._active_entry = e
        self._set_preview_markdown(self._entry_preview_markdown(e))
        self.delete_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self._update_move_buttons()

    def _add_manual(self) -> None:
        # Minimal manual entry: put focus into a dialog-ish prompt using QMessageBox with a QTextEdit.
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Add to Scratchpad")
        dlg.setText("Enter text to add to the scratchpad:")
        te = QTextEdit()
        te.setMinimumSize(500, 220)
        dlg.layout().addWidget(te, 1, 0, 1, dlg.layout().columnCount())
        dlg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        if dlg.exec() == QMessageBox.Ok:
            txt = te.toPlainText().strip()
            if txt:
                self.add_entry(txt, tags=None)

    def _delete_selected(self) -> None:
        if not self._active_entry:
            return
        e = self._active_entry
        if QMessageBox.question(self, "Delete", "Delete selected scratchpad entry?") != QMessageBox.Yes:
            return
        self._entries = [x for x in self._entries if x.entry_id != e.entry_id]
        self._apply_filters()
        self.changed.emit()

    def _copy_selected(self) -> None:
        if not self._active_entry:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._active_entry.text)



    # -------- markdown preview --------

    def _set_preview_markdown(self, md: str) -> None:
        """Render markdown in the preview panel (with graceful fallback)."""
        md = md or ""
        try:
            # QTextBrowser supports Qt's native Markdown rendering.
            self.preview.setMarkdown(md)
        except Exception:
            # Fallback: show raw text if Markdown isn't supported for some reason.
            self.preview.setPlainText(md)

    def _entry_title(self, e: ScratchpadEntry) -> str:
        first = e.text.strip().splitlines()[0].strip() if e.text.strip() else "(empty)"
        return first[:80]

    def _entry_preview_markdown(self, e: ScratchpadEntry) -> str:
        ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e.created_ts))
        tags = ', '.join(e.tags) if e.tags else '(none)'
        # Metadata header + body (body is treated as Markdown).
        body = (e.text or '').strip()
        return (
            f"**Tags:** {tags}\n\n"
            f"**Created:** {ts}\n\n"
            "---\n\n"
            f"{body}"
        )

    # -------- ordering / move --------

    def _update_move_buttons(self) -> None:
        if not self._active_entry:
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            return
        try:
            idx = self._filtered.index(self._active_entry)
        except ValueError:
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            return
        self.move_up_btn.setEnabled(idx > 0)
        self.move_down_btn.setEnabled(idx < (len(self._filtered) - 1))

    def _move_selected(self, direction: int) -> None:
        """Move the selected entry up/down within the current filtered view."""
        if not self._active_entry:
            return
        if direction not in (-1, +1):
            return

        try:
            fidx = self._filtered.index(self._active_entry)
        except ValueError:
            return

        nidx = fidx + direction
        if nidx < 0 or nidx >= len(self._filtered):
            return

        a = self._filtered[fidx]
        b = self._filtered[nidx]

        # Swap positions in the underlying master list (order that is persisted).
        try:
            ia = self._entries.index(a)
            ib = self._entries.index(b)
        except ValueError:
            return

        self._entries[ia], self._entries[ib] = self._entries[ib], self._entries[ia]

        moved_id = a.entry_id
        self._apply_filters()

        # Restore selection on moved entry
        for r in range(self.list.count()):
            item = self.list.item(r)
            if item and item.data(Qt.UserRole) == moved_id:
                self.list.setCurrentRow(r)
                break

        self.changed.emit()

    # -------- exports --------

    def _build_export_markdown(self, entries: Sequence[ScratchpadEntry]) -> str:
        lines: List[str] = []
        lines.append("# Scratchpad Export")
        lines.append("")
        lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        for i, e in enumerate(entries, start=1):
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e.created_ts))
            tags = ', '.join(e.tags) if e.tags else '(none)'
            title = self._entry_title(e)

            lines.append("---")
            lines.append("")
            lines.append(f"## {i}. {title}")
            lines.append("")
            lines.append(f"**Tags:** {tags}\n")
            lines.append(f"**Created:** {ts}")
            lines.append("")
            lines.append((e.text or '').strip())
            lines.append("")

        return "\n".join(lines)

    def _build_export_text(self, entries: Sequence[ScratchpadEntry]) -> str:
        out: List[str] = []
        out.append("SCRATCHPAD EXPORT")
        out.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        out.append("")

        for i, e in enumerate(entries, start=1):
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e.created_ts))
            tags = ', '.join(e.tags) if e.tags else '(none)'
            out.append("=" * 80)
            out.append(f"[{i}] {self._entry_title(e)}")
            out.append(f"Tags: {tags}")
            out.append(f"Created: {ts}")
            out.append("-")
            out.append((e.text or '').rstrip())
            out.append("")

        return "\n".join(out)

    def _export_pdf(self) -> None:
        if not self._entries:
            QMessageBox.information(self, "Export PDF", "Scratchpad is empty.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Scratchpad as PDF",
            "scratchpad.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return

        # Build a PDF where each scratchpad entry starts on a new page.
        # We also try to add PDF bookmarks (outline entries) when possible.

        # Write to a temporary file first so we can optionally post-process bookmarks.
        tmp_dir = os.path.dirname(path) or os.getcwd()
        fd, tmp_path = tempfile.mkstemp(prefix="scratchpad_", suffix=".pdf", dir=tmp_dir)
        os.close(fd)

        bookmarks: List[Tuple[str, int]] = []  # (title, page_index)

        def render_doc_to_writer(doc: QTextDocument, painter: QPainter, writer: QPdfWriter, dpi: int) -> int:
            """Render a QTextDocument to a QPdfWriter. Returns number of pages rendered."""
            paint_rect = writer.pageLayout().paintRectPixels(dpi)
            page_w = float(paint_rect.width())
            page_h = float(paint_rect.height())
            doc.setPageSize(QSizeF(page_w, page_h))

            page_count = int(doc.pageCount()) or 1
            for page in range(page_count):
                if page > 0:
                    writer.newPage()
                painter.save()
                painter.translate(float(paint_rect.x()), float(paint_rect.y()) - page * page_h)
                clip = QRectF(0.0, page * page_h, page_w, page_h)
                doc.drawContents(painter, clip)
                painter.restore()
            return page_count

        # Use QPdfWriter (avoids Windows print engine / CreateDC issues)
        try:
            writer = QPdfWriter(tmp_path)
            dpi = 120
            writer.setResolution(dpi)
            writer.setPageSize(QPageSize(QPageSize.A4))

            painter = QPainter(writer)

            current_page = 0
            for i, e in enumerate(self._entries, start=1):
                if i > 1:
                    writer.newPage()
                    current_page += 1

                title = f"{i}. {self._entry_title(e)}"
                bookmarks.append((title, current_page))

                ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(e.created_ts))
                tags = ', '.join(e.tags) if e.tags else '(none)'
                body = (e.text or '').strip()
                md = (
                    f"# {title}\n\n"
                    f"**Tags:** {tags}\n\n"
                    f"**Created:** {ts}\n\n"
                    "---\n\n"
                    f"{body}\n"
                )

                doc = QTextDocument()
                try:
                    doc.setMarkdown(md)
                except Exception:
                    doc.setPlainText(md)

                pages = render_doc_to_writer(doc, painter, writer, dpi)
                current_page += max(pages - 1, 0)

            painter.end()

            # Try to add bookmarks (outline) using a lightweight PDF library.
            # Qt's QPdfWriter doesn't expose bookmark APIs, so we post-process the PDF.
            # We support either `pypdf` (preferred) or `PyPDF2` (fallback).
            try:
                try:
                    from pypdf import PdfReader, PdfWriter  # type: ignore
                    _pdf_lib = "pypdf"
                except Exception:
                    from PyPDF2 import PdfReader, PdfWriter  # type: ignore
                    _pdf_lib = "PyPDF2"

                reader = PdfReader(tmp_path)
                w = PdfWriter()
                for p in reader.pages:
                    w.add_page(p)

                # Add outline items
                for title, page_index in bookmarks:
                    # Clamp page index just in case
                    if page_index < 0:
                        page_index = 0
                    if page_index >= len(reader.pages):
                        page_index = len(reader.pages) - 1

                    # API differences between libraries / versions
                    try:
                        # pypdf >=3
                        w.add_outline_item(title, page_number=page_index)
                    except Exception:
                        try:
                            w.add_outline_item(title, page_index)
                        except Exception:
                            # PyPDF2 older API
                            try:
                                w.addBookmark(title, page_index)  # type: ignore[attr-defined]
                            except Exception:
                                pass

                # Hint viewers to show outline when available (best-effort).
                try:
                    # pypdf: NameObject/DictionaryObject exist; PyPDF2 has similar.
                    from pypdf.generic import NameObject  # type: ignore
                    w._root_object.update({NameObject("/PageMode"): NameObject("/UseOutlines")})
                except Exception:
                    try:
                        from PyPDF2.generic import NameObject  # type: ignore
                        w._root_object.update({NameObject("/PageMode"): NameObject("/UseOutlines")})
                    except Exception:
                        pass

                with open(path, "wb") as f:
                    w.write(f)
            except Exception as ex_bookmarks:
                # If bookmarks fail for any reason, keep the generated PDF as-is.
                # (Also log why, so it's not "silent".)
                try:
                    self.ctx.log(f"[Scratchpad] PDF exported without bookmarks: {ex_bookmarks}")
                except Exception:
                    pass
                os.replace(tmp_path, path)
                tmp_path = ""

            QMessageBox.information(self, "Export PDF", f"Exported PDF to:\n{path}")
        except Exception as ex:
            # Cleanup temp if it exists
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

            # Fallback: try QPrinter path (may still fail on some Windows installs)
            try:
                md = self._build_export_markdown(self._entries)
                doc = QTextDocument()
                try:
                    doc.setMarkdown(md)
                except Exception:
                    doc.setPlainText(md)

                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(path)
                doc.print(printer)
                QMessageBox.information(self, "Export PDF", f"Exported PDF to:\n{path}")
            except Exception as ex2:
                QMessageBox.critical(
                    self,
                    "Export PDF",
                    f"Failed to export PDF:\n{ex}\n\nFallback also failed:\n{ex2}",
                )
        finally:
            # Best-effort temp cleanup
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass


    def _export_text(self) -> None:
        if not self._entries:
            QMessageBox.information(self, "Export Text", "Scratchpad is empty.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Scratchpad as Text",
            "scratchpad.txt",
            "Text Files (*.txt)",
        )
        if not path:
            return

        txt = self._build_export_text(self._entries)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt)
            QMessageBox.information(self, "Export Text", f"Exported text to:\n{path}")
        except Exception as ex:
            QMessageBox.critical(self, "Export Text", f"Failed to export text:\n{ex}")
