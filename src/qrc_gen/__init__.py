"""Generate QR codes for contacts, links and printable storage labels."""

# Note: the render helpers are deliberately not re-exported here. `render` is
# also a submodule name, and shadowing it breaks `from qrc_gen import render`.
from .payloads import Contact, contact, email, phone, sms, storage_label, url

__version__ = "0.1.0"

__all__ = [
  "Contact",
  "__version__",
  "contact",
  "email",
  "phone",
  "sms",
  "storage_label",
  "url",
]
