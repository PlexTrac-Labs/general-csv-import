import json
import csv
import sys
from getpass import getpass
from typing import List, Optional
import utils.log_handler as logger
log = logger.log

prompt_prefix = "\n[Prompt] "
prompt_suffix = ": "

# Global variable to track interactive mode
_interactive_mode = True

def set_interactive_mode(interactive: bool):
    """
    Sets the interactive mode for input functions.
    
    :param interactive: The interactive mode from script arguments
    :type interactive: bool
    """
    global _interactive_mode
    _interactive_mode = bool(interactive)

def _check_interactive_mode(error_msg: str, override: Optional[bool] = None):
    """
    Checks if interactive mode is enabled. If not, logs critical error and exits.
    
    :param error_msg: Error message to display when not in interactive mode
    :type error_msg: str
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    """
    interactive_mode = override if override is not None else _interactive_mode
    if not interactive_mode:
        log.critical(error_msg)
        sys.exit(1)

# prompts user for data not needing validation
def prompt_user(msg, error_msg: Optional[str] = None, override: Optional[bool] = None):
    """
    Prompts user for input. If not in interactive mode, exits with error.
    
    :param msg: Message to display to user
    :type msg: str
    :param error_msg: Custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: User input
    :rtype: str
    """
    if error_msg is None:
        error_msg = "User input required but interactive mode is disabled"
    _check_interactive_mode(error_msg, override)
    
    log.debug(f"prompt_user: Prompting for user input: {msg}")
    user_input = input(prompt_prefix + msg + prompt_suffix)
    log.debug(f"prompt_user: User entered input: {user_input}")
    return user_input


def prompt_password(msg: str = "Password", error_msg: Optional[str] = None, override: Optional[bool] = None) -> str:
    """
    Prompts user for password input (hidden). If not in interactive mode, exits with error.
    
    :param msg: Message to display to user
    :type msg: str
    :param error_msg: Custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: User password input
    :rtype: str
    """
    if error_msg is None:
        error_msg = "Password is required but not provided"
    _check_interactive_mode(error_msg, override)
    
    log.debug(f"prompt_password: Prompting for user input: {msg}")
    user_input = getpass(prompt=prompt_prefix + msg + prompt_suffix)
    log.debug("prompt_password: User entered password (hidden)")
    return user_input


def user_options(msg: str, retry_msg: str ="", options: Optional[List[str]] = None, error_msg: Optional[str] = None, override: Optional[bool] = None) -> str:
    """
    Prompts a user for an input from a given list of options, and returns the valid choice.

    :param msg: message to display with the prompt
    :type msg: str
    :param retry_msg: message to display if user enters invalid input, defaults to ""
    :type retry_msg: str, optional
    :param options: list of valid options, defaults to []
    :type options: List[str], optional
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: the valid option chosen by the user
    :rtype: str
    """
    if options is None:
        options = []
    if error_msg is None:
        error_msg = "user_options: User selection required but interactive mode is disabled"
    _check_interactive_mode(error_msg, override)
    
    # setup
    str_options = "/".join(options)
    
    # get input
    log.debug(f"user_options: Prompting for user input with: {msg} (options: {options})")
    entered = input(prompt_prefix + msg + " (" + str_options + ")" + prompt_suffix)
    log.debug(f"user_options: User entered input: {entered}")
    
    #validate input
    if entered in options:
        return entered

    #ask again
    if retry(retry_msg, None, override):
        return user_options(msg, retry_msg, options, error_msg, override)


def user_list(msg: str, retry_msg: str = "", range: int = 0, error_msg: Optional[str] = None, override: Optional[bool] = None) -> int:
    """
    Prompts a user for an input from a given range, and returns the valid choice. Call this method after printing
    a list of options. This list should display incrementing numbers with each item, from 1 to number
    of options.

    ex.
    1 - first option
    2 - second option
    etc.

    The number return is the 1-based index. If looping through a list you will need to subtract one
    to reference the correct choice.

    :param msg: message to display with the prompt
    :type msg: str
    :param retry_msg: message to display if user enters invalid input, defaults to ""
    :type retry_msg: str, optional
    :param range: number of valid options, defaults to 0
    :type range: int, optional
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: the valid option chosen by the user
    :rtype: int
    """
    if error_msg is None:
        error_msg = "user_list: User selection required but interactive mode is disabled"
    _check_interactive_mode(error_msg, override)
    
    #setup
    str_options = f"1-{range}"
    
    # get input
    log.debug(f"user_list: Prompting for user input with: {msg} (range: 1-{range})")
    entered = input(prompt_prefix + msg + " (" + str_options + ")" + prompt_suffix)
    log.debug(f"user_list: User entered input: {entered}")
    
    #validate input
    if int(entered) > 0 and int(entered) <= range:
        return int(entered)

    #ask again
    if retry(retry_msg, None, override):
        return user_list(msg, retry_msg, range, error_msg, override)


def continue_check(msg: str, error_msg: Optional[str] = None, override: Optional[bool] = None) -> bool:
    """
    Prompts a user whether they want to continue, by adding the string " Continue? (y/n)"
    to the end of the `msg` passed in. This is similar to continue_anyways, but doesn't
    mean something bad might happen. This can be used for general checkpoints in a script.

    :param msg: message to display with the prompt
    :type msg: str
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: True if user types "y" else False
    :rtype: bool
    """
    if error_msg is None:
        error_msg = "continue_check: User confirmation required but interactive mode is disabled"
    _check_interactive_mode(error_msg, override)
    
    log.debug(f"continue_check: Prompting for user input: {msg}")
    entered = input(prompt_prefix + msg + " Continue? (y/n)" + prompt_suffix)
    log.debug(f"continue_check: User entered input: {entered}")
    if entered == 'y':
        return True
    else:
        return False
    

def continue_anyways(msg: str, error_msg: Optional[str] = None, override: Optional[bool] = None) -> bool:
    """
    Prompts a user whether they want to continue despite a potentially problematic input,
    by adding the string " Continue Anyways? (y/n)" to the end of the `msg` passed in.

    :param msg: message to display with the prompt
    :type msg: str
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: True if user types "y" else False
    :rtype: bool
    """
    if error_msg is None:
        error_msg = "continue_anyways: User confirmation required but interactive mode is disabled"
    _check_interactive_mode(error_msg, override)
    
    log.debug(f"continue_anyways: Prompting for user input: {msg}")
    entered = input(prompt_prefix + msg + " Continue Anyways? (y/n)" + prompt_suffix)
    log.debug(f"continue_anyways: User entered input: {entered}")
    if entered == 'y':
        return True
    else:
        return False

        
def retry(msg: str, error_msg: Optional[str] = None, override: Optional[bool] = None) -> bool:
    """
    Prompts a user if they want to retry the last input option. This will either return a True boolean
    or exit the script.

    :param msg: message to display with the prompt
    :type msg: str
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: True if user wants to retry otherwise the the script will exit
    :rtype: bool
    """
    if error_msg is None:
        error_msg = "Retry required but interactive mode is disabled"
    _check_interactive_mode(error_msg, override)
    
    log.debug(f"retry: Prompting for user input: {msg}")
    entered = input(prompt_prefix + msg + " Try Again? (y/n)" + prompt_suffix)
    log.debug(f"retry: User entered input: {entered}")
    if entered == 'y':
        return True
    else:
        exit()


class LoadedJSONData():
    def __init__(self, file_path: str, data: dict):
        self.file_path = file_path
        self.data = data

def load_json_data(msg: str, json_file_path: str = "", error_msg: Optional[str] = None, override: Optional[bool] = None) -> LoadedJSONData:
    """
    Returns a LoadedJSONData with the loaded JSON data. If unsuccessful loading file, continues prompting user until successful or exits the script.

    LoadedJSONData : {
        "file_path": csv_file_path,
        "data": data loaded from JSON file
    }

    :param msg: custom message to tell the user which file they should enter the file path of
    :type msg: str
    :param json_file_path: file path to JSON file to load, defaults to ""
    :type json_file_path: str, optional
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: object with loaded JSON data and the file path the data was loaded from
    :rtype: LoadedJSONData
    """
    if json_file_path == "":
        if error_msg is None:
            error_msg = "load_json_data: JSON file path required but not provided"
        _check_interactive_mode(error_msg, override)
        log.debug(f"load_json_data: Prompting for user input: {msg}")
        json_file_path = prompt_user(msg + "(relative file path, including file extention)")
        log.debug(f"load_json_data: User entered input: {json_file_path}")

    try:
        with open(json_file_path, 'r', encoding="utf8") as file:
            json_data = json.load(file)
            return LoadedJSONData(file_path=json_file_path, data=json_data)
    except FileNotFoundError as e:
        log.error(f'FileNotFoundError: Specified JSON file at \'{json_file_path}\' does not exist.')
        if retry(f'Enter another file path?', None, override):
            return load_json_data(msg, "", error_msg, override)
    except Exception as e:
        if retry(f'Error loading file: {e}', None, override):
            return load_json_data(msg, "", error_msg, override)


class LoadedCSVData():
    def __init__(self, file_path: str, csv: List[List[str]], headers: List[str], data: List[str] | List[List[str]]):
        self.file_path = file_path
        self.csv = csv
        self.headers = headers
        self.data = data

def load_csv_data(msg: str, csv_file_path: str = "", error_msg: Optional[str] = None, override: Optional[bool] = None) -> LoadedCSVData:
    """
    Returns a LoadedCSVData with the loaded CSV data. If unsuccessful loading file, continues prompting user until successful or exits the script.

    LoadedCSVData : {
        "file_path": csv_file_path,
        "csv": List[row List[val]] list of rows, each row being a list of column values. Including header row
        "headers": List[val] of csv header values
        "data": List[row List[val]] list of rows, each row being a list of column values. Excluding header row
    }

    :param msg: custom message to tell the user which file they should enter the file path of
    :type msg: str
    :param csv_file_path: file path to CSV file to load, defaults to ""
    :type csv_file_path: str, optional
    :param error_msg: custom error message when not in interactive mode
    :type error_msg: str, optional
    :param override: Override parameter to force a specific mode for this call
    :type override: bool, optional
    :return: object with loaded CSV data and the file path the data was loaded from
    :rtype: LoadedCSVData
    """
    if csv_file_path == "":
        if error_msg is None:
            error_msg = "load_csv_data: CSV file path required but not provided"
        _check_interactive_mode(error_msg, override)
        log.debug(f"load_csv_data: Prompting for user input: {msg}")
        csv_file_path = prompt_user(msg + "(relative file path, including file extention)")
        log.debug(f"load_csv_data: User entered input: {csv_file_path}")

    try:
        # if running into errors with reading a loaded csv, check the encoding
        #
        # changed default encoding from 'utf-8' to 'utf-8-sig'. This generally
        # works better when the input is either a CSV vs a UTF-8 CSV. Should
        # remove the BOM char '\ufeff' from the beginning of the first cell value
        with open(csv_file_path, 'r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)

            csv_complete = []

            for row in reader:
                csv_complete.append(row)

            csv_headers = csv_complete[0]

            # depending on encoding, empty cells at the end of a row might be counted as empty strings "" or not added
            # (i.e. each row of the CSV might be a different length array)
            # the following processing makes sure each row of the CSV is the same length
            for row in csv_complete[1:]:
                if len(row) < len(csv_headers):
                    for i in range(len(csv_headers) - len(row)):
                        row.append("")

            csv_data = csv_complete[1:]

            return LoadedCSVData(file_path=csv_file_path, csv=csv_complete, headers=csv_headers, data=csv_data)

    except FileNotFoundError as e:
        log.error(f'FileNotFoundError: Specified CSV file at \'{csv_file_path}\' does not exist.')
        if retry(f'Enter another file path?', None, override):
            return load_csv_data(msg, "", error_msg, override)
    except Exception as e:
        if retry(f'Error loading file: {e}', None, override):
            return load_csv_data(msg, "", error_msg, override)
