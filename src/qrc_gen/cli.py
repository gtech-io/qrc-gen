"""qrc - generate QR codes for contacts, phones, emails, URLs and storage labels."""

from __future__ import annotations

import csv
import sys
import warnings
from pathlib import Path
from typing import Annotated

import typer

from . import labels as labels_mod
from . import payloads, render
from .labels import PRESETS, Label, SheetSpec, render_sheet
from .render import ErrorLevel

app = typer.Typer(name="qrc", help=__doc__, no_args_is_help=True, add_completion=True)

# --- Options shared by every payload command ---------------------------------

Output = Annotated[
  Path | None,
  typer.Option(
    "--output",
    "-o",
    help="Write to this file (.png .svg .eps .pdf .txt). Omit to draw in the terminal.",
  ),
]
Error = Annotated[
  str,
  typer.Option(
    "--error",
    "-e",
    help="Error correction: l=7% m=15% q=25% h=30% recoverable. Use h on labels that get scuffed.",
  ),
]
Scale = Annotated[
  int, typer.Option("--scale", "-s", min=1, help="Pixels (or points) per QR module.")
]
Border = Annotated[
  int, typer.Option("--border", "-b", min=0, help="Quiet-zone width, in modules.")
]
Dark = Annotated[str, typer.Option("--dark", help="Colour of the dark modules.")]
Light = Annotated[
  str, typer.Option("--light", help="Background colour, or 'none' for transparent.")
]
ShowPayload = Annotated[
  bool,
  typer.Option("--print-payload", help="Print the encoded string instead of a QR code."),
]

# --- Command-specific options ------------------------------------------------

Subject = Annotated[
  str | None, typer.Option("--subject", help="Pre-filled subject line.")
]
Body = Annotated[str | None, typer.Option("--body", help="Pre-filled message body.")]
Message = Annotated[
  str | None, typer.Option("--message", "-m", help="Pre-filled message.")
]
Name = Annotated[str, typer.Option("--name", "-n", help="Full name, e.g. 'Ada Lovelace'.")]
Org = Annotated[str | None, typer.Option("--org", help="Organisation.")]
Title = Annotated[str | None, typer.Option("--title", help="Job title.")]
Phones = Annotated[
  list[str] | None, typer.Option("--phone", help="Phone number. Repeatable.")
]
Emails = Annotated[
  list[str] | None, typer.Option("--email", help="Email address. Repeatable.")
]
Urls = Annotated[list[str] | None, typer.Option("--url", help="Website. Repeatable.")]
Address = Annotated[
  str | None, typer.Option("--address", help="Street address, on one line.")
]
Note = Annotated[str | None, typer.Option("--note", help="Free-text note.")]
BaseUrl = Annotated[
  str | None, typer.Option("--base-url", help="Resolve the id against this URL.")
]
Extras = Annotated[
  list[str] | None, typer.Option("--extra", help="Extra key=value pair. Repeatable.")
]


def _emit(
  payload: str,
  output: Path | None,
  error: str,
  scale: int,
  border: int,
  dark: str,
  light: str,
  print_payload: bool = False,
) -> None:
  """Shared tail end of every payload command."""
  if print_payload:
    typer.echo(payload)
    return
  try:
    art = render.render(
      payload,
      output,
      error=_error_level(error),
      scale=scale,
      border=border,
      dark=dark,
      light=None if light.lower() == "none" else light,
    )
  except ValueError as exc:
    raise typer.BadParameter(str(exc)) from exc
  if art is not None:
    typer.echo(art)
  else:
    typer.echo(f"Wrote {output}", err=True)


def _error_level(value: str) -> ErrorLevel:
  level = value.lower()
  if level not in ("l", "m", "q", "h"):
    raise typer.BadParameter("--error must be one of: l, m, q, h")
  return level  # type: ignore[return-value]


def _guard(builder, *args, **kwargs) -> str:
  """Turn a payload builder's ValueError into a clean CLI error."""
  try:
    return builder(*args, **kwargs)
  except ValueError as exc:
    raise typer.BadParameter(str(exc)) from exc


@app.command()
def url(
  address: Annotated[str, typer.Argument(help="URL. https:// is assumed if omitted.")],
  output: Output = None,
  error: Error = "m",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode a web address."""
  payload = _guard(payloads.url, address)
  _emit(payload, output, error, scale, border, dark, light, print_payload)


@app.command()
def email(
  address: Annotated[str, typer.Argument(help="Destination email address.")],
  subject: Subject = None,
  body: Body = None,
  output: Output = None,
  error: Error = "m",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode a mailto: link, optionally with a subject and body."""
  payload = _guard(payloads.email, address, subject, body)
  _emit(payload, output, error, scale, border, dark, light, print_payload)


@app.command()
def phone(
  number: Annotated[str, typer.Argument(help="Phone number. Punctuation is ignored.")],
  output: Output = None,
  error: Error = "m",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode a phone number that dials when scanned."""
  payload = _guard(payloads.phone, number)
  _emit(payload, output, error, scale, border, dark, light, print_payload)


@app.command()
def sms(
  number: Annotated[str, typer.Argument(help="Phone number to text.")],
  message: Message = None,
  output: Output = None,
  error: Error = "m",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode a pre-addressed text message."""
  payload = _guard(payloads.sms, number, message)
  _emit(payload, output, error, scale, border, dark, light, print_payload)


@app.command()
def text(
  content: Annotated[str, typer.Argument(help="Arbitrary text to encode.")],
  output: Output = None,
  error: Error = "m",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode plain text, unmodified."""
  _emit(content, output, error, scale, border, dark, light, print_payload)


@app.command()
def contact(
  name: Name,
  org: Org = None,
  title: Title = None,
  phone_numbers: Phones = None,
  emails: Emails = None,
  urls: Urls = None,
  address: Address = None,
  note: Note = None,
  output: Output = None,
  error: Error = "m",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode contact details as a vCard."""
  card = payloads.Contact(
    name=name,
    org=org,
    title=title,
    phones=list(phone_numbers or []),
    emails=list(emails or []),
    urls=list(urls or []),
    address=address,
    note=note,
  )
  payload = _guard(payloads.contact, card)
  _emit(payload, output, error, scale, border, dark, light, print_payload)


@app.command()
def label(
  identifier: Annotated[str, typer.Argument(help="Label id, e.g. BIN-042.")],
  base_url: BaseUrl = None,
  extra: Extras = None,
  output: Output = None,
  error: Error = "h",
  scale: Scale = 8,
  border: Border = 4,
  dark: Dark = "#000000",
  light: Light = "#ffffff",
  print_payload: ShowPayload = False,
) -> None:
  """Encode a single storage-container label."""
  payload = _guard(payloads.storage_label, identifier, base_url, _parse_extras(extra))
  _emit(payload, output, error, scale, border, dark, light, print_payload)


def _parse_extras(extras: list[str] | None) -> dict[str, str]:
  parsed: dict[str, str] = {}
  for item in extras or []:
    key, sep, value = item.partition("=")
    if not sep or not key:
      raise typer.BadParameter(f"--extra expects key=value, got {item!r}")
    parsed[key] = value
  return parsed


# --- Sheet options -----------------------------------------------------------

SheetOutput = Annotated[
  Path,
  typer.Option(
    "--output",
    "-o",
    help=(
      "File to write. .pdf puts every page in one file and is what you want "
      "for printing; .svg writes one file per page."
    ),
  ),
]
CsvFile = Annotated[
  Path | None,
  typer.Option(
    "--csv",
    help="CSV with an id (or payload) column plus optional caption and subtitle. '-' reads stdin.",
  ),
]
Prefix = Annotated[
  str | None,
  typer.Option("--prefix", help="Generate sequential ids with this prefix, e.g. BIN-."),
]
Count = Annotated[
  int, typer.Option("--count", min=1, help="How many sequential ids to generate.")
]
Start = Annotated[int, typer.Option("--start", min=0, help="First number in the run.")]
Pad = Annotated[
  int, typer.Option("--pad", min=1, help="Zero-pad sequential numbers to this width.")
]
Subtitle = Annotated[
  str | None, typer.Option("--subtitle", help="Second line printed on every label.")
]
Preset = Annotated[
  str, typer.Option("--preset", "-p", help="Label stock. Run `qrc presets` to list them.")
]
Skip = Annotated[
  int,
  typer.Option("--skip", min=0, help="Leave this many cells blank on the first page."),
]
CutLines = Annotated[
  bool, typer.Option("--cut-lines", help="Draw cell outlines as cutting guides.")
]


@app.command()
def sheet(
  output: SheetOutput,
  csv_file: CsvFile = None,
  prefix: Prefix = None,
  count: Count = 1,
  start: Start = 1,
  pad: Pad = 3,
  base_url: BaseUrl = None,
  subtitle: Subtitle = None,
  preset: Preset = labels_mod.DEFAULT_PRESET,
  skip: Skip = 0,
  cut_lines: CutLines = False,
  error: Error = "h",
) -> None:
  """Lay out a printable sheet of storage labels.

  Source the labels from a CSV, or generate a numbered run with --prefix.
  """
  spec = _preset(preset)
  items = _sheet_labels(csv_file, prefix, count, start, pad, base_url, subtitle)
  try:
    with warnings.catch_warnings(record=True) as caught:
      warnings.simplefilter("always")
      written = render_sheet(
        items,
        output,
        spec=spec,
        error=_error_level(error),
        skip=skip,
        show_cut_lines=cut_lines,
      )
  except ValueError as exc:
    raise typer.BadParameter(str(exc)) from exc
  for warning in caught:
    typer.echo(f"warning: {warning.message}", err=True)
  pages = -(-(len(items) + skip) // spec.per_page)
  typer.echo(
    f"Wrote {len(items)} labels across {pages} page(s) on {spec.name}: "
    + ", ".join(str(path) for path in written),
    err=True,
  )


def _preset(name: str) -> SheetSpec:
  try:
    return PRESETS[name]
  except KeyError:
    raise typer.BadParameter(
      f"unknown preset {name!r}; choose from: {', '.join(sorted(PRESETS))}"
    ) from None


def _sheet_labels(
  csv_file: Path | None,
  prefix: str | None,
  count: int,
  start: int,
  pad: int,
  base_url: str | None,
  subtitle: str | None,
) -> list[Label]:
  if (csv_file is None) == (prefix is None):
    raise typer.BadParameter("pass exactly one of --csv or --prefix")

  if prefix is not None:
    ids = [f"{prefix}{n:0{pad}d}" for n in range(start, start + count)]
    rows = [{"id": i, "caption": i, "subtitle": subtitle or ""} for i in ids]
  else:
    rows = _read_csv(csv_file)  # type: ignore[arg-type]
    if not rows:
      raise typer.BadParameter(f"no rows found in {csv_file}")

  out: list[Label] = []
  for row in rows:
    identifier = (row.get("id") or "").strip()
    payload = (row.get("payload") or "").strip()
    if payload:
      encoded = payload
    elif identifier:
      encoded = _guard(payloads.storage_label, identifier, base_url)
    else:
      raise typer.BadParameter("each CSV row needs an 'id' or a 'payload' column")
    out.append(
      Label(
        payload=encoded,
        caption=(row.get("caption") or identifier or "").strip(),
        subtitle=(row.get("subtitle") or subtitle or "").strip(),
      )
    )
  return out


def _read_csv(path: Path) -> list[dict[str, str]]:
  if str(path) == "-":
    return list(csv.DictReader(sys.stdin))
  if not path.exists():
    raise typer.BadParameter(f"no such file: {path}")
  with path.open(newline="", encoding="utf-8") as handle:
    return list(csv.DictReader(handle))


@app.command()
def presets() -> None:
  """List the built-in label-sheet layouts."""
  for name, spec in sorted(PRESETS.items()):
    typer.echo(
      f"{name:<14} {spec.cols}x{spec.rows} = {spec.per_page:>2} per page  "
      f"({spec.cell_w:g} x {spec.cell_h:g} mm on {spec.page_w:g} x {spec.page_h:g} mm)"
    )


def main() -> None:
  app()


if __name__ == "__main__":
  main()
