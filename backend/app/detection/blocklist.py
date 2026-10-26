"""Synthetic threat-intel blocklist (documentation-range IPs only).

A real deployment would load this from a threat feed; the rule logic is the same.
"""

KNOWN_BAD_IPS: dict[str, str] = {
    "203.0.113.66": "Synthetic feed: credential-stuffing infrastructure",
    "203.0.113.99": "Synthetic feed: known scanner",
    "198.51.100.200": "Synthetic feed: botnet command and control",
    "192.0.2.250": "Synthetic feed: malware download host",
}
