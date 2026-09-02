"""Printable label sheets: a grid of QR codes with human-readable captions.

`render_sheet` picks its backend from the output extension: `.pdf` puts every
page in one file and is what you want for printing; `.svg` writes one file per
page, for editing or embedding.
"""

from __future__ import annotations

from pathlib import Path

from ..render import ErrorLevel
from .layout import (
  A4,
  DEFAULT_PRESET,
  LETTER,
  PRESETS,
  CellLayout,
  Label,
  SheetSpec,
  TextLine,
  layout_cell,
  paginate,
)
from .pdf import write_pdf
from .svg import page_svg

__all__ = [
  "A4",
  "DEFAULT_PRESET",
  "FORMATS",
  "LETTER",
  "PRESETS",
  "CellLayout",
  "Label",
  "SheetSpec",
  "TextLine",
  "layout_cell",
  "paginate",
  "render_sheet",
]

#: Output formats `render_sheet` understands, chosen by file extension.
FORMATS = ("pdf", "svg")


def render_sheet(
  labels: list[Label],
  out: Path,
  *,
  spec: SheetSpec | None = None,
  error: ErrorLevel = "m",
  skip: int = 0,
  show_cut_lines: bool = False,
) -> list[Path]:
  """Lay labels out on `spec` stock and write them to `out`.

  Returns the paths written. PDF is always a single multi-page file; SVG
  spills onto `name-2.svg`, `name-3.svg` and so on, one per page.

  `skip` leaves that many cells blank at the start, so a part-used sheet of
  labels can be fed back through the printer.
  """
  fmt = out.suffix.lstrip(".").lower()
  if fmt not in FORMATS:
    raise ValueError(
      f"unsupported sheet format {fmt!r}; use one of: {', '.join(FORMATS)}"
    )

  spec = spec or PRESETS[DEFAULT_PRESET]
  pages = paginate(labels, spec, skip)
  out.parent.mkdir(parents=True, exist_ok=True)

  if fmt == "pdf":
    write_pdf(pages, out, spec, error, show_cut_lines)
    return [out]

  written = []
  for number, page in enumerate(pages, start=1):
    path = out if number == 1 else out.with_name(f"{out.stem}-{number}{out.suffix}")
    path.write_text(page_svg(page, spec, error, show_cut_lines), encoding="utf-8")
    written.append(path)
  return written
