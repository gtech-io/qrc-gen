"""PDF backend: every page in one file, at exactly the right paper size.

This is the format to print. A PDF carries its own page dimensions, so a
printer lays it out at 100% without anyone having to remember to turn off
"fit to page" - which is the usual reason labels miss their backing sheet.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from ..render import ErrorLevel
from .layout import (
  PT_PER_MM,
  CellLayout,
  Label,
  SheetSpec,
  layout_cell,
  qr_modules,
  unsupported_characters,
)

__all__ = ["write_pdf"]

GREY = 0.35
CUT_LINE = 0.8


def write_pdf(
  pages: list[list[Label | None]],
  out: Path,
  spec: SheetSpec,
  error: ErrorLevel,
  show_cut_lines: bool,
) -> None:
  """Write every page into a single PDF at `out`."""
  page_w, page_h = spec.page_w * PT_PER_MM, spec.page_h * PT_PER_MM
  canvas = Canvas(str(out), pagesize=(page_w, page_h))
  canvas.setTitle(out.stem)

  _warn_about_unrenderable_text(pages)

  for page in pages:
    for index, label in enumerate(page):
      x, y = spec.origin(index)
      if show_cut_lines:
        canvas.setStrokeGray(CUT_LINE)
        canvas.setLineWidth(0.2 * PT_PER_MM)
        canvas.rect(
          x * PT_PER_MM,
          _flip(y + spec.cell_h, spec),
          spec.cell_w * PT_PER_MM,
          spec.cell_h * PT_PER_MM,
          stroke=1,
          fill=0,
        )
      if label is not None:
        _draw_cell(canvas, layout_cell(label, x, y, spec), label.payload, error, spec)
    canvas.showPage()
  canvas.save()


def _flip(y_mm: float, spec: SheetSpec) -> float:
  """Convert a top-down millimetre coordinate to PDF's bottom-up points."""
  return (spec.page_h - y_mm) * PT_PER_MM


def _draw_cell(
  canvas: Canvas,
  cell: CellLayout,
  payload: str,
  error: ErrorLevel,
  spec: SheetSpec,
) -> None:
  _draw_qr(canvas, payload, cell, error, spec)
  for line in cell.lines:
    canvas.setFillGray(GREY if line.grey else 0)
    canvas.setFont(line.font, line.size * PT_PER_MM)
    canvas.drawString(line.x * PT_PER_MM, _flip(line.baseline, spec), line.text)
  canvas.setFillGray(0)


def _draw_qr(
  canvas: Canvas,
  payload: str,
  cell: CellLayout,
  error: ErrorLevel,
  spec: SheetSpec,
) -> None:
  """Draw the matrix as one filled path, so the modules stay hairline-crisp."""
  matrix, modules, quiet = qr_modules(payload, error)
  unit = (cell.qr_size / (modules + quiet * 2)) * PT_PER_MM
  left = (cell.qr_x + quiet * cell.qr_size / (modules + quiet * 2)) * PT_PER_MM
  top = _flip(cell.qr_y + quiet * cell.qr_size / (modules + quiet * 2), spec)

  canvas.setFillGray(0)
  path = canvas.beginPath()
  for row, cells in enumerate(matrix):
    for col, dark in enumerate(cells):
      if dark:
        path.rect(left + col * unit, top - (row + 1) * unit, unit, unit)
  canvas.drawPath(path, stroke=0, fill=1)


def _warn_about_unrenderable_text(pages: list[list[Label | None]]) -> None:
  """Flag caption text the base-14 fonts cannot encode.

  Whether these characters appear at all comes down to the reader picking a
  substitute font, so CJK in particular tends to print as black boxes. The
  QR payload is unaffected - this is only about the caption a human reads.
  """
  found = ""
  for page in pages:
    for label in page:
      if label is None:
        continue
      for text in (label.caption, label.subtitle):
        for char in unsupported_characters(text):
          if char not in found:
            found += char
  if found:
    warnings.warn(
      f"these caption characters may not render in PDF: {found}. "
      "The QR codes are unaffected. Write an .svg instead to keep them.",
      UserWarning,
      stacklevel=3,
    )
