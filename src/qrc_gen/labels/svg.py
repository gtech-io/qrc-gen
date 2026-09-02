"""SVG backend: one file per page, sized in real millimetres."""

from __future__ import annotations

import html

from ..render import ErrorLevel
from .layout import CellLayout, Label, SheetSpec, layout_cell, qr_modules

__all__ = ["page_svg"]

GREY = "#555555"
CUT_LINE = "#cccccc"


def page_svg(
  page: list[Label | None],
  spec: SheetSpec,
  error: ErrorLevel,
  show_cut_lines: bool,
) -> str:
  """Render one page of labels as a standalone SVG document."""
  parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{spec.page_w}mm" height="{spec.page_h}mm" '
    f'viewBox="0 0 {spec.page_w} {spec.page_h}">',
    '<rect width="100%" height="100%" fill="#ffffff"/>',
    '<g font-family="Helvetica, Arial, sans-serif" fill="#000000">',
  ]
  for index, label in enumerate(page):
    x, y = spec.origin(index)
    if show_cut_lines:
      parts.append(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{spec.cell_w:.2f}" '
        f'height="{spec.cell_h:.2f}" fill="none" stroke="{CUT_LINE}" '
        f'stroke-width="0.2"/>'
      )
    if label is not None:
      parts.append(_cell_svg(layout_cell(label, x, y, spec), label.payload, error))
  parts.append("</g></svg>")
  return "\n".join(parts)


def _cell_svg(cell: CellLayout, payload: str, error: ErrorLevel) -> str:
  parts = [_qr_svg(payload, cell.qr_x, cell.qr_y, cell.qr_size, error)]
  for line in cell.lines:
    weight = ' font-weight="600"' if line.font.endswith("Bold") else ""
    fill = f' fill="{GREY}"' if line.grey else ""
    parts.append(
      f'<text x="{line.x:.2f}" y="{line.baseline:.2f}" '
      f'font-size="{line.size}"{weight}{fill}>{html.escape(line.text)}</text>'
    )
  return "".join(parts)


def _qr_svg(payload: str, x: float, y: float, size: float, error: ErrorLevel) -> str:
  """Emit the QR matrix as a single vector path scaled to `size` mm."""
  matrix, modules, quiet = qr_modules(payload, error)
  unit = size / (modules + quiet * 2)

  segments = [
    f"M{col + quiet},{row + quiet}h1v1h-1z"
    for row, cells in enumerate(matrix)
    for col, cell in enumerate(cells)
    if cell
  ]
  return (
    f'<g transform="translate({x:.3f},{y:.3f}) scale({unit:.5f})">'
    f'<path d="{"".join(segments)}" fill="#000000" shape-rendering="crispEdges"/></g>'
  )
