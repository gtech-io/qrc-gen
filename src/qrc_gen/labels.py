"""Printable label sheets: a grid of QR codes with human-readable captions.

Output is SVG in real millimetres, so printing at 100% scale (no "fit to
page") lands the codes on the label stock they were laid out for.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from .render import ErrorLevel, make

__all__ = ["PRESETS", "Label", "SheetSpec", "render_sheet"]


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
  # No label stock: a plain 3x4 grid of 50mm squares to cut out yourself.
  "cut-4x3": SheetSpec(
    "cut-4x3", *LETTER, cols=3, rows=4,
    cell_w=60.0, cell_h=60.0, margin_x=17.9, margin_y=19.7,
  ),
}

DEFAULT_PRESET = "avery-5163"

PADDING = 2.5
QUIET_ZONE = 4
CAPTION_SIZE = 4.2
SUBTITLE_SIZE = 3.0


def render_sheet(
  labels: list[Label],
  out: Path,
  *,
  spec: SheetSpec | None = None,
  error: ErrorLevel = "m",
  skip: int = 0,
  show_cut_lines: bool = False,
) -> list[Path]:
  """Write one SVG per page. Returns the paths written, in order.

  `skip` leaves that many cells blank at the start, so a part-used sheet of
  labels can be fed back through the printer.
  """
  if not labels:
    raise ValueError("no labels to render")
  spec = spec or PRESETS[DEFAULT_PRESET]
  if skip < 0 or skip >= spec.per_page:
    raise ValueError(f"--skip must be between 0 and {spec.per_page - 1}")

  cells: list[Label | None] = [None] * skip + list(labels)
  pages = [
    cells[i : i + spec.per_page] for i in range(0, len(cells), spec.per_page)
  ]

  out.parent.mkdir(parents=True, exist_ok=True)
  written = []
  for number, page in enumerate(pages, start=1):
    path = out if number == 1 else out.with_name(f"{out.stem}-{number}{out.suffix}")
    path.write_text(_page_svg(page, spec, error, show_cut_lines), encoding="utf-8")
    written.append(path)
  return written


def _page_svg(
  page: list[Label | None],
  spec: SheetSpec,
  error: ErrorLevel,
  show_cut_lines: bool,
) -> str:
  parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{spec.page_w}mm" height="{spec.page_h}mm" '
    f'viewBox="0 0 {spec.page_w} {spec.page_h}">',
    '<rect width="100%" height="100%" fill="#ffffff"/>',
    "<g font-family=\"Helvetica, Arial, sans-serif\" fill=\"#000000\">",
  ]
  for index, label in enumerate(page):
    x, y = spec.origin(index)
    if show_cut_lines:
      parts.append(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{spec.cell_w:.2f}" '
        f'height="{spec.cell_h:.2f}" fill="none" stroke="#cccccc" '
        f'stroke-width="0.2"/>'
      )
    if label is not None:
      parts.append(_cell_svg(label, x, y, spec, error))
  parts.append("</g></svg>")
  return "\n".join(parts)


def _cell_svg(
  label: Label, x: float, y: float, spec: SheetSpec, error: ErrorLevel
) -> str:
  size = spec.cell_h - PADDING * 2
  qr_x, qr_y = x + PADDING, y + PADDING
  parts = [_qr_svg(label.payload, qr_x, qr_y, size, error)]

  text_x = qr_x + size + PADDING
  available = spec.cell_w - (text_x - x) - PADDING
  if label.caption and available > 8:
    chars = max(4, int(available / (CAPTION_SIZE * 0.55)))
    caption = html.escape(_truncate(label.caption, chars))
    baseline = y + spec.cell_h / 2 + (0 if label.subtitle else CAPTION_SIZE / 3)
    if label.subtitle:
      baseline -= SUBTITLE_SIZE * 0.4
    parts.append(
      f'<text x="{text_x:.2f}" y="{baseline:.2f}" font-size="{CAPTION_SIZE}" '
      f'font-weight="600">{caption}</text>'
    )
    if label.subtitle:
      sub_chars = max(4, int(available / (SUBTITLE_SIZE * 0.55)))
      subtitle = html.escape(_truncate(label.subtitle, sub_chars))
      parts.append(
        f'<text x="{text_x:.2f}" y="{baseline + SUBTITLE_SIZE * 1.4:.2f}" '
        f'font-size="{SUBTITLE_SIZE}" fill="#555555">{subtitle}</text>'
      )
  return "".join(parts)


def _qr_svg(payload: str, x: float, y: float, size: float, error: ErrorLevel) -> str:
  """Emit the QR matrix as a single vector path scaled to `size` mm."""
  matrix = make(payload, error=error).matrix
  modules = len(matrix)
  # 4 modules is the quiet zone the QR spec requires. Anything less and
  # decoders start failing on codes that look fine to the eye.
  quiet = QUIET_ZONE
  unit = size / (modules + quiet * 2)

  segments = []
  for row_index, row in enumerate(matrix):
    for col_index, cell in enumerate(row):
      if cell:
        segments.append(f"M{col_index + quiet},{row_index + quiet}h1v1h-1z")
  path = "".join(segments)
  return (
    f'<g transform="translate({x:.3f},{y:.3f}) scale({unit:.5f})">'
    f'<path d="{path}" fill="#000000" shape-rendering="crispEdges"/></g>'
  )


def _truncate(text: str, limit: int) -> str:
  text = text.strip()
  return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
