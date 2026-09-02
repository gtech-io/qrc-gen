import pytest

from qrc_gen import payloads


class TestURL:
  def test_adds_https_when_scheme_missing(self):
    assert payloads.url("example.com/docs") == "https://example.com/docs"

  def test_keeps_existing_scheme(self):
    assert payloads.url("http://example.com") == "http://example.com"

  def test_rejects_empty(self):
    with pytest.raises(ValueError):
      payloads.url("   ")


class TestEmail:
  def test_bare_address(self):
    assert payloads.email("ada@example.com") == "mailto:ada@example.com"

  def test_percent_encodes_subject_and_body(self):
    got = payloads.email("ada@example.com", subject="Hi there", body="a&b")
    assert got == "mailto:ada@example.com?subject=Hi%20there&body=a%26b"

  def test_rejects_non_address(self):
    with pytest.raises(ValueError):
      payloads.email("not-an-address")


class TestPhone:
  def test_strips_formatting(self):
    assert payloads.phone("+1 (555) 010-9999") == "tel:+15550109999"

  def test_sms_with_message(self):
    assert payloads.sms("5550109999", "on my way") == "SMSTO:5550109999:on my way"

  def test_rejects_number_without_digits(self):
    with pytest.raises(ValueError):
      payloads.phone("++")


class TestContact:
  def test_splits_name_into_vcard_n_field(self):
    card = payloads.Contact(name="Ada Lovelace")
    assert "N:Lovelace;Ada;;;" in payloads.contact(card)

  def test_single_word_name(self):
    assert "N:Prince;;;;" in payloads.contact(payloads.Contact(name="Prince"))

  def test_escapes_separator_characters(self):
    card = payloads.Contact(name="Ada", org="Analytical; Engines, Ltd")
    assert r"ORG:Analytical\; Engines\, Ltd" in payloads.contact(card)

  def test_normalizes_urls(self):
    card = payloads.Contact(name="Ada", urls=["example.com"])
    assert "URL:https://example.com" in payloads.contact(card)

  def test_uses_crlf_line_endings(self):
    # vCard requires CRLF; some Android scanners drop fields without it.
    assert payloads.contact(payloads.Contact(name="Ada")).startswith(
      "BEGIN:VCARD\r\nVERSION:3.0\r\n"
    )

  def test_rejects_blank_name(self):
    with pytest.raises(ValueError):
      payloads.contact(payloads.Contact(name="  "))


class TestStorageLabel:
  def test_bare_identifier(self):
    assert payloads.storage_label("BIN-042") == "BIN-042"

  def test_resolves_against_base_url(self):
    got = payloads.storage_label("BIN-042", base_url="inv.example.com/")
    assert got == "https://inv.example.com/BIN-042"

  def test_url_encodes_identifier_and_extras(self):
    got = payloads.storage_label(
      "BIN 42/A", base_url="inv.example.com", extras={"loc": "shelf 3"}
    )
    assert got == "https://inv.example.com/BIN%2042%2FA?loc=shelf%203"

  def test_extras_without_base_url_become_lines(self):
    got = payloads.storage_label("BIN-042", extras={"loc": "shelf 3"})
    assert got == "BIN-042\nloc=shelf 3"

  def test_rejects_empty_identifier(self):
    with pytest.raises(ValueError):
      payloads.storage_label("")
