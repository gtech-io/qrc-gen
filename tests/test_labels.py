import pytest

from qrc_gen.labels import PRESETS, Label, SheetSpec, render_sheet

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
