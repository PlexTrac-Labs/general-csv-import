import pytest

import utils.rich_text_utils as rtu


# --- low-level string helpers ------------------------------------------------
def test_escape_angle_brackets_escapes_both_directions():
    assert rtu.escape_angle_brackets("<p>hi</p>") == "&lt;p&gt;hi&lt;/p&gt;"


def test_update_open_closing_tags_replaces_matching_and_nested_pairs():
    value = "`{outer `{inner}` outer}`"
    result = rtu.update_open_closing_tags(value, "`{", "}`", "<code>", "</code>")

    assert result == "<code>outer <code>inner</code> outer</code>"


def test_update_open_closing_tags_only_strips_br_when_requested():
    value = "<b>keep<br /></b>"
    without_strip = rtu.update_open_closing_tags(value, "<b>", "</b>", "<strong>", "</strong>")
    with_strip = rtu.update_open_closing_tags(value, "<b>", "</b>", "<strong>", "</strong>", strip_br_tags=True)

    assert without_strip == "<strong>keep<br /></strong>"
    assert with_strip == "<strong>keep</strong>"


# --- convert_to_cke_html: format dispatch ------------------------------------
def test_convert_blank_and_non_string_returned_unchanged():
    assert rtu.convert_to_cke_html("", rtu.FORMAT_PLAIN) == ""
    assert rtu.convert_to_cke_html("   ", rtu.FORMAT_MARKDOWN) == "   "
    assert rtu.convert_to_cke_html(None, rtu.FORMAT_PLAIN) is None


def test_convert_unknown_format_returns_input_unchanged():
    assert rtu.convert_to_cke_html("keep me", "not-a-format") == "keep me"


def test_convert_html_is_identity():
    assert rtu.convert_to_cke_html("<p>already html</p>", rtu.FORMAT_HTML) == "<p>already html</p>"


def test_convert_plain_wraps_paragraphs_and_line_breaks():
    result = rtu.convert_to_cke_html("line1\nline2\n\npara2", rtu.FORMAT_PLAIN)

    assert result == "<p>line1<br>line2</p><p>para2</p>"


def test_convert_plain_preserves_embedded_html_tags():
    # a plain-text field that already contains an <img> tag must not be mangled
    result = rtu.convert_to_cke_html('before\n<img src="x.png">\nafter', rtu.FORMAT_PLAIN)

    assert '<img src="x.png">' in result


def test_convert_markdown_basic_and_code_block_verbatim():
    if rtu.markdown is None:
        pytest.skip("markdown is not installed")

    text = "**bold**\n\n```\n<b>literal</b>\n*not italic*\n```"
    result = rtu.convert_to_cke_html(text, rtu.FORMAT_MARKDOWN)

    assert "<strong>bold</strong>" in result
    # inside a fenced code block the tag is escaped and markdown syntax stays literal
    assert "&lt;b&gt;literal&lt;/b&gt;" in result
    assert "*not italic*" in result


def test_convert_textile_basic_markup():
    if rtu.textile is None:
        pytest.skip("textile is not installed")

    result = rtu.convert_to_cke_html("*bold*", rtu.FORMAT_TEXTILE)

    assert "<strong>bold</strong>" in result


# --- sanitize_cke_html: individual rules -------------------------------------
def test_sanitize_blank_and_non_string_returned_unchanged():
    assert rtu.sanitize_cke_html("") == ""
    assert rtu.sanitize_cke_html(None) is None


def test_sanitize_keeps_known_tags_and_escapes_unknown_tags():
    result = rtu.sanitize_cke_html("<p><b>keep</b> <option1|option2> <dradis.placeholder></p>")

    assert "<p>" in result and "<b>keep</b>" in result
    assert "&lt;option1|option2&gt;" in result
    assert "&lt;dradis.placeholder&gt;" in result
    assert "<option1" not in result
    assert "<dradis" not in result


def test_sanitize_preserves_real_p_tag():
    # regression for the flipped behavior: <p> is a real tag, not escaped text
    assert rtu.sanitize_cke_html("<p>hi</p>") == "<p>hi</p>"


def test_sanitize_escapes_lone_angle_brackets_as_text():
    assert rtu.sanitize_cke_html("<p>a &lt; b and c > d</p>") == "<p>a &lt; b and c &gt; d</p>"


def test_sanitize_drops_hr():
    result = rtu.sanitize_cke_html("<p>a</p><hr><p>b</p>")

    assert "<hr" not in result
    assert result == "<p>a</p><p>b</p>"


def test_sanitize_self_closes_void_elements():
    assert rtu.sanitize_cke_html('<p>x<br></p>') == "<p>x<br /></p>"
    assert '<img src="x.png" />' in rtu.sanitize_cke_html('<p><img src="x.png"></p>')


def test_sanitize_wraps_tables_in_figure_table_tbody():
    result = rtu.sanitize_cke_html("<table><tr><td>a</td></tr></table>")

    assert result == '<figure class="table"><table><tbody><tr><td>a</td></tr></tbody></table></figure>'


def test_sanitize_does_not_double_wrap_existing_figure_table():
    already = '<figure class="table"><table><tr><td>a</td></tr></table></figure>'
    result = rtu.sanitize_cke_html(already)

    assert result.count('<figure class="table">') == 1
    assert "<tbody>" in result


def test_sanitize_straightens_literal_smart_quotes():
    # U+201C/D double, U+2018/19 single
    assert rtu.sanitize_cke_html("<p>“hi” and ‘yo’</p>") == "<p>\"hi\" and 'yo'</p>"


def test_sanitize_straightens_smart_quote_numeric_and_named_refs():
    # decimal, hex, and named forms all collapse to straight ASCII quotes
    decimal = rtu.sanitize_cke_html("<p>&#8220;a&#8221; &#8216;b&#8217;</p>")
    assert decimal == "<p>\"a\" 'b'</p>"

    hexed = rtu.sanitize_cke_html("<p>&#x201C;a&#x201D; &#x2018;b&#x2019;</p>")
    assert hexed == "<p>\"a\" 'b'</p>"

    named = rtu.sanitize_cke_html("<p>&ldquo;a&rdquo; &lsquo;b&rsquo;</p>")
    assert named == "<p>\"a\" 'b'</p>"


def test_sanitize_straightens_cp1252_control_range_smart_quotes():
    # dec 145-148 / hex 0x91-0x94 and the literal mis-decoded chars
    assert rtu.sanitize_cke_html("<p>&#147;a&#148; &#145;b&#146;</p>") == "<p>\"a\" 'b'</p>"
    assert rtu.sanitize_cke_html("<p>a b</p>") == "<p>\"a\" 'b'</p>"


def test_sanitize_leaves_non_quote_entities_untouched():
    result = rtu.sanitize_cke_html("<p>a &amp; b &#160;c &lt;d&gt;</p>")

    assert "&amp;" in result
    assert "&#160;" in result
    assert "&lt;d&gt;" in result


def test_sanitize_preserves_smart_quotes_inside_code_blocks():
    value = "<pre><code>text = “literal” + &#8220;ref&#8221;</code></pre>"
    result = rtu.sanitize_cke_html(value)

    # code content is verbatim: curly chars and refs are NOT straightened
    assert "“literal”" in result
    assert "&#8220;ref&#8221;" in result


def test_process_textile_straightens_smart_quotes_end_to_end():
    if rtu.textile is None:
        pytest.skip("textile is not installed")

    result = rtu.process_rich_text('He said "hello" to me', rtu.FORMAT_TEXTILE)

    assert '"hello"' in result
    assert "&#8220;" not in result and "&#8221;" not in result
    assert "“" not in result and "”" not in result


def test_sanitize_preserves_pre_block_verbatim():
    value = "before\n\n\n<pre><code>line1\n\n\nline2  <b>real</b> &lt;kept&gt;</code></pre>\n\n\nafter"
    result = rtu.sanitize_cke_html(value)

    # whitespace, inner tags, and entities inside <pre> are untouched
    assert "<pre><code>line1\n\n\nline2  <b>real</b> &lt;kept&gt;</code></pre>" in result


# --- process_rich_text: convert + sanitize end to end ------------------------
def test_process_plain_with_embedded_image_survives_and_is_sanitized():
    result = rtu.process_rich_text('step one\n<img src="shot.png">\nstep two', rtu.FORMAT_PLAIN)

    assert "<p>" in result
    assert '<img src="shot.png" />' in result  # embedded image preserved and self-closed


def test_process_markdown_code_block_survives_end_to_end():
    if rtu.markdown is None:
        pytest.skip("markdown is not installed")

    result = rtu.process_rich_text("intro\n\n```\n<script>x</script>\nkeep  spaces\n```", rtu.FORMAT_MARKDOWN)

    assert "<pre>" in result
    # code content is escaped text, never a live tag, and its spacing is intact
    assert "&lt;script&gt;x&lt;/script&gt;" in result
    assert "<script>" not in result
    assert "keep  spaces" in result


def test_process_textile_preserves_real_tags_but_escapes_pseudo_tags():
    if rtu.textile is None:
        pytest.skip("textile is not installed")

    pseudo = rtu.process_rich_text("Contains <dradis.placeholder> token", rtu.FORMAT_TEXTILE)
    assert "&lt;dradis.placeholder&gt;" in pseudo
    assert "<dradis.placeholder>" not in pseudo

    real = rtu.process_rich_text("has <b>bold</b> inline", rtu.FORMAT_TEXTILE)
    assert "<b>bold</b>" in real
