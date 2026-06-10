import logging


# LOGGING
console_log_level = logging.INFO
file_log_level = logging.INFO
save_logs_to_file = True

# Flag to run the script in interactive mode (with interactive prompts)
# If True, the script will prompt the user for input when required info is missing
interactive = True

# REQUESTS
# if the Plextrac instance is running on https without valid certs, requests will respond with cert error
# change this to false to override verification of certs
verify_ssl = True
# number of times to retry a request before throwing an error. will only throw the last error encountered if
# number of retries is exceeded. set to 0 to disable retrying requests
retries = 0

# description of script that will be print line by line when the script is run
script_info = ["====================================================================",
               "= General CSV Import Script                                        =",
               "=------------------------------------------------------------------=",
               "= Takes a CSV with rows representing client, report, finding and   =",
               "= asset data and a CSV with how to map each column to a            =",
               "= location in Plextrac.                                            =",
               "= Parses the CSV and gives the user the option to import data      =",
               "= directly to Plextrac or generate a Ptrac for each report parsed. =",
               "===================================================================="
            ]
