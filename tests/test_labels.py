import pytest

from qrc_gen.labels import PRESETS, Label, SheetSpec, render_sheet
from qrc_gen.labels.layout import (
  CAPTION_FONT,
  fit,
  unsupported_characters,
  width_mm,
)

SPEC = SheetSpec(
  "test", page_w=100, page_h=100, cols=2, rows=2,
  cell_w=40, cell_h=20, margin_x=5, margin_y=5, gutter_x=2, gutter_y=3,
)


class TestGeometry:
  def test_per_page(self):
    assert SPEC.per_page == 4

  def test_first_cell_sits_at_the_margin(self):
    assert SPEC.origin(0) == (5, 5)

  def test_second_column_clears_the_gutter(self):
    assert SPEC.origin(1) == (5 + 40 + 2, 5)

  def test_second_row_clears_the_gutter(self):
    assert SPEC.origin(2) == (5, 5 + 20 + 3)

  @pytest.mark.parametrize("name", sorted(PRESETS))
  def test_presets_fit_on_their_page(self, name):
    spec = PRESETS[name]
    width = spec.margin_x * 2 + spec.cols * spec.cell_w + (spec.cols - 1) * spec.gutter_x
    height = spec.margin_y * 2 + spec.rows * spec.cell_h + (spec.rows - 1) * spec.gutter_y
    assert width <= spec.page_w + 0.01, f"{name} is {width}mm wide"
    assert height <= spec.page_h + 0.01, f"{name} is {height}mm tall"


class TestRenderSheet:
  def test_single_page(self, tmp_path):
    out = tmp_path / "sheet.svg"
    written = render_sheet([Label("A"), Label("B")], out, spec=SPEC)
    assert written == [out]
    assert out.read_text().startswith("<svg")

  def test_overflow_spills_onto_numbered_pages(self, tmp_path):
    out = tmp_path / "sheet.svg"
    written = render_sheet([Label(str(i)) for i in range(6)], out, spec=SPEC)
    assert [p.name for p in written] == ["sheet.svg", "sheet-2.svg"]

  def test_skip_pushes_labels_past_used_cells(self, tmp_path):
    out = tmp_path / "sheet.svg"
    render_sheet([Label("A")], out, spec=SPEC, skip=3)
    svg = out.read_text()
    # The only QR on the page must sit in the last cell, not the first.
    assert f"translate({SPEC.origin(3)[0] + 2.5:.3f}" in svg
    assert f"translate({SPEC.origin(0)[0] + 2.5:.3f}" not in svg

  def test_skip_beyond_the_page_is_rejected(self, tmp_path):
    with pytest.raises(ValueError):
      render_sheet([Label("A")], tmp_path / "s.svg", spec=SPEC, skip=SPEC.per_page)

  def test_empty_label_list_is_rejected(self, tmp_path):
    with pytest.raises(ValueError):
      render_sheet([], tmp_path / "s.svg", spec=SPEC)

  def test_caption_is_xml_escaped(self, tmp_path):
    out = tmp_path / "sheet.svg"
    render_sheet([Label("A", caption="R&D")], out, spec=SPEC)
    assert "R&amp;D" in out.read_text()

  def test_long_caption_is_truncated(self, tmp_path):
    out = tmp_path / "sheet.svg"
    render_sheet([Label("A", caption="x" * 200)], out, spec=SPEC)
    assert "…" in out.read_text()

  def test_cut_lines_are_off_by_default(self, tmp_path):
    out = tmp_path / "sheet.svg"
    render_sheet([Label("A")], out, spec=SPEC)
    assert 'stroke="#cccccc"' not in out.read_text()


class TestFormatDispatch:
  def test_rejects_unknown_extension(self, tmp_path):
    with pytest.raises(ValueError, match="unsupported sheet format"):
      render_sheet([Label("A")], tmp_path / "sheet.png", spec=SPEC)

  def test_pdf_keeps_every_page_in_one_file(self, tmp_path):
    out = tmp_path / "sheet.pdf"
    written = render_sheet([Label(str(i)) for i in range(9)], out, spec=SPEC)
    assert written == [out]
    assert out.read_bytes().startswith(b"%PDF")

  def test_svg_still_spills_across_files(self, tmp_path):
    out = tmp_path / "sheet.svg"
    written = render_sheet([Label(str(i)) for i in range(9)], out, spec=SPEC)
    assert len(written) == 3


class TestTextFitting:
  """Truncation uses real Helvetica metrics, not a characters-wide guess."""

  def test_short_text_is_untouched(self):
    assert fit("BIN-001", CAPTION_FONT, 4.2, 40) == "BIN-001"

  def test_long_text_gains_an_ellipsis(self):
    got = fit("Extremely long caption text here", CAPTION_FONT, 4.2, 20)
    assert got.endswith("…") and got != "…"

  def test_result_actually_fits(self):
    for available in (10, 15, 20, 30):
      got = fit("Extremely long caption text here", CAPTION_FONT, 4.2, available)
      assert width_mm(got, CAPTION_FONT, 4.2) <= available

  def test_wide_text_truncates_sooner_than_narrow_text(self):
    # A metrics-blind implementation would cut both at the same length.
    assert len(fit("W" * 40, CAPTION_FONT, 4.2, 20)) < len(
      fit("i" * 40, CAPTION_FONT, 4.2, 20)
    )


class TestPdfTextCoverage:
  def test_plain_ascii_is_supported(self):
    assert unsupported_characters("BIN-001 / shelf 3") == ""

  def test_latin1_accents_are_supported(self):
    assert unsupported_characters("Café naïve — Zürich…") == ""

  def test_cjk_is_flagged(self):
    assert unsupported_characters("日本語") == "日本語"

  def test_each_character_is_reported_once(self):
    assert unsupported_characters("日日日") == "日"

  def test_warns_when_writing_a_pdf(self, tmp_path):
    with pytest.warns(UserWarning, match="may not render in PDF"):
      render_sheet([Label("A", caption="日本語")], tmp_path / "s.pdf", spec=SPEC)

  def test_stays_quiet_for_svg(self, tmp_path, recwarn):
    render_sheet([Label("A", caption="日本語")], tmp_path / "s.svg", spec=SPEC)
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]
