"""Stage 2 of noise reduction: strip an 8-K down to its narrative text.

A raw 8-K submission file is mostly not prose. It carries an SGML header, inline
XBRL, base64-encoded graphics, CSS, and exhibit attachments that are often
larger than the filing itself. The text that actually announces a transaction is
usually a few thousand characters inside a file of several hundred thousand.

`clean` removes the non-narrative parts and reports how much it removed, so the
reduction is measured on real documents rather than asserted.
"""

from __future__ import annotations

import re
from html import unescape

# Order matters: encoded blobs and script/style go before generic tag removal,
# otherwise their contents survive as text.
GRAPHIC_BLOCK = re.compile(r"(?is)<DOCUMENT>\s*<TYPE>(?:GRAPHIC|ZIP|EXCEL|JSON|XML).*?</DOCUMENT>")
SGML_HEADER = re.compile(r"(?is)<SEC-HEADER>.*?</SEC-HEADER>")
SCRIPT_STYLE = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")
XBRL_BLOCK = re.compile(r"(?is)<(ix:header|xbrl)[^>]*>.*?</\1>")
COMMENT = re.compile(r"(?s)<!--.*?-->")
TAG = re.compile(r"<[^>]+>")
ENTITY_SPACE = re.compile(r"&nbsp;|&#160;|\u00a0")
WHITESPACE = re.compile(r"[ \t]+")
BLANK_LINES = re.compile(r"\n\s*\n+")

# Boilerplate that appears in essentially every filing and carries no signal.
BOILERPLATE = [
    re.compile(r"(?i)pursuant to the requirements of the securities exchange act.{0,400}"),
    re.compile(r"(?i)the information (?:in|furnished under) this (?:item|current report).{0,300}"),
    re.compile(r"(?i)forward-looking statements.{0,1200}"),
    re.compile(r"(?i)check the appropriate box below.{0,600}"),
    re.compile(r"(?i)securities registered pursuant to section 12\(b\).{0,400}"),
]


def strip_markup(raw):
    text = SGML_HEADER.sub(" ", raw)
    text = GRAPHIC_BLOCK.sub(" ", text)
    text = COMMENT.sub(" ", text)
    text = SCRIPT_STYLE.sub(" ", text)
    text = XBRL_BLOCK.sub(" ", text)
    text = TAG.sub(" ", text)
    text = ENTITY_SPACE.sub(" ", text)
    text = unescape(text)
    text = WHITESPACE.sub(" ", text)
    return BLANK_LINES.sub("\n\n", text).strip()


def strip_boilerplate(text):
    for pattern in BOILERPLATE:
        text = pattern.sub(" ", text)
    return WHITESPACE.sub(" ", text).strip()


def clean(raw):
    """Return (text, metrics). Metrics are what the noise measurement reports."""
    original = len(raw)
    markup_stripped = strip_markup(raw)
    final = strip_boilerplate(markup_stripped)

    removed = original - len(final)
    return final, {
        "chars_in": original,
        "chars_after_markup": len(markup_stripped),
        "chars_out": len(final),
        "chars_removed": removed,
        "reduction": round(removed / original, 4) if original else 0.0,
    }


def find_item_numbers(text):
    """Recover item numbers from the cleaned text when metadata didn't carry them."""
    return re.findall(r"(?i)item\s+(\d{1,2}\.\d{2})", text)
