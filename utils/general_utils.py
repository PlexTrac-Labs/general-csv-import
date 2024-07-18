import re
import time
from hashlib import sha256
from typing import List
from copy import copy, deepcopy
import os

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
    return re.sub('[\W]', '', re.sub('[ -]', '_', new_str))


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
    accepted_data_formats = ['%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y', '%Y/%m/%d', '%Y-%m-%d', '%m/%d/%Y %I:%M:%S %p']
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
        if value < 1:
            raise ValueError
    except ValueError as e:
        return False
    return True


def is_valid_ipv4_address(address: str) -> bool:
    """
    Checks if a string has the correct IPv4 format.

    :param address: ipv4 string to check
    :type address: str
    :return: boolean result of validation
    :rtype: bool
    """
    ipv4_pattern = re.compile(r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$')
    return ipv4_pattern.match(address) is not None


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
    

def is_valid_cvss3_1_vector(cvss_vector: str) -> bool:
    """
    Checks if a string has the correct CVSS3.1 calculation/vector format. Calculations are checked against the format `AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:H/A:L`

    :param cvss_vector: cvss vector string to check
    :type cvss_vector: str
    :return: boolean result of validation
    :rtype: bool
    """
    pattern = re.compile(r"^((AV:[NALP]|AC:[LH]|PR:[NLH]|UI:[NR]|S:[UC]|[CIA]:[NLH]|E:[XUPFH]|RL:[XOTWU]|RC:[XURC]|[CIA]R:[XLMH]|MAV:[XNALP]|MAC:[XLH]|MPR:[XNLH]|MUI:[XNR]|MS:[XUC]|M[CIA]:[XNLH])/)*(AV:[NALP]|AC:[LH]|PR:[NLH]|UI:[NR]|S:[UC]|[CIA]:[NLH]|E:[XUPFH]|RL:[XOTWU]|RC:[XURC]|[CIA]R:[XLMH]|MAV:[XNALP]|MAC:[XLH]|MPR:[XNLH]|MUI:[XNR]|MS:[XUC]|M[CIA]:[XNLH])$") 
    return pattern.match(cvss_vector) is not None


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
