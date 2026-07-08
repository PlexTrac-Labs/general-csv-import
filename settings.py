import logging


# LOGGING
console_log_level = logging.INFO
file_log_level = logging.INFO
save_logs_to_file = True

# Flag to run the script in interactive mode (with interactive prompts)
# If True, the script will prompt the user for input when required info is missing
interactive = True

# PERFORMANCE / MEMORY TRACKING (perf-testing only)
# When True, the import pipeline prints per-phase timing + process memory (RSS)
# for the three heavy stages - create_temp_csv, parse_data (build object arrays),
# and generate_ptrac_json_data (build ptracs) - plus a consolidated report per
# input file. Memory is sampled on a background thread so the hot loops are not
# instrumented and runtime is barely affected.
track_performance = False
# Dedicated file for the perf tracker output (kept separate from the normal logs
# and the console). Tail this file in another terminal to watch perf output live
# while the script's usual INFO logs stream to the console as normal.
perf_log_file = "logs/perf_run.log"

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
