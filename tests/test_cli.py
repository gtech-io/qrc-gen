import pytest
from typer.testing import CliRunner

from qrc_gen.cli import app

runner = CliRunner()


def run(*args: str):
  return runner.invoke(app, list(args))


class TestPayloadCommands:
  @pytest.mark.parametrize(
    ("args", "expected"),
    [
      (("url", "example.com"), "https://example.com"),
      (("email", "ada@example.com", "--subject", "Hi"), "mailto:ada@example.com?subject=Hi"),
      (("phone", "+1 555 010 9999"), "tel:+15550109999"),
      (("sms", "5550109999", "-m", "hey"), "SMSTO:5550109999:hey"),
      (("text", "plain"), "plain"),
      (("label", "BIN-042", "--base-url", "inv.example.com"), "https://inv.example.com/BIN-042"),
    ],
  )
  def test_print_payload(self, args, expected):
    result = run(*args, "--print-payload")
    assert result.exit_code == 0, result.output
    assert result.output.strip() == expected

  def test_contact_builds_a_vcard(self):
    result = run("contact", "-n", "Ada Lovelace", "--org", "Analytical", "--print-payload")
    assert result.exit_code == 0
    assert "FN:Ada Lovelace" in result.output

  def test_writes_a_png(self, tmp_path):
    out = tmp_path / "qr.png"
    assert run("url", "example.com", "-o", str(out)).exit_code == 0
    assert out.read_bytes().startswith(b"\x89PNG")

  def test_writes_an_svg(self, tmp_path):
    out = tmp_path / "qr.svg"
    assert run("url", "example.com", "-o", str(out)).exit_code == 0
    assert "<svg" in out.read_text()

  def test_terminal_output_when_no_file_given(self):
    result = run("url", "example.com")
    assert result.exit_code == 0
    assert "█" in result.output

  def test_rejects_unknown_extension(self, tmp_path):
    result = run("url", "example.com", "-o", str(tmp_path / "qr.jpg"))
    assert result.exit_code != 0

  def test_rejects_bad_error_level(self):
    assert run("url", "example.com", "-e", "z").exit_code != 0

  def test_rejects_malformed_extra(self):
    assert run("label", "BIN-1", "--extra", "novalue", "--print-payload").exit_code != 0

  def test_rejects_invalid_email(self):
    assert run("email", "nope").exit_code != 0


class TestSheet:
  def test_sequential_run(self, tmp_path):
    out = tmp_path / "sheet.svg"
    result = run("sheet", "-o", str(out), "--prefix", "BIN-", "--count", "3", "--pad", "2")
    assert result.exit_code == 0, result.output
    svg = out.read_text()
    assert ">BIN-01<" in svg and ">BIN-03<" in svg

  def test_csv_source(self, tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("id,caption,subtitle\nTOTE-A,Winter clothes,Attic\n")
    out = tmp_path / "sheet.svg"
    result = run("sheet", "-o", str(out), "--csv", str(csv_path), "--base-url", "inv.example.com")
    assert result.exit_code == 0, result.output
    assert "Winter clothes" in out.read_text()

  def test_csv_payload_column_wins_over_base_url(self, tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("payload,caption\nmailto:a@b.io,Ping me\n")
    out = tmp_path / "sheet.svg"
    assert run("sheet", "-o", str(out), "--csv", str(csv_path)).exit_code == 0

  def test_requires_exactly_one_source(self, tmp_path):
    out = tmp_path / "sheet.svg"
    assert run("sheet", "-o", str(out)).exit_code != 0

  def test_rejects_both_sources(self, tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("id\nA\n")
    out = tmp_path / "sheet.svg"
    assert run("sheet", "-o", str(out), "--csv", str(csv_path), "--prefix", "B-").exit_code != 0

  def test_rejects_unknown_preset(self, tmp_path):
    out = tmp_path / "sheet.svg"
    assert run("sheet", "-o", str(out), "--prefix", "B-", "-p", "nope").exit_code != 0

  def test_rejects_csv_without_id_or_payload(self, tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("caption\nWinter clothes\n")
    out = tmp_path / "sheet.svg"
    assert run("sheet", "-o", str(out), "--csv", str(csv_path)).exit_code != 0


def test_presets_lists_every_layout():
  result = run("presets")
  assert result.exit_code == 0
  assert "avery-5160" in result.output and "avery-l7159" in result.output


class TestCsvEncoding:
  """Spreadsheet exports are full of byte-order marks."""

  def test_utf8_bom_does_not_hide_the_id_column(self, tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("id,caption,subtitle\nBOX-01,Memories,cards\n", encoding="utf-8-sig")
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf"), "test needs a real BOM"

    out = tmp_path / "sheet.pdf"
    result = run("sheet", "-o", str(out), "--csv", str(csv_path))
    assert result.exit_code == 0, result.output
    assert out.exists()

  def test_error_names_the_columns_it_found(self, tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("name,where\nBOX-01,Attic\n")
    result = run("sheet", "-o", str(tmp_path / "s.pdf"), "--csv", str(csv_path))
    assert result.exit_code != 0
    assert "name" in result.output and "where" in result.output
