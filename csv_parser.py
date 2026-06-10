import base64
import json
import time
import csv
from uuid import uuid4
from copy import copy, deepcopy
import re
import zipfile

import utils.log_handler as logger
log = logger.log
import utils.general_utils as utils
import mapping_utils.dradis_utils as dradis


class CSVParser():

    # should have static header mapping build in when importing data for a static source

    # example key, value (key should be the same as header)

    # "Id": {
    #     "header": "Id",
    #     "mapping_key": "finding_title",
    #     "col_index": None
    # }

    # otherwise should be None when the script will be supplied with a header file
    csv_headers_mapping_template = {

    }
    
    # list of locations to store data in Plextrac and how to access that location
    data_mapping = {
        'no_mapping': {
            'id': 'no_mapping',
            'object_type': 'IGNORE',
            'data_type' : 'IGNORE',
            'validation_type': None,
            'input_blanks': False,
            'path': []
        },
        # CLIENT INFO
        'client_name': {
            'id': 'client_name',
            'object_type': 'CLIENT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['name']
        },
        'client_poc': {
            'id': 'client_poc',
            'object_type': 'CLIENT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['poc']
        },
        'client_poc_email': {
            'id': 'client_poc_email',
            'object_type': 'CLIENT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['poc_email']
        },
        'client_description': {
            'id': 'client_description',
            'object_type': 'CLIENT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['description']
        },
        'client_tag': {
            'id': 'client_tag',
            'object_type': 'CLIENT',
            'data_type' : 'TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags']
        },
        'client_multi_tag': {
            'id': 'client_multi_tag',
            'object_type': 'CLIENT',
            'data_type' : 'MULTI_TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags']
        },
        'client_custom_field': {
            'id': 'client_custom_field',
            'object_type': 'CLIENT',
            'data_type' : 'CUSTOM_FIELD',
            'validation_type': 'STR',
            'input_blanks': True,
            'path': ['custom_field', 'INDEX']
        },
        # REPORT INFO
        'report_name': {
            'id': 'report_name',
            'object_type': 'REPORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['name']
        },
        'report_start_date': {
            'id': 'report_start_date',
            'object_type': 'REPORT',
            'data_type' : 'DETAIL',
            'validation_type': "DATE_ZULU",
            'input_blanks': False,
            'path': ['start_date'] # validate
        },
        'report_end_date': {
            'id': 'report_end_date',
            'object_type': 'REPORT',
            'data_type' : 'DETAIL',
            'validation_type': "DATE_ZULU",
            'input_blanks': False,
            'path': ['end_date'] # validate
        },
        'report_tag': {
            'id': 'report_tag',
            'object_type': 'REPORT',
            'data_type' : 'TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags']
        },
        'report_multi_tag': {
            'id': 'report_multi_tag',
            'object_type': 'REPORT',
            'data_type' : 'MULTI_TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags']
        },
        'report_custom_field': {
            'id': 'report_custom_field',
            'object_type': 'REPORT',
            'data_type' : 'CUSTOM_FIELD',
            'validation_type': 'STR',
            'input_blanks': True,
            'path': ['custom_field', 'INDEX']
        },
        'report_narrative': {
            'id': 'report_narrative',
            'object_type': 'REPORT',
            'data_type' : 'NARRATIVE',
            'validation_type': None,
            'input_blanks': True,
            'path': ['exec_summary', 'custom_fields', 'INDEX']
        },
        # FINDING INFO
        'finding_assigned_to': {
            'id': 'finding_assigned_to',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['assignedTo'],
            'merge_type': 'SCALAR',
            'merge_override': None,
            # format email
        },
        'finding_created_at': {
            'id': 'finding_created_at',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': "DATE_EPOCH",
            'input_blanks': False,
            'path': ['createdAt'], # validate
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_closed_at': {
            'id': 'finding_closed_at',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': "DATE_EPOCH",
            'input_blanks': False,
            'path': ['closedAt'], # validate
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_last_updated_at': {
            'id': 'finding_last_updated_at',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': "DATE_EPOCH",
            'input_blanks': False,
            'path': ['last_update'], # validate
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_description': {
            'id': 'finding_description',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['description'],
            'merge_type': 'RICH_TEXT',
            'merge_override': None,
        },
        'finding_recommendations': {
            'id': 'finding_recommendations',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['recommendations'],
            'merge_type': 'RICH_TEXT',
            'merge_override': None,
        },
        'finding_references': {
            'id': 'finding_references',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['references'],
            'merge_type': 'RICH_TEXT',
            'merge_override': None,
        },
        'finding_severity': {
            'id': 'finding_severity',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': "SEVERITY",
            'input_blanks': False,
            'path': ['severity'], # validate
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_status': {
            'id': 'finding_status',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': "STATUS",
            'input_blanks': False,
            'path': ['status'], # validate
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_sub_status': {
            'id': 'finding_sub_status',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['subStatus'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_tag': {
            'id': 'finding_tag',
            'object_type': 'FINDING',
            'data_type' : 'TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags'],
            'merge_type': 'LIST',
            'merge_override': None,
        },
        'finding_multi_tag': {
            'id': 'finding_multi_tag',
            'object_type': 'FINDING',
            'data_type' : 'MULTI_TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags'],
            'merge_type': 'LIST',
            'merge_override': None,
        },
        'finding_title': {
            'id': 'finding_title',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['title'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_custom_field': {
            'id': 'finding_custom_field',
            'object_type': 'FINDING',
            'data_type' : 'KEY_CUSTOM_FIELD',
            'validation_type': None,
            'input_blanks': True,
            'path': ['fields'],
            'merge_type': 'RICH_TEXT',
            'merge_override': None,
        },
        # cvss scores
        'finding_cvss4_overall': {
            'id': 'finding_cvss4_overall',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': 'FLOAT', # validate
            'input_blanks': False,
            'path': ['risk_score', 'CVSS4', 'overall'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss4_vector': {
            'id': 'finding_cvss4_vector',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': 'CVSS4_VECTOR', # validate
            'input_blanks': False,
            'path': ['risk_score', 'CVSS4', 'vector'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss3_1_overall': {
            'id': 'finding_cvss3_1_overall',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': 'FLOAT', # validate
            'input_blanks': False,
            'path': ['risk_score', 'CVSS3_1', 'overall'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss3_1_vector': {
            'id': 'finding_cvss3_1_vector',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': 'CVSS3_VECTOR', # validate
            'input_blanks': False,
            'path': ['risk_score', 'CVSS3_1', 'vector'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss3_vector': {
            'id': 'finding_cvss3_vector',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'cvss3', 'calculation'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss3_value': {
            'id': 'finding_cvss3_value',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'cvss3', 'value'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss3_label': {
            'id': 'finding_cvss3_label',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'cvss3', 'label'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss2_vector': {
            'id': 'finding_cvss2_vector',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'cvss', 'calculation'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss2_value': {
            'id': 'finding_cvss2_value',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'cvss', 'value'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss2_label': {
            'id': 'finding_cvss2_label',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'cvss', 'label'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss_general_vector': {
            'id': 'finding_cvss_general_vector',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'general', 'calculation'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss_general_value': {
            'id': 'finding_cvss_general_value',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'general', 'value'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cvss_general_label': {
            'id': 'finding_cvss_general_label',
            'object_type': 'FINDING',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['fields', 'scores', 'general', 'label'],
            'merge_type': 'SCALAR',
            'merge_override': None,
        },
        'finding_cve': {
            'id': 'finding_cve_name',
            'object_type': 'FINDING',
            'data_type' : 'CVE',
            'validation_type': None,
            'input_blanks': False,
            'path': ['common_identifiers', 'CVE', 'INDEX'],
            'merge_type': 'LIST',
            'merge_override': None,
            # format CVE-2022-12345
        },
        'finding_cwe': {
            'id': 'finding_cwe_name',
            'object_type': 'FINDING',
            'data_type' : 'CWE',
            'validation_type': None,
            'input_blanks': False,
            'path': ['common_identifiers', 'CWE', 'INDEX'],
            'merge_type': 'LIST',
            'merge_override': None,
            # format number i.e. 501
        },
        # ASSET INFO
        'asset_multi_name': {
            'id': 'asset_multi_name',
            'object_type': 'MULTI_ASSET',
            'data_type' : 'MULTI_ASSET',
            'validation_type': None,
            'input_blanks': False,
            'path': ['asset']
        },
        'asset_name': {
            'id': 'asset_name',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['asset']
        },
        'asset_type': {
            'id': 'asset_type',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': 'ASSET_TYPE', # validate
            'input_blanks': False,
            'path': ['type']
        },
        'asset_criticality': {
            'id': 'asset_criticality',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': 'SEVERITY', # validate
            'input_blanks': False,
            'path': ['assetCriticality']
        },
        'asset_system_owner': {
            'id': 'asset_system_owner',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['system_owner']
        },
        'asset_data_owner': {
            'id': 'asset_data_owner',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['data_owner']
        },
        'asset_hostname': {
            'id': 'asset_hostname',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['hostname']
        },
        'asset_operating_systems': {
            'id': 'asset_operating_systems',
            'object_type': 'ASSET',
            'data_type' : 'LIST',
            'validation_type': None,
            'input_blanks': False,
            'path': ['operating_system']
        },
        'asset_dns_name': {
            'id': 'asset_dns_name',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['dns_name']
        },
        'asset_host_fqdn': {
            'id': 'asset_host_fqdn',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['host_fqdn']
        },
        'asset_host_rdns': {
            'id': 'asset_host_rdns',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['host_rdns']
        },
        'asset_mac_address': {
            'id': 'asset_mac_address',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['mac_address']
        },
        'asset_physical_location': {
            'id': 'asset_physical_location',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['physical_location']
        },
        'asset_netbios_name': {
            'id': 'asset_netbios_name',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['netbios_name']
        },
        'asset_total_cves': {
            'id': 'asset_total_cves',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': 'POS_INT_AS_STR', # validate
            'input_blanks': False,
            'path': ['total_cves']
        },
        'asset_pci_compliance_status': {
            'id': 'asset_pci_compliance_status',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': 'PCI_STATUS', # validate
            'input_blanks': False,
            'path': ['pci_status']
        },
        'asset_description': {
            'id': 'asset_description',
            'object_type': 'ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['description']
        },
        'asset_known_ips': {
            'id': 'asset_known_ips',
            'object_type': 'ASSET',
            'data_type' : 'LIST',
            'validation_type': None,
            'input_blanks': False,
            'path': ['knownIps']
        },
        'asset_tag': {
            'id': 'asset_tag',
            'object_type': 'ASSET',
            'data_type' : 'TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags']
        },
        'asset_multi_tag': {
            'id': 'asset_multi_tag',
            'object_type': 'ASSET',
            'data_type' : 'MULTI_TAG',
            'validation_type': None,
            'input_blanks': False,
            'path': ['tags']
        },
        'asset_ports': {
            'id': 'asset_ports',
            'object_type': 'ASSET',
            'data_type' : 'PORTS',
            'validation_type': None,
            'input_blanks': False,
            'path': ['ports']
        },
        # ASSET PORT DATA
        'asset_port_number': {
            'id': 'asset_port_number',
            'object_type': 'ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': 'POS_INT_AS_STR', # validate
            'input_blanks': False,
            'path': ['number']
        },
        'asset_port_service': {
            'id': 'asset_port_service',
            'object_type': 'ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['service']
        },
        'asset_port_protocol': {
            'id': 'asset_port_protocol',
            'object_type': 'ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['protocol']
        },
        'asset_port_version': {
            'id': 'asset_port_version',
            'object_type': 'ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['version']
        },
        # AFFECTED ASSET INFO
        'affected_asset_status': {
            'id': 'asset_status',
            'object_type': 'AFFECTED_ASSET',
            'data_type' : 'DETAIL',
            'validation_type': 'STATUS', # validate
            'input_blanks': False,
            'path': ['status']
        },
        'affected_asset_sub_status': {
            'id': 'asset_sub_status',
            'object_type': 'AFFECTED_ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['subStatus']
        },
        'affected_asset_ports': {
            'id': 'asset_ports',
            'object_type': 'AFFECTED_ASSET',
            'data_type' : 'PORTS',
            'validation_type': None,
            'input_blanks': False,
            'path': ['ports']
        },
        'affected_asset_location_url': {
            'id': 'asset_location_url',
            'object_type': 'AFFECTED_ASSET',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['locationUrl']
        },
        'affected_asset_evidence': {
            'id': 'affected_asset_evidence',
            'object_type': 'AFFECTED_ASSET',
            'data_type' : 'EVIDENCE',
            'validation_type': None,
            'input_blanks': False,
            'path': ['evidence', 'INDEX']
        },
        # AFFECTED ASSET PORT DATA
        'affected_asset_port_number': {
            'id': 'affected_asset_port_number',
            'object_type': 'AFFECTED_ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': 'POS_INT_AS_STR', # validate
            'input_blanks': False,
            'path': ['number']
        },
        'affected_asset_port_service': {
            'id': 'affected_asset_port_service',
            'object_type': 'AFFECTED_ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['service']
        },
        'affected_asset_port_protocol': {
            'id': 'affected_asset_port_protocol',
            'object_type': 'AFFECTED_ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['protocol']
        },
        'affected_asset_port_version': {
            'id': 'affected_asset_port_version',
            'object_type': 'AFFECTED_ASSET_PORT',
            'data_type' : 'DETAIL',
            'validation_type': None,
            'input_blanks': False,
            'path': ['version']
        }
    }
    #--- END CSV---


    #--- CLIENT - template of client object - list of clients generated while running the script---

    # you can add data here that should be added to all clients
    client_template_mock = { # need all arrays build out to prevent KEY ERR when adding data
        "sid": None,
        "name": f'Custom CSV Import Blank',
        "tags": [],
        "custom_field": [],
        "description": "",
        "assets": [],
        "reports": []
    }
    #--- END CLIENT---


    #--- REPORT - template of report object - list of reports generated while running the script---

    # you can add data here that should be added to all reports
    report_template_mock = { # need all arrays build out to prevent KEY ERR when adding data
        'sid': None,
        'client_sid': None,
        "name": f'Custom CSV Import Report Blank',
        "status": "Published",
        "tags": [],
        "custom_field": [],
        "start_date": None,
        "end_date": None,
        "exec_summary": {
            "custom_fields": []
        },
        "findings": []
    }
    #--- END REPORT---


    #--- FINDING - template of finding object - list of findings generated while running the script---

    # you can add data here that should be added to all findings
    finding_template_mock = { # need all arrays build out to prevent KEY ERR when adding data
        'sid': None,
        'client_sid': None,
        'report_sid': None,
        'affected_asset_sid': None,
        'title': None,
        'severity': "Informational",
        'status': "Open",
        'description': "No description",
        'recommendations': "",
        'references': "",
        'fields': {
            'scores': {
                "cvss3": {
                    "type": "cvss3",
                    "calculation": "",
                    "value": "",
                    "label": ""
                },
                "cvss": {
                    "type": "cvss",
                    "calculation": "",
                    "value": "",
                    "label": ""
                },
                "general": {
                    "type": "general",
                    "calculation": "",
                    "value": "",
                    "label": ""
                }
            }
        },
        'risk_score': {
            'CVSS4': {
                'overall': 0,
                'vector': ""
            },
            'CVSS3_1': {
                'overall': 0,
                'vector': ""
            }
        },
        'common_identifiers': {
            "CVE": [],
            "CWE": []
        },
        'tags': [],
        'affected_assets': {},
        'assets': [],
        'exhibits': [],
        'id': None,
    }
    #--- END FINDING---


    #--- ASSET - template of asset object - list of assets generated while running the script---

     # you can add data here that should be added to all assets
    asset_template_mock = { # need all arrays build out to prevent KEY ERR when adding data
        'sid': None,
        'client_sid': None,
        'finding_sid': None,
        'original_asset_sid': None,
        'is_multi': False,
        'asset': None,
        'assetCriticality': None,
        'hostname': "",
        'knownIps': [],
        'operating_system': [],
        'tags': [],
        'ports': {}
    }

    # template for created nested affected asset
    affected_asset_fields_mock = {
        'status': "Open",
        'ports': {},
        'locationUrl': "",
        'vulnerableParameters': [],
        'evidence': [],
        'notes': ""
    }
    #--- END Asset---


    def __init__(self, header_mapping=None, enable_rich_text_processing: bool = False):
        """
        
        """
        self.data_mapping = deepcopy(self.data_mapping)
        self.csv_headers_mapping: dict = deepcopy(header_mapping) if header_mapping is not None else deepcopy(self.csv_headers_mapping_template)
        self.csv_data: list = None
        self.parser_progress: int = None

        self.severities = ["Critical", "High", "Medium", "Low", "Informational"]

        self.parser_time_seconds: float = time.time()
        self.parser_time_milliseconds: int = int(self.parser_time_seconds*1000)
        self.parser_date: str = time.strftime("%m/%d/%Y", time.localtime(self.parser_time_seconds))
        self.parser_time: str = time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime(self.parser_time_seconds))

        self.doc_version = None

        self.finding_merge_strategy = None
        self.finding_merge_sid_map = {}
        self.asset_merge_strategy = None

        # Dradis (and other ZIP-paired sources) rich-text support. Disabled by
        # default so plain CSV/JSON imports keep their original text untouched.
        self.zip_file_path = None
        self.enable_rich_text_processing = enable_rich_text_processing

        self.client_template = deepcopy(self.client_template_mock)
        self.report_template = deepcopy(self.report_template_mock)
        self.finding_template = deepcopy(self.finding_template_mock)
        self.asset_template = deepcopy(self.asset_template_mock)
        self.affected_asset_fields = deepcopy(self.affected_asset_fields_mock)
        self.clients = {}
        self.reports = {}
        self.findings = {}
        self.assets = {}
        self.affected_assets = {}
        self.evidence = {}
        self.report_media = {}

        self.client_lookup = {}
        self.report_lookup = {}
        self.finding_lookup = {}
        self.asset_lookup = {}
        self.evidence_lookup = {}
        self.report_media_lookup = {}

        self.client_template['name'] = f'client_name_{self.parser_date}'
        self.report_template['name'] = f'report_name_{self.parser_date}'


    #----------getters and setter----------
    def get_data_mapping_ids(self):
        return list(self.data_mapping.keys())
    
    def get_csv_headers(self):
        """
        Returns the list of expected headers based on the csv_header value in the tracker array containing data mapping info.
        """
        return list(map(lambda x:x['header'], self.csv_headers_mapping.values()))

    def get_index_from_header(self, header):
        return self.csv_headers_mapping.get(header, {}).get("col_index")

    def get_mapping_key_from_header(self, header):
        return self.csv_headers_mapping.get(header, {}).get("mapping_key")
    
    def get_index_from_key(self, mapping_key):
        for value in self.csv_headers_mapping.values():
            if mapping_key == value['mapping_key']:
                return value['col_index']
        return None

    # only returns the first instance of the key. will not get expected return if a generic key is used i.e. finding_custom_field
    def get_header_from_key(self, mapping_key):
        for value in self.csv_headers_mapping.values():
            if mapping_key == value['mapping_key']:
                return value['header']
        return None

    def set_finding_merge_strategy(self, strategy: str):
        if strategy not in ["title", "user_defined_fields", "all_fields"]:
            log.warning(f"Incorrect key value '{strategy}': Unknown findings merge strategy, accepted values [\"title\", \"user_defined_fields\", \"all_fields\"]\nWill not merge findings...")
            return
        self.finding_merge_strategy = strategy
        self.asset_merge_strategy = strategy
    #----------End getters and setter----------


    #----------logging functions----------
    def display_parser_results(self):
        log.success(f'CSV parsing completed!')
        log.info(f'Detailed logs can be found in \'{log.LOGS_FILE_PATH}\'')

    def save_data_to_csv(self, file_path: str) -> None:
        """
        Useful for testing to read the CSV data the CSVParser object is currently holding onto.

        Note: Microsoft Excel has a limit of 32,767 characters for a single cell. This will make the CSV
              file look wrong if there is a cell that is longer than this. Python is still able to handle
              this length of a string perfectly fine.

        :param file_path: file path and name to save the CSV to
        :type file_path: str
        """
        log.info(f'Saving current data to CSV \'{file_path}\'')
        try:
            with open(file_path, 'w', newline="", encoding="utf-8") as file:
                writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(self.get_csv_headers())
                writer.writerows(self.csv_data)
            log.success(f'Saved data to CSV \'{file_path}\'')
        except Exception as e:
            log.exception(f'Could not save data to CSV: {e}')
    #----------End logging functions----------


    #----------Post parsing handling functions----------
    def handle_finding_dup_names(self):
        """
        Runs through all findings and updates the titles for any duplicates.
        Cannot be done during parsing since we still have to look for duplicates there
        """
        if self.finding_merge_strategy:
            merged_findings = {}

            findings_by_report = {}
            for finding_sid, finding in self.findings.items():
                report_sid = finding['report_sid']
                if report_sid not in findings_by_report:
                    findings_by_report[report_sid] = {}
                findings_by_report[report_sid][finding_sid] = finding

            for report in self.reports.values():
                report_sid = report['sid']
                if report_sid in findings_by_report:
                    merged_findings.update(self.combine_findings(findings_by_report[report_sid], self.finding_merge_strategy))

            self.findings = merged_findings

            for report in self.reports.values():
                new_finding_sids = []
                seen_sids = set()
                for finding_sid in report['findings']:
                    mapped_sid = self.finding_merge_sid_map.get(finding_sid, finding_sid)
                    if mapped_sid not in seen_sids:
                        new_finding_sids.append(mapped_sid)
                        seen_sids.add(mapped_sid)
                self.reports[report['sid']]['findings'] = new_finding_sids

            for asset in self.assets.values():
                if asset['finding_sid'] in self.finding_merge_sid_map:
                    self.assets[asset['sid']]['finding_sid'] = self.finding_merge_sid_map[asset['finding_sid']]

            title_groups = {}
            for finding in self.findings.values():
                title = finding['title']
                if title not in title_groups:
                    title_groups[title] = []
                title_groups[title].append(finding)

            for findings in title_groups.values():
                if len(findings) > 1:
                    findings.sort(key=lambda x: x['dup_num'])
                    for i, finding in enumerate(findings, 1):
                        finding['dup_num'] = i

        for f in self.findings.values():
            if f['dup_num'] > 1:
                f['title'] = f'{f["title"]} ({f["dup_num"]})'
            f.pop("dup_num")


    def combine_findings(self, finding_list_to_merge, merge_strategy: str):
        current_mapping_keys = [x['mapping_key'] for x in self.csv_headers_mapping.values()]
        filtered_data_mappings = {k: v for k, v in self.data_mapping.items() if k in current_mapping_keys}
        if not filtered_data_mappings:
            filtered_data_mappings = {k: v for k, v in self.data_mapping.items() if v['object_type'] == "FINDING"}

        scalar_paths = [v['path'] for v in filtered_data_mappings.values() if v['object_type'] == "FINDING" and v['merge_type'] == "SCALAR"]
        rich_text_paths = [v['path'] for v in filtered_data_mappings.values() if v['object_type'] == "FINDING" and v['merge_type'] == "RICH_TEXT"]
        list_paths = [v['path'] for v in filtered_data_mappings.values() if v['object_type'] == "FINDING" and v['merge_type'] == "LIST"]
        rich_text_exclusions = [['fields']]

        def _get_path(obj, path):
            cur = obj
            for k in path:
                if k == "INDEX":
                    return cur
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    return None
            return cur

        def _set_path(obj, path, value):
            if len(path) == 1:
                if path[0] != "INDEX":
                    obj[path[0]] = value
                return
            if path[0] == "INDEX":
                log.warning("Reached unexpected conditional code path, check fundamental script logic")
                return
            if path[0] not in obj:
                obj[path[0]] = {}
            _set_path(obj[path[0]], path[1:], value)

        def _has_value(x):
            if x is None:
                return False
            if isinstance(x, str):
                return len(x) > 0
            if isinstance(x, (list, tuple, set, dict)):
                return len(x) > 0
            return True

        def _normalized_text(text):
            if not isinstance(text, str):
                return str(text)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        def _is_value_contained_in_base(base_value, inc_value):
            if not base_value or not inc_value:
                return False
            return _normalized_text(inc_value) in _normalized_text(base_value)

        def _merge_lists(a, b):
            a = a or []
            b = b or []
            seen = set()
            out = []

            def _key(item):
                try:
                    hash(item)
                    return ("H", item)
                except TypeError:
                    return ("U", json.dumps(item, sort_keys=True, default=str))

            for item in a + b:
                key = _key(item)
                if key not in seen:
                    seen.add(key)
                    out.append(item)
            return out

        def _are_matching(f1, f2) -> bool:
            if merge_strategy == "title":
                return True
            if merge_strategy == "user_defined_fields":
                return all(_get_path(f1, path) == _get_path(f2, path) for path in scalar_paths)
            if merge_strategy == "all_fields":
                return (
                    all(_get_path(f1, path) == _get_path(f2, path) for path in scalar_paths)
                    and all(_get_path(f1, path) == _get_path(f2, path) for path in rich_text_paths)
                )
            log.critical("Incorrect key value: Unknown findings merge strategy")
            exit(1)

        def _merge_findings(base: dict, incoming: dict):
            merged = deepcopy(base)

            for path in scalar_paths:
                base_val = _get_path(merged, path)
                inc_val = _get_path(incoming, path)
                if not _has_value(base_val) and _has_value(inc_val):
                    _set_path(merged, path, inc_val)

            for path in rich_text_paths:
                if path in rich_text_exclusions:
                    continue
                base_val = _get_path(merged, path)
                inc_val = _get_path(incoming, path)
                if merge_strategy == "user_defined_fields":
                    if base_val and inc_val and base_val != inc_val:
                        if not _is_value_contained_in_base(base_val, inc_val):
                            _set_path(merged, path, f"{base_val}\n{inc_val}")
                    elif not base_val and inc_val:
                        _set_path(merged, path, inc_val)
                elif not base_val and inc_val:
                    _set_path(merged, path, inc_val)

            base_fields = _get_path(merged, ["fields"])
            inc_fields = _get_path(incoming, ["fields"])
            if isinstance(base_fields, dict) and isinstance(inc_fields, dict):
                for field_key, field_value in inc_fields.items():
                    if field_key == "scores":
                        continue
                    if field_key not in base_fields:
                        base_fields[field_key] = deepcopy(field_value)
                        continue
                    base_field = base_fields[field_key]
                    if isinstance(base_field, dict) and isinstance(field_value, dict):
                        base_value = base_field.get("value", "")
                        inc_value = field_value.get("value", "")
                        if base_value and inc_value and not _is_value_contained_in_base(base_value, inc_value):
                            merged_field = deepcopy(base_field)
                            merged_field["value"] = f"{base_value}\n{inc_value}"
                            base_fields[field_key] = merged_field
                        elif not base_value and inc_value:
                            base_fields[field_key] = deepcopy(field_value)
                    elif not _has_value(base_field):
                        base_fields[field_key] = deepcopy(field_value)
                _set_path(merged, ["fields"], base_fields)

            for path in list_paths:
                base_val = _get_path(merged, path)
                inc_val = _get_path(incoming, path)
                if isinstance(base_val, list) or isinstance(inc_val, list):
                    _set_path(merged, path, _merge_lists(base_val, inc_val))

            base_affected_asset_sid = _get_path(merged, ["affected_asset_sid"])
            inc_affected_asset_sid = _get_path(incoming, ["affected_asset_sid"])
            if isinstance(base_affected_asset_sid, dict) and isinstance(inc_affected_asset_sid, dict):
                _set_path(merged, ["affected_asset_sid"], {**base_affected_asset_sid, **inc_affected_asset_sid})

            base_assets = _get_path(merged, ["assets"])
            inc_assets = _get_path(incoming, ["assets"])
            if isinstance(base_assets, list) or isinstance(inc_assets, list):
                _set_path(merged, ["assets"], _merge_lists(base_assets, inc_assets))

            return merged

        finding_groups = {}
        for finding in finding_list_to_merge.values():
            finding_title = finding['title']
            if finding_title not in finding_groups:
                finding_groups[finding_title] = {}
            finding_groups[finding_title][finding['sid']] = finding

        new_findings = {}
        for group in finding_groups.values():
            remaining = list(group.keys())
            while remaining:
                canonical_sid = remaining[0]
                canonical = deepcopy(group[canonical_sid])
                remaining.remove(canonical_sid)

                to_absorb = []
                for sid in remaining:
                    if _are_matching(canonical, group[sid]):
                        to_absorb.append(sid)

                for sid in to_absorb:
                    canonical = _merge_findings(canonical, group[sid])
                    self.finding_merge_sid_map[sid] = canonical_sid
                    remaining.remove(sid)

                new_findings[canonical_sid] = canonical

        return new_findings


    def add_asset_to_finding(self, finding, asset, finding_sid, asset_sid):
        """
        Adds the asset data as an affected asset on a finding.
        Must be called after the finding and asset are created
        """
        asset_id = asset['id']

        affected_asset = asset
        affected_asset_fields = deepcopy(self.affected_asset_fields)

        # single asset with possible affected asset fields
        if self.assets[asset_sid]['is_multi'] == False:
            affected_asset_fields = self.affected_assets[self.findings[finding_sid]['affected_asset_sid']]
        
        affected_asset.update(affected_asset_fields)

        if asset_id in finding['affected_assets']:
            existing_affected_asset = finding['affected_assets'][asset_id]
            existing_affected_asset['status'] = affected_asset.get('status', existing_affected_asset.get('status'))
            existing_affected_asset['locationUrl'] = affected_asset.get('locationUrl', "") if affected_asset.get('locationUrl', "") != "" else existing_affected_asset.get('locationUrl', "")
            existing_affected_asset['ports'].update(affected_asset.get('ports', {}))
            existing_affected_asset['vulnerableParameters'] = list(
                set(existing_affected_asset.get('vulnerableParameters', []) + affected_asset.get('vulnerableParameters', []))
            )

            if self.asset_merge_strategy in ["user_defined_fields", "all_fields"]:
                notes_1 = existing_affected_asset.get("notes", "")
                notes_2 = affected_asset.get("notes", "")
                if notes_1 and notes_2:
                    existing_affected_asset['notes'] = f'{notes_1}\n{notes_2}'
                else:
                    existing_affected_asset['notes'] = notes_1 or notes_2
            else:
                existing_affected_asset['notes'] = affected_asset.get('notes', "") if affected_asset.get('notes', "") != "" else existing_affected_asset.get('notes', "")

            finding['affected_assets'][asset_id] = existing_affected_asset
        else:
            finding['affected_assets'][asset_id] = affected_asset

        return finding
    

    def update_asset_list_fields(self, og_asset, dup_asset, update_ports: bool = True) -> None:
        """
        Adds extra values from the OS, known IPs, tags, and ports fields from a duplicate asset to the original.
        Updates original asset and does not return anything.

        Important: Updating finding.affected_assets reference with another asset reference will incorrectly add additional affected ports - Must set update_ports to False

        :param og_asset: The reference to the original asset 
        :type og_asset: dict of asset - stored in self.assets or a copy that was created from an asset in that list. Includes ptrac ReportAssets or ptrac finding.affected_assets
        :param dup_asset: The reference to the duplicate asset
        :type dup_asset: dict of asset - stored in self.assets
        :param update_ports: Should new port numbers be added to original asset, defaults to True
        :type update_ports: bool, optional
        """
        utils.merge_sanitized_str_lists(og_asset['operating_system'], dup_asset['operating_system'])
        utils.merge_sanitized_str_lists(og_asset['knownIps'], dup_asset['knownIps'])
        utils.merge_sanitized_str_lists(og_asset['tags'], dup_asset['tags'])
        if update_ports:
            for port_id, port_data in dup_asset['ports'].items():
                if port_id not in og_asset['ports']:
                    og_asset['ports'][port_id] = port_data

    #----------End post parsing handling functions----------


    #----------Object Handling----------
    def handle_client(self, row):
        """
        Returns a client sid and name based on the csv columns specified that relate to client data.

        Looks through list of clients already created during this running instance of the script
        Determines if a client exists that the current entry should be added to

        Returns the client sid and name of existing client or
        Creates new client and adds all csv column data that relates to the client
        """
        header = self.get_header_from_key("client_name")
        if header == None:
            client_name = self.client_template['name']
        else:
            index = self.get_index_from_header(header)
            value = row[index] # TODO there could be an index problem if client_name is NOT used as a mapping_key in self.csv_headers_mapping_template - currently handled elsewhere
            client_name = value if value != "" else self.client_template['name']

        if client_name in self.client_lookup:
            client_sid = self.client_lookup[client_name]
            log.info(f'Found existing client {self.clients[client_sid]["name"]}')
            return client_sid, self.clients[client_sid]['name']

        # return new client
        log.info(f'No client found. Creating new client...')
        new_sid = uuid4()
        client = deepcopy(self.client_template)
        client['sid'] = new_sid

        self.add_data_to_object(client, "CLIENT", row)

        self.clients[new_sid] = client
        self.client_lookup[client['name']] = new_sid

        return new_sid, client['name']


    def handle_report(self, row, client_sid):
        """
        Returns a report sid and name based the csv columns specified that relate to report data.

        Looks through list of reports already created during this running instance of the script for the given client
        Determines if a report exists that the current entry should be added to

        Returns the report sid and name of existing report or
        Creates new report and adds all csv column data that relates to the report
        """
        header = self.get_header_from_key("report_name")
        if header == None:
            report_name = self.report_template['name']
        else:
            index = self.get_index_from_header(header)
            value = row[index] # TODO there could be an index problem if report_name is NOT used as a mapping_key in self.csv_headers_mapping_template - currently handled elsewhere
            report_name = value if value != "" else self.report_template['name']

        lookup_key = (client_sid, report_name)
        if lookup_key in self.report_lookup:
            report_sid = self.report_lookup[lookup_key]
            log.info(f'Found existing report {self.reports[report_sid]["name"]}')
            return report_sid, self.reports[report_sid]['name']

        # return new report
        log.info(f'No report found. Creating new report...')
        new_sid = uuid4()
        report = deepcopy(self.report_template)
        report['sid'] = new_sid
        report['client_sid'] = client_sid

        self.add_data_to_object(report, "REPORT", row)

        self.reports[new_sid] = report
        self.clients[client_sid]['reports'].append(new_sid)
        self.report_lookup[(client_sid, report['name'])] = new_sid

        return new_sid, report['name']


    def handle_finding(self, row, client_sid, report_sid):
        """
        Returns a finding sid and name based the csv columns specified that relate to finding data.

        Looks through list of findings already created during this running instance of the script for the given client and report
        Determines if a finding has a duplicate and needs a different finding title

        Creates new finding and adds all csv column data that relates to the finding

        Returns the finding sid and name of the new finding
        """
        header = self.get_header_from_key('finding_title')
        index = self.get_index_from_header(header)
        value = row[index] # TODO there is checking in the parse_data func to prevent index errors here
        lookup_key = (client_sid, report_sid, value)
        matching_findings = self.finding_lookup.get(lookup_key, [])

        # return finding
        new_sid = uuid4()
        finding = deepcopy(self.finding_template)
        finding['sid'] = new_sid
        finding['client_sid'] = client_sid
        finding['report_sid'] = report_sid
        finding['dup_num'] = len(matching_findings) + 1

        self.add_data_to_object(finding, "FINDING", row)

        self.findings[new_sid] = finding
        self.reports[report_sid]['findings'].append(new_sid)
        if lookup_key not in self.finding_lookup:
            self.finding_lookup[lookup_key] = []
        self.finding_lookup[lookup_key].append(new_sid)

        return new_sid, finding['title']


    def handle_multi_asset(self, row, client_sid, finding_sid):
        """
        Creates an asset for each asset name listed in the asset_multi_name column.

        Looks through list of assets already created during this running instance of the script for the given client
        Determines if an asset has a duplicate, but will create a new asset with the same name

        Does NOT add any other asset data keys besides the names.
        """
        header = self.get_header_from_key('asset_multi_name')
        if header == None:
            return

        index = self.get_index_from_header(header)
        value = row[index] # TODO there could be an index problem if we DO use the asset_multi_name as a mapping_key in self.csv_headers_mapping_template
        if value == "":
            return

        for asset_name in value.split(","):
            asset_name = asset_name.strip()

            lookup_key = (client_sid, asset_name)
            matching_assets = self.asset_lookup.get(lookup_key, [])

            # create asset
            new_sid = uuid4()
            asset = deepcopy(self.asset_template)
            asset['sid'] = new_sid
            asset['client_sid'] = client_sid
            asset['finding_sid'] = finding_sid
            asset['dup_num'] = len(matching_assets) + 1
            if len(matching_assets) > 0:
                asset['original_asset_sid'] = matching_assets[0]

            self.set_value(asset, ['asset'], asset_name)
            asset['is_multi'] = True

            self.assets[new_sid] = asset
            self.clients[client_sid]['assets'].append(new_sid)
            self.findings[finding_sid]['assets'].append(new_sid)
            if lookup_key not in self.asset_lookup:
                self.asset_lookup[lookup_key] = []
            self.asset_lookup[lookup_key].append(new_sid)


    def handle_asset(self, row, client_sid, finding_sid):
        """
        Returns an asset sid and name based the csv columns specified that relate to asset data.

        Looks through list of assets already created during this running instance of the script for the given client
        Determines if an asset has a duplicate, but will create a new asset with the same name

        Creates new asset and adds all csv column data that relates to the asset

        Returns the asset sid and name of the new asset
        """
        header = self.get_header_from_key('asset_name')
        if header == None:
            return None, None

        index = self.get_index_from_header(header) # TODO verify there are no index problems like the other objects
        if index == None:
            return None, None

        value = row[index]
        if value == "":
            return None, None

        lookup_key = (client_sid, value)
        matching_assets = self.asset_lookup.get(lookup_key, [])

        # return asset
        new_sid = uuid4()
        asset = deepcopy(self.asset_template)
        asset['sid'] = new_sid
        asset['client_sid'] = client_sid
        asset['finding_sid'] = finding_sid
        asset['dup_num'] = len(matching_assets) + 1
        if len(matching_assets) > 0:
            asset['original_asset_sid'] = matching_assets[0]

        self.add_data_to_object(asset, "ASSET", row)

        # adds unaffected port data to asset
        asset_ports = asset['ports']
        self.handle_port_data(row, asset_ports, "ASSET_PORT")

        self.assets[new_sid] = asset
        self.clients[client_sid]['assets'].append(new_sid)
        self.findings[finding_sid]['assets'].append(new_sid)
        if lookup_key not in self.asset_lookup:
            self.asset_lookup[lookup_key] = []
        self.asset_lookup[lookup_key].append(new_sid)

        return new_sid, asset['asset']

    
    def handle_affected_asset(self, row, finding_sid, asset_sid=None):
        """
        Handles affected asset data that relates to an asset that should be added on a finding

        Creates new affected_asset and adds all csv column data that relates to the affected_asset
        """
        new_sid = uuid4()
        affected_asset = deepcopy(self.affected_asset_fields)

        self.add_data_to_object(affected_asset, "AFFECTED_ASSET", row)

        for evidence in affected_asset['evidence']:
            if asset_sid is not None:
                evidence['assets'] = [str(asset_sid)]
            self.evidence[evidence['id']] = evidence
            self.evidence_lookup[(finding_sid, asset_sid, evidence['caption'])] = evidence['id']

        # adds affected port data to affected asset
        affected_asset_ports = affected_asset['ports']
        self.handle_port_data(row, affected_asset_ports, "AFFECTED_ASSET_PORT")

        self.affected_assets[new_sid] = affected_asset
        self.findings[finding_sid]['affected_asset_sid'] = new_sid


    def handle_port_data(self, row, ports, type):
        """
        Handles asset port data that relates to an asset that should be added on an asset or affected asset

        Creates new port data object and adds all csv column data that relates to the port
        """
        port_data = {"number": None}

        self.add_data_to_object(port_data, type, row)

        if port_data['number'] != None:
            ports[int(port_data['number'])] = port_data
    #----------End Object Handling----------


    #----------functions to add specific types of data to certain locations----------
    def validate_value(self, header, mapping, value):
        """
        Invalid values will return an empty string or None
        
        If there is a chance that some might have mapping might have `input_blanks` set to True it should return "" rather than None
        """
        if mapping['validation_type'] == None:
            return value

        if mapping['validation_type'] == "DATE_ZULU":
            value = str(value)
            try:
                raw_date = utils.try_parsing_date(value)
            except ValueError:
                log.exception(f"Non-valid date format for '{header}': '{value}'. Ignoring...")
                return ""
            except Exception:
                log.exception(f"Could not parse date value for '{header}': '{value}'. Ignoring...")
                return ""
            return time.strftime("%Y-%m-%dT08:00:00.000000Z", raw_date)

        if mapping['validation_type'] == "DATE_EPOCH":
            value = str(value)
            try:
                raw_date = utils.try_parsing_date(value)
            except ValueError:
                log.exception(f"Non-valid date format for '{header}': '{value}'. Ignoring...")
                return ""
            except Exception:
                log.exception(f"Could not parse date value for '{header}': '{value}'. Ignoring...")
                return ""
            return int(time.mktime(raw_date)*1000)

        if mapping['validation_type'] == "SEVERITY":
            # ["Critical", "High", "Medium", "Low", "Informational"]
            if value not in self.severities:
                log.warning(f'Header "{header}" value "{value}" is not a valid severity. Must be in the list ["Critical", "High", "Medium", "Low", "Informational"] Skipping...')
                return None
            return value

        if mapping['validation_type'] == "STATUS":
            statuses = ["Open", "In Process", "Closed"]
            if value not in statuses:
                log.warning(f'Header "{header}" value "{value}" is not a valid status. Must be in the list ["Open", "In Process", "Closed"] Skipping...')
                return None
            return value

        if mapping['validation_type'] == "ASSET_TYPE":
            types = ["Workstation", "Server", "Network Device", "Application", "General"]
            if value not in types:
                log.warning(f'Header "{header}" value "{value}" is not a valid asset type. Must be in the list ["Workstation", "Server", "Network Device", "Application", "General"] Skipping...')
                return None
            return value

        if mapping['validation_type'] == "PCI_STATUS":
            pass_types = ["Pass", "pass", "Yes", "yes", "y"]
            fail_types = ["Fail", "fail", "No", "no", "n"]
            if value in pass_types:
                value = "pass"
            elif value in fail_types:
                value = "fail"
            else:
                log.warning(f'Header "{header}" value "{value}" is not a valid asset type. Must be in the list ["Pass", "pass", "Yes", "yes", "y"] or ["Fail", "fail", "No", "no", "n"] Skipping...')
                return None
            return value

        if mapping['validation_type'] == "CVSS3_VECTOR":
            # Validates CVSS 3.0 and 3.1 vectors for finding_cvss3_1_vector.
            # CVSS 4.0 vectors belong in finding_cvss4_vector (use CVSS4_VECTOR type).
            value = utils.normalize_cvss_vector(value)
            version = utils.detect_cvss_version(value)
            if version not in ("3.0", "3.1") and not utils.is_valid_cvss3_vector(value):
                log.warning(
                    f'Header "{header}" value "{value}" is not a valid CVSS 3.x vector. '
                    f'Accepted: CVSS:3.0/..., CVSS:3.1/..., or a bare metric string '
                    f'(e.g. AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H). '
                    f'For CVSS 4.0 use the finding_cvss4_vector mapping key. Skipping...'
                )
                return None
            if version in ("3.0", "3.1"):
                return value[9:]  # strip CVSS:3.x/ prefix for PTRAC storage
            return value          # bare metric string: store as-is

        if mapping['validation_type'] == "CVSS4_VECTOR":
            # Validates CVSS 4.0 vectors for finding_cvss4_vector.
            value = utils.normalize_cvss_vector(value)
            if not utils.is_valid_cvss4_vector(value):
                log.warning(
                    f'Header "{header}" value "{value}" is not a valid CVSS 4.0 vector. '
                    f'Must start with CVSS:4.0/ and include all 11 base metrics '
                    f'(AV, AC, AT, PR, UI, VC, VI, VA, SC, SI, SA). Skipping...'
                )
                return None
            return value  # keep full CVSS:4.0/... string

        if mapping['validation_type'] == "POS_INT_AS_STR":
            if not utils.is_str_positive_integer(value):
                log.warning(f'Header "{header}" value "{value}" is not a valid number. Must be a positive integer. Skipping...')
                return None
            return value

        if mapping['validation_type'] == "FLOAT":
            try:
                return float(value)
            except ValueError:
                log.exception(f'Header "{header}" value "{value}" is not a valid number. Skipping...')
                return None

        if mapping['validation_type'] == "BOOL":
            try:
                return bool(value)
            except ValueError:
                log.exception(f'Header "{header}" value "{value}" cannot be converted to a boolean. Skipping...')
                return None

        if mapping['validation_type'] == "INT":
            try:
                return int(value)
            except ValueError:
                log.exception(f'Header "{header}" value "{value}" cannot be converted to an integer. Skipping...')
                return None
        
        if mapping['validation_type'] == "STR":
            try:
                return str(value)
            except ValueError:
                log.exception(f'Header "{header}" value "{value}" cannot be converted to a string. Skipping...')
                return None

    # base function that takes path and sets value
    def set_value(self, obj, path, value):
        if len(path) == 1:
            if path[0] == "INDEX":
                obj.append(value)
            elif path[0] == "references":
                obj['references'] = f'{obj["references"]}\n\n{value}'
            else:    
                obj[path[0]] = value
            return

        if path[0] == "INDEX":
            obj.append({})
            self.set_value(obj[-1], path[1:], value)
        else:
            self.set_value(obj[path[0]], path[1:], value)

    def _generate_report_media_file_name(self, image_file_name: str) -> str:
        file_extension = ""
        if "." in image_file_name:
            file_extension = f'.{image_file_name.rsplit(".", 1)[1]}'
        return f'{uuid4()}{file_extension}'

    def _load_report_media(self, image_tag: str, image_node_id: str, image_file_name: str):
        """
        Load image bytes from the paired ZIP, base64 encode them, store them in
        ``self.report_media``, and cache by normalized Dradis image tag.
        """
        normalized_image_tag = image_tag[1:-1]
        if normalized_image_tag in self.report_media_lookup:
            return self.report_media_lookup[normalized_image_tag]

        if not self.zip_file_path:
            log.warning(f'Could not load image \'{image_file_name}\'. No paired ZIP file is available. Ignoring...')
            return None

        try:
            with zipfile.ZipFile(self.zip_file_path, "r") as zip_ref:
                zip_member_path = f'{image_node_id}/{image_file_name}'
                image_bytes = None

                if zip_member_path in zip_ref.namelist():
                    image_bytes = zip_ref.read(zip_member_path)
                else:
                    matching_zip_member = next(
                        (
                            file_name for file_name in zip_ref.namelist()
                            if file_name.endswith(f'/{zip_member_path}') or file_name == zip_member_path
                        ),
                        None,
                    )
                    if matching_zip_member is not None:
                        image_bytes = zip_ref.read(matching_zip_member)

                if image_bytes is None:
                    raise FileNotFoundError(f'Could not find image path \'{zip_member_path}\' in ZIP \'{self.zip_file_path}\'')

            report_media_file_name = self._generate_report_media_file_name(image_file_name)
            self.report_media[report_media_file_name] = {
                "data": base64.b64encode(image_bytes).decode("utf-8")
            }
            self.report_media_lookup[normalized_image_tag] = report_media_file_name
            return report_media_file_name
        except FileNotFoundError as e:
            log.error(f'Could not load image \'{image_file_name}\'. Ignoring...\n{e}')
        except Exception as e:
            log.error(e)
        return None

    def _build_image_replacement(self, image_ref: dradis.DradisImageReference) -> str:
        new_image_tag = f"Missing image for tag '{image_ref.normalized_tag[1:-1]}'"
        report_media_file_name = self._load_report_media(image_ref.normalized_tag, image_ref.node_id, image_ref.file_name)
        if report_media_file_name is not None:
            new_image_tag = f'<img src="/api/v1/uploads/{report_media_file_name}">'
            if image_ref.caption:
                new_image_tag = f'<figure class="image"><img src="/api/v1/uploads/{report_media_file_name}" ><figcaption>{image_ref.caption}</figcaption></figure>'
        return new_image_tag

    def add_image(self, value, field):
        """
        Replace Dradis image markers in a value with PlexTrac upload references.

        Dradis provides a CSV and ZIP file. The ZIP file contains a folder
        structure of images referenced by markers in rich text fields.
        """
        new_value = value
        while isinstance(new_value, str):
            image_ref = dradis.find_dradis_image_reference(new_value)
            if image_ref is None:
                break

            log.debug(f'Found image tag in {field} at char {image_ref.start_index}')
            log.debug(f'Parsed image from tag in project \'{image_ref.project_id}\' with file name \'{image_ref.file_name}\' in node \'{image_ref.node_id}\'. Loading image...')

            new_image_tag = self._build_image_replacement(image_ref)
            new_value = new_value[:image_ref.start_index] + new_image_tag + new_value[image_ref.end_index:]

        return new_value

    def replace_images_with_placeholders(self, value, field):
        """
        Hold Dradis image markers through Textile conversion so Textile does not
        convert them into incorrect external image tags.
        """
        new_value = value
        image_placeholders = {}
        while isinstance(new_value, str):
            image_ref = dradis.find_dradis_image_reference(new_value)
            if image_ref is None:
                break

            log.debug(f'Found image tag in {field} at char {image_ref.start_index}')
            log.debug(f'Parsed image from tag in project \'{image_ref.project_id}\' with file name \'{image_ref.file_name}\' in node \'{image_ref.node_id}\'. Loading image...')

            placeholder = f"zzdradisimageplaceholder{len(image_placeholders)}zz"
            image_placeholders[placeholder] = self._build_image_replacement(image_ref)
            new_value = new_value[:image_ref.start_index] + placeholder + new_value[image_ref.end_index:]

        return new_value, image_placeholders

    def format_rich_text_value(self, value, header):
        if not self.enable_rich_text_processing:
            return value
        new_value, image_placeholders = self.replace_images_with_placeholders(value, header)
        new_value = utils.convert_textile_to_html(new_value)
        for placeholder, image_tag in image_placeholders.items():
            new_value = new_value.replace(placeholder, image_tag)
        new_value = utils.strip_extra_lines(new_value, header)
        return new_value

    # detail
    def add_detail(self, header, obj, mapping, value):
        path = mapping['path']
        if mapping['id'] in ["client_description", "finding_description", "finding_recommendations", "finding_references", "asset_description"]:
            value = self.format_rich_text_value(value, header)
        self.set_value(obj, path, value)

    # client/report custom field
    def add_label_value(self, header, obj, mapping, value):
        label_value = {
            'label': header.strip(),
            'value': value
        }

        self.set_value(obj, mapping['path'], label_value)

    # finding custom field
    def add_key_label_value(self, header, obj, mapping, value):
        path = copy(mapping['path'])
        path.append(utils.format_key(header.strip()))
        value = self.format_rich_text_value(value, header)

        label_value = {
            'label': header.strip(),
            'value': value
        }

        self.set_value(obj, path, label_value)

    # tag
    def add_tag(self, header, obj, mapping, value):
        if "," in value:
            log.exception(f'Single tag value of \'{value}\' contains a \',\'. Will be processed into the tag \'{utils.format_key(value)}\'.Is this value multiple tags? Update the mapping file \'{header}\' column key from \'{str(mapping["object_type"]).lower()}_tag\' to \'{str(mapping["object_type"]).lower()}_multi_tag\'')
        utils.add_tag(obj['tags'], value)

    # multiple tags
    def add_multi_tag(self, header, obj, mapping, value):
        tags = value.split(",")
        for tag in tags:
            utils.add_tag(obj['tags'], tag)

    # report narrative
    def add_label_text(self, header, obj, mapping, value):
        value = self.format_rich_text_value(value, header)

        label_text = {
            'label': header.strip(),
            'text': value
        }

        self.set_value(obj, mapping['path'], label_text)

    # finding cve
    def add_cve(self, header, obj, mapping, value):
        cves = value.split(",")
        for cve in cves:
            cve_clean = cve.strip()
            if not utils.is_valid_cve(cve_clean):
                log.warning(f'Header "{header}" value "{cve_clean}" is not a list of valid CVE IDs. Expects "CVE-2022-12345" or "CVE-2022-12345, CVE-2022-67890" Skipping...')
                return
            
            values = cve_clean.split("-")
            data= {
                "name": cve_clean,
                "year": int(values[1]),
                "id": int(values[2]),
                "link": f'https://www.cve.org/CVERecord?id={cve_clean}'
            }
            self.set_value(obj, mapping['path'], data)
                

    # finding cwe
    def add_cwe(self, header, obj, mapping, value):
        cwes = value.split(",")
        for cwe in cwes:
            cwe_clean = cwe.strip()
            if not (utils.is_valid_cwe(cwe_clean) or utils.is_valid_cwe(cwe_clean, has_prefix=False)):
                log.warning(f'Header "{header}" value "{cwe_clean}" is not a list of valid CWE numbers. Expects "1234" or "CWE-1234" Skipping...')
                return

            if cwe_clean.startswith("CWE"):
                cwe_clean = cwe_clean[4:]

            data = {
                "name": f'CWE-{cwe_clean}',
                "id": int(cwe_clean),
                "link": f'https://cwe.mitre.org/data/definitions/{cwe_clean}.html'
            }
            self.set_value(obj, mapping['path'], data)


    # list (asset known ips, operating systems)
    def add_list(self, header, obj, mapping, value):
        log.debug(f'Updating \'{header}\' with values [{value}]')
        values = value.split(",")
        for value in values:
            new_value = value.strip()
            log.debug(f'Adding \'{new_value}\' to \'{mapping["path"][0]}\' list with existing values {obj[mapping["path"][0]]}')
            if value not in obj[mapping['path'][0]]:
                if mapping['path'][0] == "knownIps": # add to list of known IPs, must be a valid IPv4 or IPv6
                    if utils.is_valid_ipv4_address(new_value) or utils.is_valid_ipv6_address(new_value):
                        obj[mapping['path'][0]].append(new_value)
                    else:
                        log.warning(f'IP \'{new_value}\' is not a valid IPv4 or IPv6 address. Skipping...')
                else: # add to any list with no validation
                    obj[mapping['path'][0]].append(new_value)

        log.debug(f'Updated list {obj[mapping["path"][0]]}')

    # asset port obj - csv data should be formatted "port|service|protocol|version"
    def add_port(self, header, obj, mapping, value):
        ports = value.split(",")
        for port in ports:
            data = port.strip().split("|")
            if len(data) != 4:
                log.warning(f'Port data {port} not formatted correctly. Expected "port|service|protocol|version". Ignoring...')
                continue
            if data[0] == "":
                log.warning(f'Missing port number. Expected "port|service|protocol|version". Ignoring...')
                continue
            if not utils.is_str_positive_integer(data[0].strip()):
                log.warning(f'Port number "{data[0].strip()}" from "{port}" is not a valid number. Must be a positive integer. Skipping...')
                continue
            
            port = {
                'number': data[0].strip(),
                'service': data[1].strip(),
                'protocol': data[2].strip(),
                'version': data[3].strip()
            }
            obj['ports'][data[0]] = port

    # evidence
    def add_evidence(self, header, obj, mapping, value):
        evidence = {
            'id': str(uuid4()),
            'caption': header.strip(),
            'code': value,
            'type': 'CodeSample',
            'assets': [],
        }
        self.set_value(obj, mapping['path'], evidence)
    #----------end functions----------


    def add_data_to_object(self, obj, obj_type, row):
        """
        Controller to add different types of data to different locations on an object.

        Objects can be clients, reports, findings, assets, affected assets, or vulnerabilities

        Adds all data from csv row that corresponds to the object type
        """
        for value in self.csv_headers_mapping.values():
            index = value['col_index']
            if index == None: # if CSV being processed doesn't have this column from the mapping, the index never got set
                continue
            header = value['header']
            data_mapping_key = self.get_mapping_key_from_header(header)
            if data_mapping_key == None:
                log.debug(f'CSV header "{header}" not mapped with a location key. Skipping {header}...')
                continue

            data_mapping = self.data_mapping.get(data_mapping_key)
            if data_mapping == None:
                log.warning(f'No Plextrac mapping for <{data_mapping_key}>, was it typed incorrectly? Ignoring...')
                continue

            # only loop through the field for hte correct obj type
            if data_mapping['object_type'] != obj_type:
                continue

            data_type = data_mapping['data_type']

            # skip blank values that would be discarded anyway, before validation,
            # so validated fields (dates, floats, etc.) do not log spurious errors
            raw_value = row[index]
            if not data_mapping['input_blanks'] and (raw_value == "" or raw_value is None):
                continue

            value = self.validate_value(header, data_mapping, raw_value)

            # determine whether to add blank values
            if data_mapping['input_blanks'] or (value != "" and value != None): 

                if data_type == "DETAIL":
                    self.add_detail(header, obj, data_mapping, value)
                elif data_type == "CUSTOM_FIELD":
                    self.add_label_value(header, obj, data_mapping, value)
                elif data_type == "KEY_CUSTOM_FIELD":
                    self.add_key_label_value(header, obj, data_mapping, value)
                elif data_type == "TAG":
                    self.add_tag(header, obj, data_mapping, value)
                elif data_type == "MULTI_TAG":
                    self.add_multi_tag(header, obj, data_mapping, value)
                elif data_type == "NARRATIVE":
                    self.add_label_text(header, obj, data_mapping, value)
                elif data_type == "CVE":
                    self.add_cve(header, obj, data_mapping, value)
                elif data_type == "CWE":
                    self.add_cwe(header, obj, data_mapping, value)
                elif data_type == "LIST":
                    self.add_list(header, obj, data_mapping, value)
                elif data_type == "PORTS":
                    self.add_port(header, obj, data_mapping, value)
                elif data_type == "EVIDENCE":
                    self.add_evidence(header, obj, data_mapping, value)


    def parser_row(self, row):
        """
        Parsers the csv row to determine which client and report the finding should be added to.

        Gets or creates client to import to
        Gets or creates report to import to
        Creates finding
        Creates asset
        """
        # query csv row for client specific info and create or choose client
        client_sid, client_name = self.handle_client(row)
        if client_sid == None:
            return

        # query csv row for report specific data and create or choose report
        report_sid, report_name = self.handle_report(row, client_sid)   
        if report_sid == None:
            return     
        
        # query csv row for finding specific data and create finding
        finding_sid, finding_name = self.handle_finding(row, client_sid, report_sid)
        if finding_sid == None:
            return

        self.handle_multi_asset(row, client_sid, finding_sid)
        log.debug(f'After MULTI asset call, asset list:')
        for asset in self.assets.values():
            log.debug(f'SID: {asset["sid"]} - Name: {asset["asset"]} - Dup num: {asset["dup_num"]} - OG SID: {asset["original_asset_sid"]}')

        # query csv row for asset specific data and create or choose asset
        asset_sid, asset_name = self.handle_asset(row, client_sid, finding_sid)
        log.debug(f'After SINGLE asset call, asset list:')
        for asset in self.assets.values():
            log.debug(f'SID: {asset["sid"]} - Name: {asset["asset"]} - Dup num: {asset["dup_num"]} - OG SID: {asset["original_asset_sid"]}')

        # if there was a header mapped to a single asset, handle the potential affected asset data for the single asset
        if finding_sid != None and asset_sid != None:
            self.handle_affected_asset(row, finding_sid, asset_sid)


    def parse_data(self) -> bool:
        """
        Top level parsing controller. Loops through loaded csv, gathers required data, calls function to process data.

        Determine where to look for finding name (needed to verify each row contains a finding)
        Loop through csv findings
        - Verify row contains finding
        - Call to process finding
        """
        # get index of 'name' obj in self.data_mapping - this will be the index to point us to the finding name column in the csv
        try:
            csv_finding_title_index = self.get_index_from_key("finding_title")
            if csv_finding_title_index == None:
                raise ValueError
        except ValueError:
            log.critical(f'Did not map "finding_title" key to any csv headers during temporary CSV creation. Cannot process file. Skipping...')
            return False

        log.info(f'---Beginning CSV parsing---')
        self.parser_progress = 0
        for row in self.csv_data:
            log.info(f'=======Parsing Finding {self.parser_progress+1}=======')

            # checking if current row contains a finding since the csv could have rows that extend beyond finding data
            if row[csv_finding_title_index] == "":
                log.warning(f'Row {self.parser_progress+2} in the CSV did not have a value for the finding_title. Skipping...')
                self.parser_progress += 1
                continue
            
            vuln_name = row[csv_finding_title_index]
            log.info(f'---{vuln_name}---')
            self.parser_row(row)

            self.parser_progress += 1
            log.info(f'=======End {vuln_name}=======')

            # if self.parser_progess >= 150:
            #     break

        # post parsing processing
        log.info(f'---Post parsing processing---')
        self.handle_finding_dup_names()
        return True


    def generate_ptrac_json_data(self) -> list:
        """
        Creates PTRAC JSON data for each report found while parsing.
        """        
        ptracs = []
        ptrac_template = {
            "report_info": {
                "doc_type": "report"
            },
            "flaws_array": [],
            "summary": {
                "ReportAssets": {},
                "ReportMedia": {}
            },
            "evidence": [],
            "client_info": {
                "doc_type": "client",
                "poc": "",
                "poc_email": "",
                "tenant_id": 0
            }
        }

        # creates and export a ptrac for each report parsed
        log.info(f'---Creating ptrac---')
        # clients
        for client in self.clients.values():
            client_info = deepcopy(client)
            client_info.pop("assets")
            client_info.pop("reports")
            client_info.pop("sid")
            client_info['doc_type'] = "client"
            client_info['tenant_id'] = 0

            # reports
            for report_sid in client['reports']:
                report_assets = {} # this list is created here, but needs to be populated when looping through the affected assets

                report = deepcopy(self.reports[report_sid])
                report_info = deepcopy(report)
                report_info.pop("findings")
                report_info.pop("sid")
                report_info.pop("client_sid")
                report_info['doc_type'] = "report"
                report_info['includeEvidence'] = False
                report_info['reportType'] = "default"

                ptrac = deepcopy(ptrac_template)
                ptrac['client_info'] = client_info
                ptrac['report_info'] = report_info
                ptrac['summary']['ReportMedia'] = deepcopy(self.report_media)

                # findings
                for finding_sid in report['findings']:
                    finding = deepcopy(self.findings[finding_sid])
                    finding_info = deepcopy(finding)
                    finding_info.pop("assets")
                    finding_info.pop("sid")
                    finding_info.pop("client_sid")
                    finding_info.pop("report_sid")
                    finding_info.pop("affected_asset_sid")

                    # when importing data from a ptrac a finding does not go through the normal finding validation checks that are run when a finding is created
                    # metadata
                    finding_info['flaw_id'] = utils.generate_flaw_id(finding_info['title'])
                    finding_info['id'] = finding_info['flaw_id']
                    finding_info['exhibits'] = []
                    finding_info['doc_type'] = "flaw"
                    finding_info['source'] = "plextrac"
                    finding_info['visibility'] = "published"
                    finding_info['doc_version'] = self.doc_version
                    # dates
                    if finding_info.get("createdAt") == None:
                        finding_info['createdAt'] = self.parser_time_milliseconds
                    if finding_info['status'] == "Closed":
                        if finding_info.get("closedAt") == None:
                            finding_info['closedAt'] = self.parser_time_milliseconds
                    else:
                        finding_info['closedAt'] = None
                    if finding_info.get("last_update") == None:
                        finding_info['last_update'] = self.parser_time_milliseconds
                    # sev
                    finding_info['sev'] = self.severities.index(finding_info['severity'])
                    # assignedTo
                    if finding_info.get("assignedTo") == None:
                        finding_info['assignedTo'] = None
                    # data
                    finding_info['data'] = [
                        finding_info['flaw_id'],
                        finding_info['severity'],
                        finding_info['title'],
                        finding_info['status'],
                        finding_info['last_update'],
                        finding_info['assignedTo'],
                        finding_info['createdAt'],
                        finding_info['closedAt'],
                        None,
                        None,
                        finding_info['visibility']
                    ]

                    # affected assets
                    for asset_sid in finding['assets']:
                        # get a copy of the asset, checking duplicates and getting the original asset
                        asset = deepcopy(self.assets[asset_sid])
                        asset_sid_str = f'{asset["sid"]}'
                        if asset['original_asset_sid'] != None:
                            og_asset = self.assets[asset['original_asset_sid']]
                            self.update_asset_list_fields(og_asset, asset)
                            asset = deepcopy(og_asset)
                            asset_sid_str = f'{asset["sid"]}'


                            # update ReportAssets og asset reference in ptrac


                            # update og asset for the future when added to ptrac as affected asset core
                            # update instances of og asset already saved in ptrac



                            # log.info(f'Found existing asset <{asset["asset"]}>')
                            # # purposely not making a copy we need to update original asset list fields with new entries
                            # og_asset = self.assets[asset['original_asset_sid']]
                            # # update og asset - OS, known IPs, tags, and ports
                            # utils.merge_sanitized_str_lists(og_asset['operating_system'], asset['operating_system'])
                            # utils.merge_sanitized_str_lists(og_asset['knownIps'], asset['knownIps'])
                            # utils.merge_sanitized_str_lists(og_asset['tags'], asset['tags'])
                            # for port_id, port_data in asset['ports'].items():
                            #     if port_id not in og_asset['ports']:
                            #         og_asset['ports'][port_id] = port_data
                            # # update asset that was previously created
                            # payload = deepcopy(og_asset)
                            # payload.pop("sid")
                            # payload.pop("client_sid")
                            # payload.pop("finding_sid")
                            # payload.pop("dup_num")
                            # payload.pop("is_multi")
                            # log.info(f'Updating client asset <{payload["asset"]}>')
                            # response = api._v1.assets.update_asset(auth.base_url, auth.get_auth_headers(), client_id, og_asset['asset_id'], payload)
                            # if response.json.get("message") != "success":
                            #     log.warning(f'Could not update asset in PT with additional data. Skipping')
                            # # update this duplicate asset to point to the same asset_id that as assigned by PT when the og asset was created
                            # asset['asset_id'] = og_asset.get('asset_id', None)
                            # continue

                        # create a copy for the ReportAssets that will be modified to match ptrac specifications
                        client_asset_info = deepcopy(asset)
                        client_asset_info.pop("sid")
                        client_asset_info.pop("client_sid")
                        client_asset_info.pop("finding_sid")
                        client_asset_info.pop("original_asset_sid")
                        client_asset_info.pop("dup_num")
                        client_asset_info.pop("is_multi")
                        # when the script creates assets through the api asset's ID is saved to the asset_id property on an asset in parsed asset list. used for later deduplication
                        # removing `asset_id` here instead of reworking the api creation section
                        # the second parameter of None prevents the .pop from throwing an error if the asset_id was never added due to failed creation attempt
                        client_asset_info.pop("asset_id", None)
                        client_asset_info['id'] = asset_sid_str
                        client_asset_info['parent_asset'] = None

                        if asset_sid_str not in list(report_assets.keys()):
                            # add client asset to ReportAssets
                            report_assets[asset_sid_str] = client_asset_info
                        else:
                            # update ReportAssets reference with possible additional data
                            existing_report_asset = report_assets[asset_sid_str]
                            self.update_asset_list_fields(existing_report_asset, client_asset_info)
                            # updates affected asset instances that were already saved to the ptrac with possible additional data
                            existing_ptrac_findings = ptrac['flaws_array']
                            findings_to_update = list(filter(lambda x: asset_sid_str in x['affected_assets'].keys(), existing_ptrac_findings))
                            for f in findings_to_update:
                                for asset_id, existing_affected_asset in f['affected_assets'].items():
                                    if asset_id == asset_sid_str:
                                        self.update_asset_list_fields(existing_affected_asset, client_asset_info, update_ports=False)
                        
                        # create a copy of the client asset and modify to create and add the affected asset following the ptrac schema
                        affected_asset_info = deepcopy(client_asset_info)
                        finding_info = self.add_asset_to_finding(finding_info, affected_asset_info, finding_sid, asset["sid"])

                        # update the client asset with open ports
                        # - the affected ported are stored on the affected asset on a finding record
                        # - these should be backfilled to the client asset's open ports list
                        asset_ports = report_assets.get(asset_sid_str, {}).get("ports")
                        if asset_ports != None:
                            for k, v in affected_asset_info['ports'].items():
                                if k not in asset_ports.keys():
                                    asset_ports[k] = v

                    ptrac['flaws_array'].append(finding_info)

                ptrac['summary']['ReportAssets'] = report_assets

                ptracs.append(ptrac)

        return ptracs
