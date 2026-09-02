"""Turn a payload string into a QR code on disk or in the terminal."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import segno

__all__ = ["ErrorLevel", "make", "render", "to_terminal"]

ErrorLevel = Literal["l", "m", "q", "h"]

#: Formats we let `--output` write. segno supports more, these are the ones
#: that make sense for a QR you are about to print or paste somewhere.
FILE_FORMATS = ("png", "svg", "eps", "pdf", "txt")


def make(payload: str, error: ErrorLevel = "m") -> segno.QRCode:
  """Build a standard (never micro) QR code.

  Micro QR codes are smaller but a lot of phone cameras cannot read them,
  which is the wrong trade for something you print once and stick on a box.
  """
  if not payload:
    raise ValueError("nothing to encode")
  return segno.make(payload, error=error, micro=False)


def render(
  payload: str,
  output: Path | None = None,
  *,
  error: ErrorLevel = "m",
  scale: int = 8,
  border: int = 4,
  dark: str = "#000000",
  light: str | None = "#ffffff",
) -> str | None:
  """Render `payload`. Writes to `output`, or returns terminal art if None."""
  qr = make(payload, error=error)
  if output is None:
    return to_terminal(qr)

  fmt = output.suffix.lstrip(".").lower()
  if fmt not in FILE_FORMATS:
    raise ValueError(
      f"unsupported output format {fmt!r}; use one of: {', '.join(FILE_FORMATS)}"
    )
  output.parent.mkdir(parents=True, exist_ok=True)
  qr.save(output, scale=scale, border=border, dark=dark, light=light)
  return None


def to_terminal(qr: segno.QRCode) -> str:
  """Half-block rendering: two QR rows per text row, so it stays square."""
  matrix = [[bool(cell) for cell in row] for row in qr.matrix]
  quiet = 4  # the quiet zone the QR spec requires
  width = len(matrix[0]) + quiet * 2
  blank = [False] * width
  rows = [blank] * quiet
  rows += [[False] * quiet + row + [False] * quiet for row in matrix]
  rows += [blank] * quiet

  lines = []
  for top_index in range(0, len(rows), 2):
    top = rows[top_index]
    bottom = rows[top_index + 1] if top_index + 1 < len(rows) else blank
    line = "".join(_half_block(t, b) for t, b in zip(top, bottom, strict=True))
    lines.append(line)
  return "\n".join(lines)


def _half_block(top: bool, bottom: bool) -> str:
  # Dark modules are rendered as the *background* colour of the terminal
  # (white-on-black terminals still scan, because we invert consistently).
  if top and bottom:
    return " "
  if top:
    return "▄"  # lower half block
  if bottom:
    return "▀"  # upper half block
  return "█"  # full block
