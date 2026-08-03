import re
import time
import json
from hashlib import sha256
from typing import List, Optional
from copy import copy, deepcopy
import os

from cvss import CVSS3, CVSS4, CVSSError

import utils.log_handler as logger
log = logger.log


def format_key(string: str) -> str:
    """
    PT keys and tags should be lowercase alphanumeric strings, including (a-z), (0-9), and underscores (_)
    String is cleaned by:
     - lowercasing string
     - replacing spaces ( ) and dashes (-) with underscores
     - striping non alphanumeric characters

    :param str: string to be cleaned
    :type str: str
    :return: cleaned alphanumeric string
    :rtype: str
    """
    new_str = string.strip().lower()
    return re.sub(r'[\W]', '', re.sub(r'[ -]', '_', new_str))


def add_tag(list: List[str], tag: str) -> None:
    """
    Adds a tag to a list if the tag is not already in the list

    :param list: list to add tag to
    :type list: List[str]
    :param tag: tag to add to list
    :type tag: str
    """
    new_tag = format_key(tag)
    if new_tag not in list:
        list.append(new_tag)


def merge_sanitized_str_lists(list1: List[str], list2: List[str]) -> None:
    """
    Appends the new values from a second list into the first list

    :param list1: List that should be appended to
    :type list1: List[str]
    :param list2: List of values to append if they don't already exist
    :type list2: List[str]
    """
    resulting_list = list1
    resulting_list.extend(x for x in list2 if x not in resulting_list)


def try_parsing_date(possible_date_str: str) -> time.struct_time:
    """
    Try to parse a date string into Python time module's struct_time using several formats.
    Useful if the format is unknown

    :param possible_date_str: date string to parse
    :type possible_date_str: str
    :return: parsed date string
    :rtype: time.struct_time
    """
    error = None
    accepted_data_formats = ['%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y', '%Y/%m/%d', '%Y-%m-%d', '%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y %H:%M', '%B %d, %Y', '%b %d, %Y']
    for fmt in accepted_data_formats:
        try:
            return time.strptime(possible_date_str, fmt)
        except ValueError as e:
            error = e
    raise ValueError(f'Could not parse date from list of accepted formats: {accepted_data_formats}') from error


def is_int(value: str) -> bool:
    """
    Checks if a string contains a value that can be parsed to an int

    :param value: string to check
    :type value: str
    :return: boolean result of validation
    :rtype: bool
    """
    try:
        int(value)
        return True
    except ValueError:
        return False


def is_str_positive_integer(value: str) -> bool:
    """
    Checks if a string contains a value that can be parsed to a positive int 1,2,3,...

    :param value: string to check
    :type value: str
    :raises ValueError: value was not a positive integer
    :return: boolean result of validation
    :rtype: bool
    """
    try:
        value = int(value)
        if value < 0:
            raise ValueError
    except ValueError as e:
        return False
    return True


def is_valid_ipv4_address(address: str) -> bool:
    """
    Checks if a string has the correct IPv4 format by splitting and validating parts.

    :param address: IPv4 string to check
    :type address: str
    :return: boolean result of validation
    :rtype: bool
    """
    parts = address.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255:
            return False
        # Leading zeros are invalid (e.g., "01")
        if len(part) > 1 and part[0] == "0":
            return False
    return True


def is_valid_ipv6_address(address: str) -> bool:
    """
    Checks if a string has the correct IPv6 format.

    :param address: ipv6 string to check
    :type address: str
    :return: boolean result of validation
    :rtype: bool
    """
    ipv6_pattern = re.compile(r'^(([0-9a-fA-F]{1,4}):){7}([0-9a-fA-F]{1,4})$')
    return ipv6_pattern.match(address) is not None


def is_valid_cve(cve: str) -> bool:
    """
    Checks if a string has the correct CVE format. CVEs are formatted as `CVE-2023-1234`

    :param cve: cve string to check
    :type cve: str
    :return: boolean result of validation
    :rtype: bool
    """
    cve_pattern = re.compile(r'CVE-[0-9]{4}-[0-9]')
    return cve_pattern.match(cve) is not None


def is_valid_cwe(cwe: str, has_prefix: bool = True) -> bool:
    """
    Checks if a string has the correct CWE format. CWEs are formatted as `CWE-1234` or `1234`

    Use the `has_prefix` parameter to choose which of these 2 CWE formats you want to validate against.
    By default `has_prefix` is True and the validation check is based on if the `cwe` matches the `CWE-1234` format.
    Setting `has_prefix` to False validates against the `1234` format.

    :param cwe: cwe string to check
    :type cwe: str
    :param has_prefix: changes the validation check based on whether the `cwe` param should contain the "CWE-" prefix, defaults to True
    :type has_prefix: bool, optional
    :return: boolean result of validation
    :rtype: bool
    """
    if has_prefix:
        cwe_pattern = re.compile(r'CWE-[0-9]')
        return cwe_pattern.match(cwe) is not None
    else:
        cwe_num = re.compile(r'[0-9]')
        return cwe_num.match(cwe) is not None


# ---- CVSS version detection and prefix normalisation ------------------------

def detect_cvss_version(vector: str) -> Optional[str]:
    """Return the CVSS version declared in the vector prefix.

    Matching is case-insensitive so ``cvss:3.1/...`` is recognised the same as
    ``CVSS:3.1/...``.  Returns ``"4.0"``, ``"3.1"``, ``"3.0"``, or ``None``
    when no recognised ``CVSS:x.y/`` prefix is present.
    """
    upper = vector.strip().upper()
    if upper.startswith("CVSS:4.0/"):
        return "4.0"
    if upper.startswith("CVSS:3.1/"):
        return "3.1"
    if upper.startswith("CVSS:3.0/"):
        return "3.0"
    return None


def normalize_cvss_vector(vector: str) -> str:
    """Uppercase the ``CVSS:x.y/`` prefix if present; leave the body as-is.

    Handles lowercase or mixed-case prefixes produced by some tools, e.g.
    ``cvss:3.1/AV:N/...`` → ``CVSS:3.1/AV:N/...``.
    Bare metric strings without a prefix are returned unchanged.
    """
    stripped = vector.strip()
    match = re.match(r'^(cvss:\d+\.\d+/)', stripped, flags=re.IGNORECASE)
    if match:
        return match.group(1).upper() + stripped[match.end():]
    return stripped


# ---- Validation (backed by the ``cvss`` package) ----------------------------

def is_valid_cvss3_vector(cvss_vector: str) -> bool:
    """Return True when *cvss_vector* is a valid CVSS 3.0 metric body.

    Accepts both bare metric strings and full ``CVSS:3.0/...`` prefixed strings.
    Validation is delegated to the ``cvss`` library.
    Example valid input: ``AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H``
    """
    body = re.sub(r'^CVSS:3\.0/', '', cvss_vector.strip(), flags=re.IGNORECASE)
    try:
        CVSS3("CVSS:3.0/" + body)
        return True
    except CVSSError:
        return False


def is_valid_cvss3_1_vector(cvss_vector: str) -> bool:
    """Return True when *cvss_vector* is a valid CVSS 3.1 metric body.

    Accepts both bare metric strings and full ``CVSS:3.1/...`` prefixed strings.
    Validation is delegated to the ``cvss`` library.
    Example valid input: ``AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H``
    """
    body = re.sub(r'^CVSS:3\.1/', '', cvss_vector.strip(), flags=re.IGNORECASE)
    try:
        CVSS3("CVSS:3.1/" + body)
        return True
    except CVSSError:
        return False


def is_valid_cvss4_vector(cvss_vector: str) -> bool:
    """Return True when *cvss_vector* is a valid CVSS 4.0 vector.

    Accepts both bare body strings and full ``CVSS:4.0/...`` prefixed strings.
    Validation is delegated to the ``cvss`` library.  Note: the ICS/OT Safety
    Impact extension (``SI:S`` / ``SA:S``) is not supported by the library and
    will be rejected.
    """
    body = re.sub(r'^CVSS:4\.0/', '', cvss_vector.strip(), flags=re.IGNORECASE)
    try:
        CVSS4("CVSS:4.0/" + body)
        return True
    except CVSSError:
        return False


def is_valid_cvss_vector(vector: str) -> bool:
    """Return True when *vector* is a valid CVSS 3.0, 3.1, or 4.0 vector.

    Normalises the prefix before checking so lowercase prefixes like
    ``cvss:3.1/...`` are accepted, then routes to the version-specific
    validator.  Bare metric strings with no prefix are validated as CVSS 3.1.
    """
    v = normalize_cvss_vector(vector)
    version = detect_cvss_version(v)
    if version == "4.0":
        return is_valid_cvss4_vector(v)
    if version == "3.0":
        return is_valid_cvss3_vector(v)
    if version == "3.1":
        return is_valid_cvss3_1_vector(v)
    return is_valid_cvss3_1_vector(v)  # bare string: validate as CVSS 3.1


# ---- Score calculation (backed by the ``cvss`` package) ---------------------

def calculate_cvss3_base_score(vector: str) -> float:
    """Compute the CVSS 3.0 or 3.1 base score from a vector string.

    Accepts both prefixed (``CVSS:3.x/...``) and bare metric strings.
    Normalises a lowercase prefix before scoring.
    Raises :class:`ValueError` for invalid or unrecognised vectors.
    """
    v = normalize_cvss_vector(vector)
    version = detect_cvss_version(v)
    if version is None:
        v = "CVSS:3.1/" + v  # bare string: assume 3.x
    try:
        return float(CVSS3(v).base_score)
    except CVSSError as exc:
        raise ValueError(f"Invalid CVSS 3.x vector '{vector}': {exc}") from exc


def calculate_cvss_base_score(vector: str) -> Optional[float]:
    """Return the CVSS base score computed from the vector string.

    Handles CVSS 3.0, 3.1, and 4.0 vectors (with or without prefix).
    Normalises a lowercase prefix before scoring.
    Returns ``None`` for unrecognised or invalid vectors.
    """
    v = normalize_cvss_vector(vector)
    version = detect_cvss_version(v)
    if version in ("3.0", "3.1"):
        try:
            return float(CVSS3(v).base_score)
        except CVSSError as exc:
            log.warning(f"CVSS 3.x score calculation failed for '{v}': {exc}")
            return None
    if version == "4.0":
        try:
            return float(CVSS4(v).base_score)
        except CVSSError as exc:
            log.warning(f"CVSS 4.0 score calculation failed for '{v}': {exc}")
            return None
    # Bare string (no prefix): try as 3.x
    try:
        return float(CVSS3("CVSS:3.1/" + v).base_score)
    except CVSSError:
        return None


def sanitize_file_name(name:str, allow_spaces: bool = False) -> str:
    """
    Windows OS has certain character that are not allowed in folder or file names. If a folder or file name is being
    generated from some data in the PT platform, like a client name, the client name could contains invalid characters.

    This function strips invalid characters.

    :param name: file name to sanitize
    :type name: str
    :return: sanitized file name
    :rtype: str
    """
    invalid_chars = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|"]
    
    new_name = name
    for char in invalid_chars:
        new_name = new_name.replace(char, "")

    if not allow_spaces:
        new_name.replace(" ", "_")
    return new_name


def generate_flaw_id(title: str) -> int:
    """
    In PT the flaw_id is generated based on a hash of the finding title. This finding_id is used for finding deduplication,
    in essence deduplicating based on the finding title.

    :param title: finding title
    :type title: str
    :return: flaw_id generated from the hash of the finding title the same as it would be generated in platform
    :rtype: int
    """
    return int(sha256(title.encode('utf-8')).hexdigest(), 16) % 10 ** 8


def increment_file_name(file_name, existing_files):
    """
    takes file name with extension
    
    return unique file name (possible appended number) without extension
    """
    base_name, extension = os.path.splitext(file_name)
    if base_name in existing_files:
        count = 1
        while f"{base_name} ({count})" in existing_files:
            count += 1
        return f"{base_name} ({count})"
    return base_name


def save_json_as_ptrac_file(ptrac_data: dict, file_name: str = "", folder_path: str = "exported_ptracs") -> None:
    """
    Save a PTRAC JSON dictionary to a .ptrac file.
    """
    if file_name:
        export_name = sanitize_file_name(file_name)
    else:
        client_name = sanitize_file_name(ptrac_data.get("client_info", {}).get("name", ""))
        report_name = sanitize_file_name(ptrac_data.get("report_info", {}).get("name", ""))
        timestamp = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime(time.time()))
        export_name = f'{client_name}_{report_name}_{timestamp}'

    try:
        os.mkdir(folder_path)
    except FileExistsError:
        pass

    existing_files = [os.path.splitext(file)[0] for file in os.listdir(folder_path)]
    export_file_name = increment_file_name(export_name, existing_files)

    file_path = f'{folder_path}/{export_file_name}.ptrac'
    with open(f'{file_path}', 'w') as file:
        json.dump(ptrac_data, file)
        log.info(f'Saved new PTRAC \'{export_file_name}.ptrac\'')
