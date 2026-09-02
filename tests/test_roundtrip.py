"""End-to-end check: render a QR, then decode it with an independent library.

Skipped unless the optional `decode` dependency group is installed
(`uv sync --group decode`), because OpenCV is a heavy dependency to carry
just for a test.

Set QRC_REQUIRE_DECODE=1 to turn every skip in this file into a failure.
CI does, because these are the only tests that check a code actually scans,
and a silent skip here looks exactly like a green run.
"""

import os
import shutil
import subprocess

import pytest

REQUIRED = os.environ.get("QRC_REQUIRE_DECODE") == "1"

if REQUIRED:
  import cv2
else:
  cv2 = pytest.importorskip("cv2", reason="install the 'decode' dependency group")

from qrc_gen import payloads, render  # noqa: E402
from qrc_gen.labels import DEFAULT_PRESET, PRESETS, Label, render_sheet  # noqa: E402

CASES = [
  ("url", payloads.url("example.com/docs"), "https://example.com/docs"),
  ("email", payloads.email("ada@example.com", subject="Hi there"),
   "mailto:ada@example.com?subject=Hi%20there"),
  ("phone", payloads.phone("+1 (555) 010-9999"), "tel:+15550109999"),
  ("sms", payloads.sms("5550109999", "on my way"), "SMSTO:5550109999:on my way"),
  ("label", payloads.storage_label("BIN-042", base_url="inv.example.com"),
   "https://inv.example.com/BIN-042"),
]


#: OpenCV's detector is unreliable on very large, hard-edged renders and
#: decodes them happily once they are the size a camera would see. Scanning
#: at this width keeps the tests measuring our layout, not that quirk.
SCAN_WIDTH = 500


def decode(path) -> str:
  data, *_ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
  return data


def scan(image) -> str:
  """Decode a cropped code the way a phone camera would see it."""
  height, width = image.shape[:2]
  if width > SCAN_WIDTH:
    scale = SCAN_WIDTH / width
    image = cv2.resize(
      image,
      (SCAN_WIDTH, max(1, int(height * scale))),
      interpolation=cv2.INTER_AREA,
    )
  data, *_ = cv2.QRCodeDetector().detectAndDecode(image)
  return data


@pytest.mark.parametrize(("name", "payload", "expected"), CASES, ids=[c[0] for c in CASES])
def test_png_scans_back_to_the_payload(tmp_path, name, payload, expected):
  out = tmp_path / f"{name}.png"
  render.render(payload, out, scale=8)
  assert decode(out) == expected


def test_vcard_survives_the_round_trip(tmp_path):
  card = payloads.Contact(
    name="Ada Lovelace",
    org="Analytical Engines, Ltd",
    phones=["+15550109999"],
    emails=["ada@example.com"],
  )
  out = tmp_path / "contact.png"
  render.render(payloads.contact(card), out, scale=8)
  assert decode(out) == payloads.contact(card)


DEVICE_SCALE = 3
PX_PER_MM = DEVICE_SCALE * 96 / 25.4  # Chrome renders CSS at 96dpi


def test_every_code_on_a_printed_sheet_scans(tmp_path):
  """The sheet renderer emits its own SVG paths, so prove they decode.

  Each cell is cropped and decoded on its own: OpenCV's multi-code detector
  is unreliable on a dense sheet and would make this test flaky for reasons
  that have nothing to do with the code under test.
  """
  chrome = _find_chrome()
  if chrome is None:
    _missing("Chrome/Chromium", "rasterize the SVG")

  spec = PRESETS[DEFAULT_PRESET]
  ids = [f"BIN-{n:03d}" for n in range(1, spec.per_page + 1)]
  expected = [payloads.storage_label(i, base_url="inv.example.com") for i in ids]

  svg = tmp_path / "sheet.svg"
  render_sheet(
    [Label(payload=p, caption=i) for i, p in zip(ids, expected, strict=True)],
    svg,
    spec=spec,
  )
  png = tmp_path / "sheet.png"
  _rasterize(chrome, svg, png)

  sheet = cv2.imread(str(png))
  failures = []
  for index, want in enumerate(expected):
    code = _crop_qr(sheet, spec, index, PX_PER_MM)
    got = scan(code)
    if got != want:
      failures.append((ids[index], want, got))
  assert not failures


def _missing(tool: str, purpose: str) -> None:
  """Skip for a missing tool - unless CI has said these tests are mandatory."""
  message = f"{tool} is needed to {purpose}"
  if REQUIRED:
    pytest.fail(f"QRC_REQUIRE_DECODE is set but {message}")
  pytest.skip(message)


def _find_chrome() -> str | None:
  for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
    found = shutil.which(name)
    if found:
      return found
  return None


def _rasterize(chrome: str, svg, png) -> None:
  subprocess.run(
    [
      chrome, "--headless", "--disable-gpu", "--no-sandbox",
      f"--force-device-scale-factor={DEVICE_SCALE}", "--window-size=850,1100",
      "--default-background-color=ffffff",
      f"--screenshot={png}", str(svg),
    ],
    check=True,
    capture_output=True,
    timeout=120,
  )


# 600dpi is what a laser printer actually rasterizes at. It also keeps the
# module grid clear of the sampling artifacts that make poppler's output at
# some intermediate resolutions undecodable for reasons unrelated to layout.
PDF_DPI = 600


def test_pdf_page_geometry_matches_the_stock(tmp_path):
  """A PDF carries its own page size, which is the whole point of using one."""
  pypdf = pytest.importorskip("pypdf", reason="install the 'decode' dependency group")

  spec = PRESETS["avery-l7159"]  # A4 stock, to catch a hardcoded Letter
  out = tmp_path / "sheet.pdf"
  render_sheet([Label("A")] * (spec.per_page + 1), out, spec=spec)

  reader = pypdf.PdfReader(str(out))
  assert len(reader.pages) == 2, "both pages belong in the one file"
  box = reader.pages[0].mediabox
  assert float(box.width) == pytest.approx(spec.page_w * 72 / 25.4, abs=0.5)
  assert float(box.height) == pytest.approx(spec.page_h * 72 / 25.4, abs=0.5)


def test_every_code_in_a_printed_pdf_scans(tmp_path):
  """Render a two-page PDF, rasterize it, and scan every cell back."""
  if shutil.which("pdftoppm") is None:
    _missing("poppler's pdftoppm", "rasterize the PDF")

  spec = PRESETS[DEFAULT_PRESET]
  total = spec.per_page + 3
  ids = [f"BIN-{n:03d}" for n in range(1, total + 1)]
  expected = [payloads.storage_label(i, base_url="inv.example.com") for i in ids]

  out = tmp_path / "sheet.pdf"
  render_sheet(
    [Label(payload=p, caption=i) for i, p in zip(ids, expected, strict=True)],
    out,
    spec=spec,
  )
  subprocess.run(
    ["pdftoppm", "-r", str(PDF_DPI), "-png", str(out), str(tmp_path / "page")],
    check=True,
    capture_output=True,
    timeout=120,
  )

  failures = []
  for index, want in enumerate(expected):
    page_number, cell_index = divmod(index, spec.per_page)
    sheet = cv2.imread(str(tmp_path / f"page-{page_number + 1}.png"))
    code = _crop_qr(sheet, spec, cell_index, PDF_DPI / 25.4)
    got = scan(code)
    if got != want:
      failures.append((ids[index], want, got))
  assert not failures


def _crop_qr(sheet, spec, index: int, px_per_mm: float):
  """Crop the square at the leading edge of cell `index`.

  Derived from the sheet spec alone, never from the layout code under test -
  otherwise a mis-placed code would simply drag the crop along with it and
  the test would pass regardless.
  """
  x, y = spec.origin(index)
  left = int(x * px_per_mm)
  top = int(y * px_per_mm)
  size = int(spec.cell_h * px_per_mm)
  return sheet[top : top + size, left : left + size]
