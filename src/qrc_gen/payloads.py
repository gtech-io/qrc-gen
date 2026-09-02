"""Builders that turn structured input into the string a QR code encodes.

Every builder returns plain text. Rendering happens elsewhere, so these are
cheap to unit-test and easy to reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote

__all__ = [
  "Contact",
  "contact",
  "email",
  "phone",
  "sms",
  "storage_label",
  "url",
]


def url(value: str) -> str:
  """Normalize a URL, defaulting to https:// when no scheme is given."""
  value = value.strip()
  if not value:
    raise ValueError("URL must not be empty")
  if "://" not in value:
    value = f"https://{value}"
  return value


def email(
  address: str,
  subject: str | None = None,
  body: str | None = None,
) -> str:
  """Build a mailto: URI, optionally pre-filling subject and body."""
  address = address.strip()
  if "@" not in address:
    raise ValueError(f"not a valid email address: {address!r}")
  params = []
  if subject:
    params.append(f"subject={quote(subject)}")
  if body:
    params.append(f"body={quote(body)}")
  query = f"?{'&'.join(params)}" if params else ""
  return f"mailto:{address}{query}"


def phone(number: str) -> str:
  """Build a tel: URI. Scanners dial this straight from the camera app."""
  return f"tel:{_clean_number(number)}"


def sms(number: str, message: str | None = None) -> str:
  """Build an SMSTO: payload, the format Android and iOS both understand."""
  base = f"SMSTO:{_clean_number(number)}"
  return f"{base}:{message}" if message else base


def _clean_number(number: str) -> str:
  cleaned = "".join(ch for ch in number if ch.isdigit() or ch == "+")
  if not cleaned.strip("+"):
    raise ValueError(f"not a valid phone number: {number!r}")
  return cleaned


@dataclass(slots=True)
class Contact:
  """The subset of vCard fields worth putting on a QR code."""

  name: str
  org: str | None = None
  title: str | None = None
  phones: list[str] = field(default_factory=list)
  emails: list[str] = field(default_factory=list)
  urls: list[str] = field(default_factory=list)
  address: str | None = None
  note: str | None = None


def contact(card: Contact) -> str:
  """Serialize a contact as vCard 3.0.

  3.0 rather than 4.0 on purpose: it is what iOS and Android camera apps
  parse reliably, and 4.0 buys nothing at this size.
  """
  if not card.name.strip():
    raise ValueError("contact name must not be empty")

  lines = ["BEGIN:VCARD", "VERSION:3.0"]
  lines.append(f"N:{_structured_name(card.name)}")
  lines.append(f"FN:{_esc(card.name)}")
  if card.org:
    lines.append(f"ORG:{_esc(card.org)}")
  if card.title:
    lines.append(f"TITLE:{_esc(card.title)}")
  for number in card.phones:
    lines.append(f"TEL;TYPE=CELL:{_clean_number(number)}")
  for address in card.emails:
    lines.append(f"EMAIL;TYPE=INTERNET:{_esc(address)}")
  for link in card.urls:
    lines.append(f"URL:{_esc(url(link))}")
  if card.address:
    lines.append(f"ADR;TYPE=WORK:;;{_esc(card.address)}")
  if card.note:
    lines.append(f"NOTE:{_esc(card.note)}")
  lines.append("END:VCARD")
  return "\r\n".join(lines)


def _structured_name(full_name: str) -> str:
  """Split "Ada Lovelace" into the vCard N field: Last;First;;;"""
  parts = full_name.split()
  if len(parts) == 1:
    return f"{_esc(parts[0])};;;;"
  last = _esc(parts[-1])
  first = _esc(" ".join(parts[:-1]))
  return f"{last};{first};;;"


def _esc(value: str) -> str:
  """Escape the characters vCard treats as separators (RFC 6350 3.4)."""
  return (
    value.replace("\\", "\\\\")
    .replace(";", "\\;")
    .replace(",", "\\,")
    .replace("\n", "\\n")
  )


def storage_label(
  identifier: str,
  base_url: str | None = None,
  extras: dict[str, str] | None = None,
) -> str:
  """Payload for a physical storage label (a bin, tote, or box).

  With --base-url the code resolves to an inventory page; without one it
  encodes the bare identifier, plus any key=value extras.
  """
  identifier = identifier.strip()
  if not identifier:
    raise ValueError("label id must not be empty")

  if base_url:
    root = url(base_url).rstrip("/")
    payload = f"{root}/{quote(identifier, safe='')}"
    if extras:
      query = "&".join(f"{quote(k)}={quote(v)}" for k, v in extras.items())
      payload = f"{payload}?{query}"
    return payload

  if not extras:
    return identifier
  pairs = "\n".join(f"{k}={v}" for k, v in extras.items())
  return f"{identifier}\n{pairs}"
