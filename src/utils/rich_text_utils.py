"""
Source-agnostic rich-text service for PlexTrac (CKE) fields.

Every PlexTrac rich-text field is a CKEditor (CKE) field. CKE accepts plain
text, Markdown, or HTML and converts all of it to HTML for rendering, and that
converted HTML is written back to the DB even without an explicit save. HTML
sanitization only runs on an in-app autosave, which never fires on PTRAC import
or API writes. Our PTRAC exporter only handles a subset of HTML, so unsanitized
(or valid-but-unsupported) HTML that survives into the stored value crashes the
export. This service does the conversion and sanitization in the import script
instead of relying on CKE, so what we send already matches the post-autosave
form the exporter expects.

Two responsibilities, split so callers can insert their own work between them
(the CSV parser restores shielded image tags between conversion and
sanitization):

* ``convert_to_cke_html`` - convert a field's declared source format
  (plain / markdown / textile / html) into HTML.
* ``sanitize_cke_html`` - normalize any HTML fragment into the exporter-safe
  form. Safe (and intended) to run on every rich-text value, including input
  that was already HTML, since arbitrary HTML can still be unsupported.

The module is stateless. Image handling is NOT here: it is coupled to the PTRAC
export shape and stays in ``CSVParser`` (which shields image markers as
placeholders across conversion and restores them before sanitization).
"""

from __future__ import annotations

import re

try:
    import markdown
except ImportError:
    markdown = None

try:
    import textile
except ImportError:
    textile = None

import utils.log_handler as logger

log = logger.log


# --- source format constants -------------------------------------------------
FORMAT_PLAIN = "plain"
FORMAT_MARKDOWN = "markdown"
FORMAT_TEXTILE = "textile"
FORMAT_HTML = "html"

SUPPORTED_FORMATS = (FORMAT_PLAIN, FORMAT_MARKDOWN, FORMAT_TEXTILE, FORMAT_HTML)


# --- known HTML tags ----------------------------------------------------------
# Outside code blocks, an ``<...>`` is treated as real HTML only when its tag
# name is in this set; anything else (``<option1|option2>``, ``<whales|dogs>``,
# ``<dradis.placeholder>``) has its angle brackets escaped so it renders as
# visible text. Angle brackets alone are valid text characters, not markup.
_KNOWN_HTML_TAGS = {
    # structural / block
    "p", "div", "span", "section", "article", "header", "footer", "main",
    "aside", "nav", "blockquote", "pre", "code", "hr", "br", "figure",
    "figcaption",
    # headings
    "h1", "h2", "h3", "h4", "h5", "h6",
    # inline formatting
    "a", "b", "i", "u", "s", "em", "strong", "mark", "small", "sub", "sup",
    "del", "ins", "abbr", "cite", "q", "kbd", "samp", "var", "wbr",
    # lists
    "ul", "ol", "li", "dl", "dt", "dd",
    # tables
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
    "col", "colgroup",
    # media
    "img",
}


# --- compiled patterns --------------------------------------------------------
# A single angle-bracket-delimited token with no nested brackets. The tag name
# is captured so it can be checked against _KNOWN_HTML_TAGS.
_TAG_TOKEN_RE = re.compile(r"<\s*/?\s*(?P<name>[a-zA-Z][a-zA-Z0-9]*)\b[^<>]*>")

_HR_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)

# <pre> blocks (covers bare <pre> and the conventional <pre><code>...</code></pre>
# code-block markup emitted by the markdown lib and CKE). Their whitespace and
# inner tags are significant and must survive every rewrite untouched.
_PRE_RE = re.compile(r"<pre\b.*?</pre>", re.IGNORECASE | re.DOTALL)
_STASH_RE = re.compile(r"\x00pre(\d+)\x00")

# HTML void elements are stored self-closed (e.g. `<img ... />`) by the CKE
# sanitizer. hr is not listed: it is stripped entirely.
_VOID_TAGS = "img|br|input|meta|link|area|base|col|embed|source|track|wbr"
_VOID_RE = re.compile(
    rf"<(?P<tag>{_VOID_TAGS})(?P<attrs>(?:\"[^\"]*\"|'[^']*'|[^>])*?)\s*/?>",
    re.IGNORECASE,
)

# Smart / typographic quotes normalized to straight ASCII quotes. Textile (and
# Word-authored source) emit these as curly quotes, often as numeric character
# references (e.g. `&#8220;`), which leak into the export as literal text. Keyed
# by Unicode code point so every representation - literal char, decimal ref, hex
# ref, named entity - collapses to the same replacement. Includes the CP1252 /
# mis-decoded control-range code points (0x91-0x94 == dec 145-148) that appear
# when a Windows-1252 quote byte is read as Latin-1.
_SMART_QUOTE_CODEPOINTS = {
    # double: " " „ ‟  and CP1252 0x93/0x94
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"', 0x93: '"', 0x94: '"',
    # single: ' ' ‚ ‛  and CP1252 0x91/0x92
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'", 0x91: "'", 0x92: "'",
}

# Named HTML entities for the smart quotes above, mapped to their code point.
_SMART_QUOTE_ENTITY_NAMES = {
    "ldquo": 0x201C, "rdquo": 0x201D, "bdquo": 0x201E,
    "lsquo": 0x2018, "rsquo": 0x2019, "sbquo": 0x201A,
}

# Matches any smart quote as a literal char, a hex ref, a decimal ref, or a
# named entity. The replacement function classifies each match by code point.
_SMART_QUOTE_RE = re.compile(
    r"[‘’‚‛“”„‟]"
    r"|&#[xX](?P<hex>[0-9A-Fa-f]+);"
    r"|&#(?P<dec>[0-9]+);"
    r"|&(?P<name>[A-Za-z]+);"
)


# --- low-level string helpers -------------------------------------------------
def escape_angle_brackets(value: str) -> str:
    """
    Escape ``<`` and ``>`` so user-entered angle-bracket text is rendered as
    literal text rather than interpreted as HTML.

    :param value: string to escape
    :return: escaped string
    :rtype: str
    """
    if not isinstance(value, str):
        return value
    return value.replace("<", "&lt;").replace(">", "&gt;")


def update_open_closing_tags(value: str, start_tag: str, end_tag: str, new_start_tag: str, new_end_tag: str, strip_br_tags: bool = False) -> str:
    """
    Replace matching open/close tag pairs while correctly handling nested pairs.

    An ``end_tag`` is only replaced when there is a currently open ``start_tag``,
    so unbalanced markers are left untouched. Set ``strip_br_tags`` to also remove
    ``<br />`` tags (legacy behavior, off by default).

    :param value: the string to process
    :param start_tag: the opening marker to match (e.g. "`{")
    :param end_tag: the closing marker to match (e.g. "}`")
    :param new_start_tag: replacement for each matched opening marker
    :param new_end_tag: replacement for each matched closing marker
    :param strip_br_tags: whether to also strip <br /> tags, defaults to False
    :return: the updated string
    :rtype: str
    """
    if not isinstance(value, str):
        return value

    result = []
    open_count = 0
    index = 0
    length = len(value)
    while index < length:
        if start_tag and value.startswith(start_tag, index):
            open_count += 1
            result.append(new_start_tag)
            index += len(start_tag)
        elif end_tag and open_count > 0 and value.startswith(end_tag, index):
            open_count -= 1
            result.append(new_end_tag)
            index += len(end_tag)
        else:
            result.append(value[index])
            index += 1

    new_value = "".join(result)
    if strip_br_tags:
        new_value = re.sub(r"<br\s*/?>", "", new_value)
    return new_value


# --- markdown converter (lazy, cached) ----------------------------------------
# GFM-style pipe tables, fenced code blocks, and predictable list handling cover
# the markdown seen in narratives, descriptions, and comments.
_MD_EXTENSIONS = ("tables", "fenced_code", "sane_lists")

_markdown_instance = None
_markdown_import_failed = False


def _get_markdown_converter():
    """
    Lazily build and cache a configured ``markdown.Markdown`` instance.

    Returns ``None`` (and logs once) if the optional ``markdown`` dependency is
    not installed, so callers degrade to leaving the raw text untouched rather
    than crashing the whole run.
    """
    global _markdown_instance, _markdown_import_failed
    if _markdown_instance is not None:
        return _markdown_instance
    if _markdown_import_failed:
        return None
    if markdown is None:
        _markdown_import_failed = True
        log.error(
            "The 'markdown' package is required for Markdown rich-text conversion "
            "but is not installed. Run 'pipenv install' to install project "
            "dependencies. Markdown fields will be left as raw text."
        )
        return None

    md = markdown.Markdown(extensions=list(_MD_EXTENSIONS))
    # Disable indented (4-space) code blocks. Fenced code is used, and incidental
    # leading whitespace (e.g. an indented image line inside numbered steps) must
    # not be reinterpreted as a code block (which would HTML-escape any tag inside
    # it). List indentation is handled by a different processor and is left
    # intact. Guard the lookup so a future markdown release cannot break import.
    try:
        md.parser.blockprocessors.deregister("code")
    except (KeyError, ValueError):
        log.debug("markdown 'code' block processor not found; leaving defaults")
    _markdown_instance = md
    return md


# --- conversion branches ------------------------------------------------------
def _convert_plain(text: str) -> str:
    """
    Convert plain text into HTML paragraphs.

    Blank lines split paragraphs; single newlines become ``<br>``. Existing tags
    are left intact (unknown-tag escaping happens later in sanitization), so
    plain text that already contains an ``<img>`` or other HTML is preserved.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for paragraph in re.split(r"\n{2,}", text):
        paragraph = paragraph.strip("\n")
        if paragraph == "":
            continue
        parts.append(f"<p>{paragraph.replace(chr(10), '<br>')}</p>")
    return "".join(parts)


def _convert_markdown(text: str) -> str:
    """Convert Markdown into HTML, leaving raw text untouched if markdown is absent."""
    md = _get_markdown_converter()
    if md is None:
        return text
    md.reset()
    return md.convert(text)


def _convert_textile(text: str) -> str:
    """
    Convert Textile (Dradis rich text) into HTML.

    Angle brackets are NOT escaped here - that is the sanitizer's known-tag pass,
    so real tags survive while Textile pseudo-tags escape. Textile inline code
    wrappers ("`{ ... }`") are removed. Degrades to the raw text if the optional
    ``textile`` dependency is unavailable or conversion fails.
    """
    if textile is None:
        html = text
    else:
        try:
            html = textile.textile(text)
        except Exception as e:
            log.warning(f"Could not convert Textile to HTML, using raw value. {e}")
            html = text
    return update_open_closing_tags(html, "`{", "}`", "", "")


# --- sanitization helpers -----------------------------------------------------
def _escape_unknown_tags(html: str) -> str:
    """
    Escape angle brackets that are not part of a recognized HTML tag.

    Recognized tags (name in ``_KNOWN_HTML_TAGS``) are kept verbatim; every other
    ``<...>`` token and every stray ``<`` / ``>`` is escaped so it renders as
    literal text. Callers must stash ``<pre>`` content first - code blocks keep
    their angle brackets verbatim and must not pass through here.
    """
    out = []
    last = 0
    for match in _TAG_TOKEN_RE.finditer(html):
        out.append(escape_angle_brackets(html[last:match.start()]))
        if match.group("name").lower() in _KNOWN_HTML_TAGS:
            out.append(match.group(0))
        else:
            out.append(escape_angle_brackets(match.group(0)))
        last = match.end()
    out.append(escape_angle_brackets(html[last:]))
    return "".join(out)


def _normalize_table_html(value: str) -> str:
    """Normalize tables into the PlexTrac ``figure > table > tbody`` shape."""
    # unwrap any tables already inside a figure so they are not double wrapped
    value = re.sub(
        r'<figure class="table">\s*(<table[^>]*>.*?</table>)\s*</figure>',
        r"\1",
        value,
        flags=re.DOTALL,
    )

    def _replace(match: "re.Match") -> str:
        inner = match.group("inner")
        rows = re.findall(r"<tr\b.*?</tr>", inner, flags=re.DOTALL)
        if not rows:
            return match.group(0)
        body = "".join(rows)
        return f'<figure class="table"><table><tbody>{body}</tbody></table></figure>'

    return re.sub(r"<table[^>]*>(?P<inner>.*?)</table>", _replace, value, flags=re.DOTALL)


def _self_close_void_elements(html: str) -> str:
    """`<img src="x">` -> `<img src="x" />`, matching the sanitizer's void form."""
    def _replace(match: "re.Match") -> str:
        attrs = match.group("attrs").strip()
        return f'<{match.group("tag").lower()}{" " + attrs if attrs else ""} />'

    return _VOID_RE.sub(_replace, html)


def _normalize_smart_quotes(text: str) -> str:
    """
    Replace smart / typographic quotes with straight ASCII quotes.

    Handles every representation - literal char, decimal or hex numeric character
    reference, and named entity - by resolving each match to a Unicode code point
    and looking it up in ``_SMART_QUOTE_CODEPOINTS``. Non-quote entities and
    references (e.g. ``&amp;``, ``&#160;``) are left untouched.
    """
    def _replace(match: "re.Match") -> str:
        if match.group("hex") is not None:
            code_point = int(match.group("hex"), 16)
        elif match.group("dec") is not None:
            code_point = int(match.group("dec"))
        elif match.group("name") is not None:
            code_point = _SMART_QUOTE_ENTITY_NAMES.get(match.group("name").lower())
        else:
            code_point = ord(match.group(0))
        if code_point is None:
            return match.group(0)
        return _SMART_QUOTE_CODEPOINTS.get(code_point, match.group(0))

    return _SMART_QUOTE_RE.sub(_replace, text)


def sanitize_cke_html(html: str) -> str:
    """
    Normalize an HTML fragment into the exporter-safe / post-autosave CKE form.

    Safe to run on HTML from any source (this module's converters or already-HTML
    input). ``<pre>`` blocks are shielded so their whitespace and inner tags
    survive verbatim; everything else is normalized: smart quotes straightened,
    escaped ``\\n``/``\\t`` artifacts removed, unknown tags escaped, ``<hr>``
    dropped, tables wrapped, void elements self-closed, inter-tag whitespace
    compacted.

    :param html: the HTML fragment to sanitize
    :return: the sanitized fragment (input returned unchanged if blank/non-string)
    :rtype: str
    """
    if not isinstance(html, str) or not html:
        return html

    stash = []

    def _capture(match: "re.Match") -> str:
        stash.append(match.group(0))
        return f"\x00pre{len(stash) - 1}\x00"

    working = _PRE_RE.sub(_capture, html)

    # normalize smart quotes to straight ASCII (code blocks are already stashed)
    working = _normalize_smart_quotes(working)

    # strip escaped newline/tab artifacts and collapse formatting whitespace
    working = working.replace("\\n", "").replace("\\t", "")
    working = re.sub(r"\n{2,}", "\n", working)
    working = re.sub(r">\s*\n\s*<", "><", working)

    working = _escape_unknown_tags(working)
    working = _HR_RE.sub("", working)
    working = _normalize_table_html(working)
    working = _self_close_void_elements(working)

    # compact inter-tag whitespace and the boundaries against stashed <pre> blocks
    working = re.sub(r">\s+<", "><", working)
    working = re.sub(r"\s+</", "</", working)
    working = re.sub(r">\s+(\x00pre\d+\x00)", r">\1", working)
    working = re.sub(r"(\x00pre\d+\x00)\s+<", r"\1<", working)
    working = working.strip()

    return _STASH_RE.sub(lambda match: stash[int(match.group(1))], working)


# --- public conversion entry points -------------------------------------------
def convert_to_cke_html(text: str, source_format: str) -> str:
    """
    Convert a rich-text value of a declared source format into HTML.

    Conversion only - no sanitization (call ``sanitize_cke_html`` after, or use
    ``process_rich_text`` for both). Returns the input unchanged when it is
    empty/whitespace or when the format is unrecognized.

    :param text: the value to convert
    :param source_format: one of ``SUPPORTED_FORMATS``
    :return: converted HTML, or the original text if conversion is skipped
    :rtype: str
    """
    if not isinstance(text, str) or not text.strip():
        return text
    if source_format == FORMAT_PLAIN:
        return _convert_plain(text)
    if source_format == FORMAT_MARKDOWN:
        return _convert_markdown(text)
    if source_format == FORMAT_TEXTILE:
        return _convert_textile(text)
    if source_format == FORMAT_HTML:
        return text
    log.warning(
        f"Unknown rich-text source format '{source_format}'. Expected one of "
        f"{SUPPORTED_FORMATS}. Leaving value unconverted."
    )
    return text


def process_rich_text(text: str, source_format: str) -> str:
    """
    Convert a value of a declared source format and sanitize it in one step.

    Convenience wrapper for callers that do not need to do work (such as image
    restoration) between conversion and sanitization.

    :param text: the value to process
    :param source_format: one of ``SUPPORTED_FORMATS``
    :return: sanitized CKE HTML, or the original text if processing is skipped
    :rtype: str
    """
    if not isinstance(text, str) or not text.strip():
        return text
    return sanitize_cke_html(convert_to_cke_html(text, source_format))
