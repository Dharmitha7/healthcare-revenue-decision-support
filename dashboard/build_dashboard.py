"""Embed data.json into template.html to produce index.html (self-contained, opens without a server)."""
from pathlib import Path

d = Path(__file__).parent
html = (d / "template.html").read_text(encoding="utf8").replace("__DATA__", (d / "data.json").read_text())
(d / "index.html").write_text(html, encoding="utf8")
