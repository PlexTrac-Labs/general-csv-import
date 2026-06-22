# Location Key List

## Notes

Findings will only be imported to new clients and reports. The names of these clients and reports are designated by mapping the client_name and report_name keys.If the client_name or report_name key is not used, a client named `Custom CSV Import <DATE>` and a report named `Report`, will be created and all findings will be imported to this report.

Keys can only be used for a single header unless otherwise noted below. If a key, that is not noted to be able to use multiple times, is added to multiple headers it will override data.

Finding mappings include merge metadata used by parser merge strategies. `SCALAR` fields must match for `user_defined_fields` merges, `RICH_TEXT` fields can be concatenated when matched findings differ, and `LIST` fields are combined and deduplicated.

---

## Available locations to map data to in Plextrac

---

## Clients

| Key | Description |
|---|---|
| client_name | Client name |
| client_poc | Client POC |
| client_poc_email | Client POC Email |
| client_description | Client description |
| client_tag | A single tag value will be added as a client tag. You can use this key for multiple headers. See tag format schema. For a comma delimited list of tags see `client_multi_tag` below |
| client_multi_tag | List of comma delimited tags to be added as client tags. See tag format schema. |
| client_custom_field | Client custom field value. The label will be the column header. You can use this key for multiple headers. |

---

## Reports

| Key | Description |
|---|---|
| report_name | Report name |
| report_start_date | Report start date |
| report_end_date | Report end date |
| report_tag | A single tag value will be added as a report tag. You can use this key for multiple headers. See tag format schema. For a comma delimited list of tags see `report_multi_tag` below |
| report_multi_tag | List of comma delimited tags to be added as finding tags. See tag format schema. |
| report_custom_field | Report custom field value. The csv column header will be used as the label. You can use this key for multiple headers. |
| report_narrative | Report narrative text. The csv column header will be used as the report narrative title. You can use this key for multiple headers. |

---

## Findings

| Key | Description |
|---|---|
| finding_assigned_to | Finding assigned to field. This should be a user email. If there is a Plextrac user with the same email, the finding will be assigned to them and show up on their dashboard. |
| finding_created_at | Date the finding was created or first observed on |
| finding_closed_at | Date the finding was closed on. If this value is added to a finding, the finding status will automatically be marked as Closed. |
| finding_last_updated_at | Date the finding was last updated. If omitted, PTRAC generation uses the parser run timestamp. |
| finding_description | Finding description field |
| finding_recommendations | Finding recommendations field |
| finding_references | Finding references field. You can use this key for multiple headers. Each value will be appended after a newline. |
| finding_severity | Finding severity. Accepted values `Critical`, `High`, `Medium`, `Low`, `Informational`. Any other value will be set to `Informational` |
| finding_status | Finding status. Accepted values `Open`, `In Process`, `Closed`. Any other values will be set to `Open` |
| finding_sub_status | Finding sub status |
| finding_tag | A single tag value will be added as a finding tag. You can use this key for multiple headers. See tag format schema. For a comma delimited list of tags see `finding_multi_tag` below |
| finding_multi_tag | List of comma delimited tags to be added as finding tags. See tag format schema. |
| finding_title | Finding title. This is the only required key, if not added to any columns the script will not run. |
| finding_custom_field | Finding custom field value. The csv column header will be used as the label. You can use this key for multiple headers. |
| finding_cvss4_overall | Overall CVSS 4.0 score. Must be a float. |
| finding_cvss4_vector | CVSS 4.0 vector. Must be a full vector string starting with the `CVSS:4.0/` prefix and include all 11 base metrics, e.g. `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N`. The full string (including prefix) is stored. |
| finding_cvss3_1_overall | Overall CVSS 3.1 score. Must be a float. |
| finding_cvss3_1_vector | CVSS 3.x vector. Accepts a `CVSS:3.0/...` string, a `CVSS:3.1/...` string, or a bare metric string `AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N`. The version prefix is stripped before storage. |
| finding_cvss3_vector | Legacy CVSS 3 vector string. |
| finding_cvss3_value | Legacy CVSS 3 numeric score value. |
| finding_cvss3_label | Legacy CVSS 3 score label. |
| finding_cvss2_vector | CVSS 2 vector string. |
| finding_cvss2_value | CVSS 2 numeric score value. |
| finding_cvss2_label | CVSS 2 score label. |
| finding_cvss_general_vector | General CVSS vector string. |
| finding_cvss_general_value | General CVSS numeric score value. |
| finding_cvss_general_label | General CVSS score label. |
| finding_cve | List of comma delimited cveIds in the format `CVE-1337-1234` |
| finding_cwe | List of comma delimited CWE Weakness IDs in the format `123` |

---

## Assets

| Key | Description |
|---|---|
| asset_multi_name | List of comma delimited asset names. Any assets created with this key will NOT have any other asset data added to them. The following asset keys will only be added to the single asset under the `asset_name` column. |
| asset_name | A single asset name. For a comma delimited list of asset names see `asset_multi_name` above |
| asset_custom_field | Asset custom field value, added to the Client Asset specified with the `asset_name` key. The csv column header is used as the field label. You can use this key for multiple headers. |
| asset_type | Asset type. Accepted values `Workstation`, `Server`, `Network Device`, `Application`, `General`. Any other value will be ignored and the asset will not have a type set. |
| asset_criticality | Asset criticality. Accepted values `Critical`, `High`, `Medium`, `Low`, `Informational`. Any other value will be ignored and the asset will not have a criticality set. |
| asset_system_owner | Asset system owner |
| asset_data_owner | Asset data owner |
| asset_hostname | Asset hostname |
| asset_operating_systems | List of comma delimited operating systems |
| asset_dns_name | Asset hostname |
| asset_host_fqdn | Asset host fqdn |
| asset_host_rdns | Asset host rdns |
| asset_mac_address | Asset MAC Address |
| asset_physical_location | Asset Physical Location |
| asset_netbios_name | Asset NetBios Name |
| asset_total_cves | Asset Total CVEs. Value must be a positive integer |
| asset_pci_compliance_status | Asset PCI Compliance Status. Accepted values `Pass`, `pass`, `yes`, `y`, `Fail`, `fail`, `no`, `n`. Any other value will be ignored and the asset will not have the PCI Status set. |
| asset_description | Asset Description |
| asset_known_ips | List of comma delimited known IP addresses. Each IP must be a valid IPv4 or IPv6 address. Addresses CANNOT have ports appended to them. |
| asset_tag | A single tag value will be added as an asset tag. You can use this key for multiple headers. See tag format schema.For a comma delimited list of tags see `asset_multi_tag` below |
| asset_multi_tag | List of comma delimited tags to be added as asset tags. See tag format schema. |
| asset_ports | List of comma delimited ports to be added as unaffected ports to the Client Asset specified with the `asset_name` key. Each port needs to contain a number, service, protocol and version. Single Port: `port\|service\|protocol\|version` Multiple Ports: `port\|service\|protocol\|version, port\|service\|protocol\|version` You could also add this key to multiple columns each with a single port. You can omit the service, protocol, or version by leaving it blank, but each port must still have 3 separator ( \| ) chars. Examples: Port Number Only: `port\|\|\|`, Port Number and Protocol: `port\|\|protocol\|` |
| asset_port_number | A single port number to be added as an unaffected port to the Client Asset specified with the asset_name key. This will get combined with the values form the keys `asset_port_service`, `asset_port_protocol`, and `asset_port_version` to create a single port object to add to the Client Asset. Value must be a positive integer |
| asset_port_service | A single port service to be added as an unaffected port to the Client Asset specified with the asset_name key. This will get combined with the values form the keys `asset_port_number`, `asset_port_protocol`, and `asset_port_version` to create a single port object to add to the Client Asset. |
| asset_port_protocol | A single port protocol to be added as an unaffected port to the Client Asset specified with the asset_name key. This will get combined with the values form the keys `asset_port_number`, `asset_port_service`, and `asset_port_version` to create a single port object to add to the Client Asset. |
| asset_port_version | A single port version to be added as an unaffected port to the Client Asset specified with the asset_name key. This will get combined with the values form the keys `asset_port_number`, `asset_port_protocol`, and `asset_port_protocol` to create a single port object to add to the Client Asset. |

---

## Affected Assets

| Key | Description |
|---|---|
| affected_asset_status | Asset status. Accepted values `Open`, `In Process`, `Closed`. Any other values will be set to `Open` |
| affected_asset_sub_status | Asset sub status |
| affected_asset_ports | List of comma delimited ports to be added as affected ports to the Affected Asset specified with the `asset_name` key. Each port needs to contain a number, service, protocol and version. Single Port: `port\|service\|protocol\|version` Multiple Ports: `port\|service\|protocol\|version, port\|service\|protocol\|version` You could also add this key to multiple columns each with a single port. You can omit the service, protocol, or version by leaving it blank, but each port must still have 3 separator ( \| ) chars. Examples: Port Number Only: `port\|\|\|` Port Number and Protocol: `port\|\|protocol\|` |
| affected_asset_evidence | Evidence to attach to the affected asset. The CSV column header becomes the evidence caption and the cell value becomes the code sample. You can use this key for multiple headers. |
| affected_asset_port_number | A single port number to be added as an affected port to the Affected Asset specified with the asset_name key. This will get combined with the values form the keys `affected_asset_port_service`, `affected_asset_port_protocol`, and `affected_asset_port_version` to create a single port object to add to the Affected Asset. Value must be a positive integer |
| affected_asset_port_service | A single port service to be added as an affected port to the Affected Asset specified with the asset_name key. This will get combined with the values form the keys `affected_asset_port_number`, `affected_asset_port_protocol`, and `affected_asset_port_version` to create a single port object to add to the Affected Asset. |
| affected_asset_port_protocol | A single port protocol to be added as an affected port to the Affected Asset specified with the asset_name key. This will get combined with the values form the keys `affected_asset_port_number`, `affected_asset_port_service`, and `affected_asset_port_version` to create a single port object to add to the Affected Asset. |
| affected_asset_port_version | A single port version to be added as an affected port to the Affected Asset specified with the asset_name key. This will get combined with the values form the keys `affected_asset_port_number`, `affected_asset_port_protocol`, and `affected_asset_port_protocol` to create a single port object to add to the Affected Asset. |
| affected_asset_location_url | Affected asset location url |
