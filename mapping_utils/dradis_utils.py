"""Reusable Dradis CSV/ZIP/XML helpers.

Dradis project exports are delivered as a CSV plus a same-basename ZIP file.
The ZIP contains ``dradis-repository.xml`` (project nodes, issues, content
blocks, and report properties) along with the attachment images referenced in
rich text. This module centralizes the generic loading and normalization of
that data so individual ``dradis_*`` mapping types can focus on field choices
rather than on parsing.

None of the logic here is customer specific. Mapping-specific field selection
belongs in the mapping module, not here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote
import csv
import glob
import json
import os
import re
import zipfile

import xmltodict

import utils.log_handler as logger
log = logger.log


DRADIS_REPOSITORY_XML_NAME = "dradis-repository.xml"

# Node labels that are administrative containers in Dradis rather than real
# assets/targets. They should be ignored when looking for a useful asset label.
NON_ASSET_NODE_LABELS = {
    "report content",
    "uploaded files",
    "legacytable",
    "deleted files",
    "threatmodel",
}


@dataclass
class LoadedDradisData:
    """Container for a loaded Dradis CSV + ZIP/XML pair."""
    file_path: str
    zip_file_path: str
    csv_rows: List[List[str]] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    row_dicts: List[Dict[str, str]] = field(default_factory=list)
    xml: Dict[str, Any] = field(default_factory=dict)
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    content_blocks: List[Dict[str, Any]] = field(default_factory=list)
    report_properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DradisImageReference:
    """A single Dradis image marker found inside a rich text value."""
    raw_tag: str
    normalized_tag: str
    start_index: int
    end_index: int
    project_id: str
    node_id: str
    file_name: str
    display_metadata: Dict[str, str] = field(default_factory=dict)
    caption: str = ""


# region file discovery -------------------------------------------------------
def find_paired_zip(csv_file_path: str) -> str:
    """Return the same-basename ``.zip`` path for a Dradis CSV file."""
    base, _ = os.path.splitext(csv_file_path)
    return f"{base}.zip"


def find_dradis_csv_candidates(folder_path: str) -> List[str]:
    """Return sorted CSV files in a folder that have a same-basename ZIP pair."""
    candidates = []
    for csv_path in sorted(glob.glob(os.path.join(folder_path, "*.csv"))):
        if os.path.exists(find_paired_zip(csv_path)):
            candidates.append(csv_path)
        else:
            log.warning(f"Skipping '{csv_path}' - no same-basename ZIP file found beside it.")
    return candidates
# endregion ---


# region low level loading ----------------------------------------------------
def load_csv_rows(csv_file_path: str) -> Tuple[List[List[str]], List[str], List[Dict[str, str]]]:
    """Read a UTF-8-sig CSV into raw rows, headers, and per-row dictionaries.

    :return: ``(csv_rows, headers, row_dicts)`` where ``csv_rows`` includes the
        header row, ``headers`` is the first row, and ``row_dicts`` is a list of
        ``{header: value}`` dictionaries for each data row.
    """
    with open(csv_file_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.reader(file)
        csv_rows = [row for row in reader]

    if not csv_rows:
        return [], [], []

    headers = csv_rows[0]
    row_dicts = []
    for row in csv_rows[1:]:
        # pad short rows so every header has a value
        padded = list(row) + ["" for _ in range(len(headers) - len(row))]
        row_dicts.append({header: padded[index] for index, header in enumerate(headers)})

    return csv_rows, headers, row_dicts


def load_xml_from_zip(zip_file_path: str) -> Dict[str, Any]:
    """Read ``dradis-repository.xml`` from a ZIP and parse it with ``xmltodict``."""
    if not os.path.exists(zip_file_path):
        raise FileNotFoundError(f"Paired Dradis ZIP file does not exist: '{zip_file_path}'")

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        member_name = None
        for name in zip_ref.namelist():
            if name == DRADIS_REPOSITORY_XML_NAME or name.endswith(f"/{DRADIS_REPOSITORY_XML_NAME}"):
                member_name = name
                break
        if member_name is None:
            raise FileNotFoundError(
                f"Could not find '{DRADIS_REPOSITORY_XML_NAME}' inside ZIP '{zip_file_path}'"
            )
        xml_bytes = zip_ref.read(member_name)

    return xmltodict.parse(xml_bytes) or {}


def load_dradis_pair(csv_file_path: str) -> LoadedDradisData:
    """Load a Dradis CSV plus its paired ZIP/XML into a ``LoadedDradisData``."""
    zip_file_path = find_paired_zip(csv_file_path)
    if not os.path.exists(zip_file_path):
        raise FileNotFoundError(
            f"No paired Dradis ZIP file found for '{csv_file_path}'. Expected '{zip_file_path}'."
        )

    csv_rows, headers, row_dicts = load_csv_rows(csv_file_path)
    xml = load_xml_from_zip(zip_file_path)
    root = _xml_root(xml)

    nodes = normalize_nodes(root)
    issues = normalize_issues(root)
    content_blocks = normalize_content_blocks(root)
    report_properties = _extract_report_properties(root, nodes)

    return LoadedDradisData(
        file_path=csv_file_path,
        zip_file_path=zip_file_path,
        csv_rows=csv_rows,
        headers=headers,
        row_dicts=row_dicts,
        xml=xml,
        nodes=nodes,
        issues=issues,
        content_blocks=content_blocks,
        report_properties=report_properties,
    )
# endregion ---


# region xml normalization ----------------------------------------------------
def ensure_list(value: Any) -> List[Any]:
    """Normalize an absent/single/list XML value into a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _xml_root(xml: Dict[str, Any]) -> Dict[str, Any]:
    """Return the inner content of a single-root xmltodict document."""
    if not isinstance(xml, dict):
        return {}
    if len(xml) == 1:
        inner = next(iter(xml.values()))
        return inner if isinstance(inner, dict) else {}
    return xml


def _key_variants(key: str) -> List[str]:
    return [key, key.replace("_", "-"), key.replace("-", "_")]


def _first_present(container: Any, candidate_keys: List[str]) -> Any:
    if not isinstance(container, dict):
        return None
    for key in candidate_keys:
        for variant in _key_variants(key):
            if variant in container:
                return container[variant]
    return None


def _get_collection(root: Dict[str, Any], container_keys: List[str], item_keys: List[str]) -> List[Any]:
    container = _first_present(root, container_keys)
    if container is None:
        return []
    if isinstance(container, list):
        return container
    if isinstance(container, dict):
        return ensure_list(_first_present(container, item_keys))
    return []


def _text(value: Any) -> str:
    """Coerce an xmltodict value (str / dict with #text / None) to a string."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("#text", "")) if "#text" in value else ""
    return str(value)


def normalize_section_key(key: str) -> str:
    """Strip/lowercase a Dradis section key and convert spaces to underscores."""
    return key.strip().lower().replace(" ", "_")


def parse_properties_json(properties: Any) -> Dict[str, Any]:
    """Parse a node ``properties`` JSON blob into a dict.

    Returns ``{}`` for blanks, non-strings, or invalid JSON.
    """
    if isinstance(properties, dict):
        return properties
    text = _text(properties).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_dradis_sections(text: Any) -> Dict[str, str]:
    """Parse Dradis ``#[Section Name]#`` blocks into normalized-key/value pairs.

    Example input::

        #[Title]#
        SQL Injection

        #[Rating]#
        High

    becomes ``{"title": "SQL Injection", "rating": "High"}``.
    """
    text = _text(text)
    if not text:
        return {}

    sections: Dict[str, str] = {}
    current_key: Optional[str] = None
    buffer: List[str] = []
    header_pattern = re.compile(r"^\s*#\[(?P<name>.+?)\]#\s*$")

    def _flush():
        if current_key is not None:
            sections[current_key] = "\n".join(buffer).strip()

    for line in text.splitlines():
        match = header_pattern.match(line)
        if match:
            _flush()
            current_key = normalize_section_key(match.group("name"))
            buffer = []
        elif current_key is not None:
            buffer.append(line)
    _flush()

    return sections


def normalize_nodes(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize ``<nodes>`` into dicts with parsed ``properties``."""
    normalized = []
    for raw in _get_collection(root, ["nodes"], ["node"]):
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "id": _text(_first_present(raw, ["id"])),
            "label": _text(_first_present(raw, ["label"])),
            "type_id": _text(_first_present(raw, ["type_id"])),
            "parent_id": _text(_first_present(raw, ["parent_id"])),
            "properties": parse_properties_json(_first_present(raw, ["properties"])),
            "raw": raw,
        })
    return normalized


def normalize_issues(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize ``<issues>`` into dicts with parsed ``sections``."""
    normalized = []
    for raw in _get_collection(root, ["issues"], ["issue"]):
        if not isinstance(raw, dict):
            continue
        text = _text(_first_present(raw, ["text"]))
        sections = parse_dradis_sections(text)
        title = sections.get("title", "") or _text(_first_present(raw, ["title"]))
        normalized.append({
            "id": _text(_first_present(raw, ["id"])),
            "title": title.strip(),
            "text": text,
            "sections": sections,
            "raw": raw,
        })
    return normalized


def normalize_content_blocks(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize ``<content-blocks>`` into dicts with parsed ``sections``."""
    normalized = []
    for raw in _get_collection(root, ["content_blocks"], ["content_block"]):
        if not isinstance(raw, dict):
            continue
        content = _text(_first_present(raw, ["content"]))
        sections = parse_dradis_sections(content)
        normalized.append({
            "id": _text(_first_present(raw, ["id"])),
            "group": _text(_first_present(raw, ["block_group", "group"])),
            "content": content,
            "title": sections.get("title", "").strip(),
            "sections": sections,
            "raw": raw,
        })
    return normalized


def _extract_report_properties(root: Dict[str, Any], nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a flat report-properties dict from root and report-content nodes."""
    properties: Dict[str, Any] = {}

    root_properties = _first_present(root, ["report_properties", "properties"])
    properties.update(parse_properties_json(root_properties))

    for node in nodes:
        if node["label"].strip().lower() in {"report content", "report"}:
            properties.update(node["properties"])

    return properties
# endregion ---


# region value helpers --------------------------------------------------------
def first_value(*values: Any) -> str:
    """Return the first non-blank value (stripped) from the arguments."""
    for value in values:
        if value is None:
            continue
        text = value if isinstance(value, str) else str(value)
        if text.strip():
            return text
    return ""


def get_csv_value(row: Dict[str, Any], keys: List[str], default: str = "") -> str:
    """Read the first non-blank value from a list of possible CSV headers."""
    if not isinstance(row, dict):
        return default
    for key in keys:
        value = row.get(key, "")
        if value is not None and str(value).strip():
            return value
    return default


def get_property(properties: Dict[str, Any], keys: List[str], default: str = "") -> str:
    """Read the first non-blank value from a list of possible XML property keys."""
    if not isinstance(properties, dict):
        return default
    for key in keys:
        value = properties.get(key, "")
        if value is not None and str(value).strip():
            return value
    return default
# endregion ---


# region issue matching -------------------------------------------------------
ISSUE_TITLE_HEADERS = ["Title", "Finding Name", "Vulnerability Name"]


def find_issue_for_row(row: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Match a CSV row to an XML issue by title-like fields."""
    row_title = get_csv_value(row, ISSUE_TITLE_HEADERS).strip().lower()
    if not row_title:
        return {}
    for issue in issues:
        if issue.get("title", "").strip().lower() == row_title:
            return issue
    return {}


def get_single_dradis_issue(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the only issue if exactly one exists, otherwise ``{}``.

    Useful for one-finding exports where title matching is unreliable.
    """
    if isinstance(issues, list) and len(issues) == 1:
        return issues[0]
    return {}
# endregion ---


# region content block narratives ---------------------------------------------
def find_content_blocks_by_group(content_blocks: List[Dict[str, Any]], group: str) -> List[Dict[str, Any]]:
    """Return content blocks whose group matches ``group`` (case-insensitive)."""
    target = normalize_section_key(group)
    return [cb for cb in content_blocks if normalize_section_key(cb.get("group", "")) == target]


def content_block_text(content_blocks: List[Dict[str, Any]], groups) -> str:
    """Join the content of all blocks belonging to the requested group(s)."""
    if isinstance(groups, str):
        groups = [groups]
    parts = []
    for group in groups:
        for block in find_content_blocks_by_group(content_blocks, group):
            text = first_value(block.get("sections", {}).get("description", ""), block.get("content", ""))
            if text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts)


def _content_block_body(block: Dict[str, Any]) -> str:
    sections = block.get("sections", {})
    # prefer named body sections, fall back to the raw content
    return first_value(sections.get("description", ""), sections.get("content", ""), block.get("content", ""))


def get_dradis_appendix_narratives(content_blocks: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Create dynamic ``Appendix: <Title>`` narrative entries."""
    narratives = []
    for index, block in enumerate(find_content_blocks_by_group(content_blocks, "Appendix"), start=1):
        title = first_value(block.get("title", ""), f"Appendix {index}")
        narratives.append((f"Appendix: {title}", _content_block_body(block)))
    return narratives


def format_executive_summary_subtype(subtype: str) -> str:
    """Format an executive summary subtype into a human-readable label."""
    return " ".join(word.capitalize() for word in re.split(r"[\s_]+", str(subtype).strip()) if word)


def is_subtyped_executive_summary_block(block: Dict[str, Any]) -> bool:
    """Whether a content block is a subtyped executive summary block."""
    if normalize_section_key(block.get("group", "")) != "executive_summary":
        return False
    sections = block.get("sections", {})
    return bool(first_value(sections.get("subtype", ""), sections.get("type", "")))


def get_dradis_executive_summary_narratives(content_blocks: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Create ``Executive Summary: <Subtype>`` entries for subtyped blocks."""
    narratives = []
    for block in find_content_blocks_by_group(content_blocks, "Executive Summary"):
        if not is_subtyped_executive_summary_block(block):
            continue
        sections = block.get("sections", {})
        subtype = format_executive_summary_subtype(first_value(sections.get("subtype", ""), sections.get("type", "")))
        narratives.append((f"Executive Summary: {subtype}", _content_block_body(block)))
    return narratives


def get_dradis_observation_narratives(content_blocks: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """Create dynamic ``Observation: <Title>`` narrative entries."""
    narratives = []
    for index, block in enumerate(find_content_blocks_by_group(content_blocks, "Observation"), start=1):
        title = first_value(block.get("title", ""), f"Observation {index}")
        narratives.append((f"Observation: {title}", _content_block_body(block)))
    return narratives


def get_dradis_target_node_label(nodes: List[Dict[str, Any]]) -> str:
    """Return the first useful non-administrative node label."""
    for node in nodes:
        label = node.get("label", "").strip()
        if label and label.lower() not in NON_ASSET_NODE_LABELS:
            return label
    return ""
# endregion ---


# region severity / status normalization --------------------------------------
def normalize_dradis_severity(severity: str) -> str:
    """Map a Dradis severity into a PlexTrac severity."""
    mapping = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "moderate": "Medium",
        "low": "Low",
        "info": "Informational",
        "informational": "Informational",
        "none": "Informational",
    }
    return mapping.get(str(severity).strip().lower(), "Informational")


def normalize_dradis_status(status: str) -> str:
    """Map a Dradis status into a PlexTrac status."""
    mapping = {
        "new": "Open",
        "draft": "Open",
        "ready_for_review": "Open",
        "ready for review": "Open",
        "open": "Open",
        "in progress": "In Process",
        "in process": "In Process",
        "closed": "Closed",
        "resolved": "Closed",
        "done": "Closed",
    }
    return mapping.get(str(status).strip().lower(), "Open")
# endregion ---


# region image reference parsing ----------------------------------------------
_IMAGE_MARKER = re.compile(
    r"!"
    r"(?P<meta>(?:\{[^}]*\})*)"
    r"(?P<path>/(?:pro/)?projects/(?P<pid>\d+)/nodes/(?P<nid>\d+)/attachments/(?P<file>[^!(*]+))"
    r"(?:\*\*)?"
    r"(?:\((?P<caption>[^)]*)\))?"
    r"(?:\*\*)?"
    r"!"
)


def parse_image_meta_tags(meta_blocks: str) -> Dict[str, str]:
    """Parse repeated ``{key:value}`` Dradis image display metadata blocks."""
    metadata: Dict[str, str] = {}
    for block in re.findall(r"\{([^}]*)\}", meta_blocks or ""):
        if ":" in block:
            key, value = block.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def split_image_path_and_caption(path_with_caption: str) -> Tuple[str, str]:
    """Split a ``path(caption)`` Dradis image fragment into ``(path, caption)``."""
    match = re.match(r"^(?P<path>[^(]+?)(?:\*\*)?(?:\((?P<caption>[^)]*)\))?(?:\*\*)?$", path_with_caption.strip())
    if not match:
        return path_with_caption.strip(), ""
    return match.group("path").strip(), (match.group("caption") or "").strip()


def find_dradis_image_reference(value: str) -> Optional[DradisImageReference]:
    """Find the next Dradis image marker in a string, or ``None`` if absent."""
    if not isinstance(value, str):
        return None
    match = _IMAGE_MARKER.search(value)
    if match is None:
        return None

    encoded_path = match.group("path")
    file_name = unquote(match.group("file"))
    normalized_path = encoded_path[: encoded_path.rindex("/") + 1] + file_name

    return DradisImageReference(
        raw_tag=match.group(0),
        normalized_tag=f"!{normalized_path}!",
        start_index=match.start(),
        end_index=match.end(),
        project_id=match.group("pid"),
        node_id=match.group("nid"),
        file_name=file_name,
        display_metadata=parse_image_meta_tags(match.group("meta")),
        caption=(match.group("caption") or "").strip(),
    )
# endregion ---
