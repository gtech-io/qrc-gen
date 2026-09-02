"""Label-sheet geometry, shared by every output backend.

All measurements are in millimetres with the origin at the top-left of the
page, which is how label stock is specified. The PDF backend flips the y
axis on its way out; SVG uses these numbers as-is.
"""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.pdfbase.pdfmetrics import stringWidth

from ..render import ErrorLevel, make

__all__ = [
  "A4",
  "DEFAULT_PRESET",
  "LETTER",
  "PRESETS",
  "CellLayout",
  "Label",
  "SheetSpec",
  "TextLine",
  "layout_cell",
  "paginate",
  "qr_modules",
  "unsupported_characters",
]

MM_PER_PT = 25.4 / 72
PT_PER_MM = 72 / 25.4

#: Base-14 fonts, so nothing has to be embedded and the PDF stays tiny.
CAPTION_FONT = "Helvetica-Bold"
SUBTITLE_FONT = "Helvetica"

PADDING = 2.5
QUIET_ZONE = 4
CAPTION_SIZE = 4.2
SUBTITLE_SIZE = 3.0
ELLIPSIS = "…"

#: The base-14 PDF fonts are encoded in WinAnsi and guarantee nothing beyond
#: it. Anything outside depends on the reader substituting a font, so it may
#: render, or may come out as black boxes.
PDF_TEXT_ENCODING = "cp1252"


@dataclass(slots=True)
class Label:
  """One sticker: what it encodes, and what a human reads off it."""

  payload: str
  caption: str = ""
  subtitle: str = ""


@dataclass(slots=True, frozen=True)
class SheetSpec:
  """Label stock geometry. All measurements in millimetres."""

  name: str
  page_w: float
  page_h: float
  cols: int
  rows: int
  cell_w: float
  cell_h: float
  margin_x: float
  margin_y: float
  gutter_x: float = 0.0
  gutter_y: float = 0.0

  @property
  def per_page(self) -> int:
    return self.cols * self.rows

  def origin(self, index: int) -> tuple[float, float]:
    """Top-left corner of the `index`-th cell on a page (0-based)."""
    col, row = index % self.cols, index // self.cols
    x = self.margin_x + col * (self.cell_w + self.gutter_x)
    y = self.margin_y + row * (self.cell_h + self.gutter_y)
    return x, y


LETTER = (215.9, 279.4)
A4 = (210.0, 297.0)

PRESETS: dict[str, SheetSpec] = {
  # Avery 5160 / 5260 - 1" x 2-5/8", 30 per US Letter sheet.
  "avery-5160": SheetSpec(
    "avery-5160", *LETTER, cols=3, rows=10,
    cell_w=66.675, cell_h=25.4, margin_x=4.7625, margin_y=12.7, gutter_x=3.175,
  ),
  # Avery 5163 - 2" x 4", 10 per US Letter sheet. Room for a real caption.
  "avery-5163": SheetSpec(
    "avery-5163", *LETTER, cols=2, rows=5,
    cell_w=101.6, cell_h=50.8, margin_x=3.96875, margin_y=12.7, gutter_x=4.7625,
  ),
  # Avery L7159 - 63.5mm x 33.9mm, 24 per A4 sheet.
  "avery-l7159": SheetSpec(
    "avery-l7159", *A4, cols=3, rows=8,
    cell_w=63.5, cell_h=33.9, margin_x=7.25, margin_y=12.9, gutter_x=2.5,
  ),
  # No label stock: a plain 3x4 grid of squares to cut out yourself.
  "cut-4x3": SheetSpec(
    "cut-4x3", *LETTER, cols=3, rows=4,
    cell_w=60.0, cell_h=60.0, margin_x=17.9, margin_y=19.7,
  ),
}

DEFAULT_PRESET = "avery-5163"


@dataclass(slots=True, frozen=True)
class TextLine:
  """One line of caption text, already truncated to fit its cell."""

  text: str
  x: float
  baseline: float  # millimetres from the top of the page
  size: float  # millimetres, cap-to-descender
  font: str
  grey: bool = False


@dataclass(slots=True, frozen=True)
class CellLayout:
  """Where everything sits inside one label, in page millimetres."""

  qr_x: float
  qr_y: float
  qr_size: float
  lines: tuple[TextLine, ...]


def paginate(
  labels: list[Label], spec: SheetSpec, skip: int
) -> list[list[Label | None]]:
  """Split labels into pages, leaving `skip` cells blank at the start."""
  if not labels:
    raise ValueError("no labels to render")
  if skip < 0 or skip >= spec.per_page:
    raise ValueError(f"--skip must be between 0 and {spec.per_page - 1}")

  cells: list[Label | None] = [None] * skip + list(labels)
  return [cells[i : i + spec.per_page] for i in range(0, len(cells), spec.per_page)]


def layout_cell(label: Label, x: float, y: float, spec: SheetSpec) -> CellLayout:
  """Place the QR code and caption lines within the cell at (x, y)."""
  size = spec.cell_h - PADDING * 2
  qr_x, qr_y = x + PADDING, y + PADDING

  text_x = qr_x + size + PADDING
  available = spec.cell_w - (text_x - x) - PADDING
  if not label.caption or available <= 8:
    return CellLayout(qr_x, qr_y, size, ())

  baseline = y + spec.cell_h / 2
  if label.subtitle:
    baseline -= SUBTITLE_SIZE * 0.4
  else:
    baseline += CAPTION_SIZE / 3

  lines = [
    TextLine(
      text=fit(label.caption, CAPTION_FONT, CAPTION_SIZE, available),
      x=text_x,
      baseline=baseline,
      size=CAPTION_SIZE,
      font=CAPTION_FONT,
    )
  ]
  if label.subtitle:
    lines.append(
      TextLine(
        text=fit(label.subtitle, SUBTITLE_FONT, SUBTITLE_SIZE, available),
        x=text_x,
        baseline=baseline + SUBTITLE_SIZE * 1.4,
        size=SUBTITLE_SIZE,
        font=SUBTITLE_FONT,
        grey=True,
      )
    )
  return CellLayout(qr_x, qr_y, size, tuple(lines))


def width_mm(text: str, font: str, size: float) -> float:
  """Width of `text` in millimetres, from the real font metrics."""
  return stringWidth(text, font, size * PT_PER_MM) * MM_PER_PT


def fit(text: str, font: str, size: float, available: float) -> str:
  """Truncate `text` with an ellipsis until it fits `available` millimetres."""
  text = text.strip()
  if width_mm(text, font, size) <= available:
    return text
  trimmed = text
  while trimmed and width_mm(trimmed + ELLIPSIS, font, size) > available:
    trimmed = trimmed[:-1].rstrip()
  return trimmed + ELLIPSIS if trimmed else ELLIPSIS


def unsupported_characters(text: str) -> str:
  """Characters in `text` that the base-14 PDF fonts cannot encode."""
  seen: list[str] = []
  for char in text:
    if char in seen:
      continue
    try:
      char.encode(PDF_TEXT_ENCODING)
    except UnicodeEncodeError:
      seen.append(char)
  return "".join(seen)


def qr_modules(payload: str, error: ErrorLevel) -> tuple[list[list[int]], int, int]:
  """Return the QR matrix, its module count, and the quiet zone to leave.

  4 modules is what the QR spec requires. Anything less and decoders start
  failing on codes that look perfectly fine to the eye.
  """
  matrix = [list(row) for row in make(payload, error=error).matrix]
  return matrix, len(matrix), QUIET_ZONE
