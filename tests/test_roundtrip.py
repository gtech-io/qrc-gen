"""End-to-end check: render a QR, then decode it with an independent library.

Skipped unless the optional `decode` dependency group is installed
(`uv sync --group decode`), because OpenCV is a heavy dependency to carry
just for a test. CI always runs it.
"""

import pytest

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


def decode(path) -> str:
  data, *_ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(path)))
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
    pytest.skip("no Chrome/Chromium available to rasterize the SVG")

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
  detector = cv2.QRCodeDetector()
  failures = []
  for index, want in enumerate(expected):
    x, y = spec.origin(index)
    cell = sheet[
      int(y * PX_PER_MM) : int((y + spec.cell_h) * PX_PER_MM),
      int(x * PX_PER_MM) : int((x + spec.cell_w) * PX_PER_MM),
    ]
    got, *_ = detector.detectAndDecode(cell)
    if got != want:
      failures.append((ids[index], want, got))
  assert not failures


def _find_chrome() -> str | None:
  import shutil

  for name in ("google-chrome", "chromium", "chromium-browser", "google-chrome-stable"):
    found = shutil.which(name)
    if found:
      return found
  return None


def _rasterize(chrome: str, svg, png) -> None:
  import subprocess

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
