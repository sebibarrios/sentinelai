import json

import pytest

from app.ingest.parser import ParseError, parse_log

HEADER = "timestamp,category,action,outcome,src_ip,username,dst_ip,dst_port\n"


def csv_bytes(*rows: str) -> bytes:
    return (HEADER + "\n".join(rows) + "\n").encode()


def test_csv_happy_path_normalizes_values():
    r = parse_log(
        "auth.csv",
        csv_bytes("2026-10-20T03:00:00+02:00,AUTH,Login,FAILURE,203.0.113.5,bob,,"),
        max_rows=10,
    )
    assert r.format == "csv" and r.total == 1 and r.rejected_count == 0
    e = r.rows[0].event
    assert (e.category, e.action, e.outcome) == ("auth", "login", "failure")
    assert e.timestamp.isoformat() == "2026-10-20T01:00:00+00:00"  # converted to UTC
    assert e.dst_ip is None and e.dst_port is None  # blanks become null


def test_bad_rows_are_rejected_with_reasons_not_fatal():
    r = parse_log(
        "auth.csv",
        csv_bytes(
            "2026-10-20T03:00:00Z,auth,login,success,10.0.0.1,alice,,",
            "2026-10-20T03:00:00Z,auth,login,success,999.0.0.1,alice,,",
            "not-a-date,auth,login,success,10.0.0.1,alice,,",
            "2026-10-20T03:00:00Z,auth,login,success,10.0.0.1,,,",
            "2026-10-20T03:00:00Z,network,connection,success,10.0.0.1,,10.0.0.2,22",
            "2026-10-20T03:00:00Z,network,connection,denied,10.0.0.1,,10.0.0.2,70000",
        ),
        max_rows=10,
    )
    assert len(r.rows) == 1 and r.rejected_count == 5
    reasons = {s["line"]: s["reason"] for s in r.rejection_samples}
    assert "not a valid IP" in reasons[3]
    assert reasons[4].startswith("timestamp")
    assert "require a username" in reasons[5]
    assert "allowed or denied" in reasons[6]
    assert reasons[7].startswith("dst_port")


def test_csv_column_aliases_are_understood():
    data = (
        b"@timestamp,type,action,result,source_ip,user\n"
        b"2026-10-20T03:00:00Z,auth,login,success,10.0.0.9,eve\n"
    )
    r = parse_log("export.csv", data, max_rows=10)
    assert r.rows[0].event.username == "eve" and r.rows[0].event.src_ip == "10.0.0.9"


def test_missing_required_columns_fails_whole_file():
    with pytest.raises(ParseError, match="missing required columns: outcome"):
        parse_log("x.csv", b"timestamp,category,action,src_ip\n", max_rows=10)


def test_json_array_and_ndjson():
    event = {
        "timestamp": "2026-10-20T03:00:00Z",
        "category": "network",
        "action": "connection",
        "outcome": "denied",
        "src_ip": "192.0.2.1",
        "dst_ip": "10.0.0.2",
        "dst_port": 22,
        "extra_vendor_field": "kept in raw",
    }
    arr = parse_log("x.json", json.dumps([event, event]).encode(), max_rows=10)
    assert len(arr.rows) == 2
    assert arr.rows[0].raw["extra_vendor_field"] == "kept in raw"

    nd = (json.dumps(event) + "\n{broken\n\n" + json.dumps(event) + "\n").encode()
    r = parse_log("x.ndjson", nd, max_rows=10)
    assert len(r.rows) == 2 and r.rejection_samples == [
        {"line": 2, "reason": "line is not valid JSON"}
    ]


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("evil.exe", b"MZ...", "Unsupported file type"),
        ("logs.csv.php", b"<?php", "Unsupported file type"),
        ("logs.csv", b"\x00\x01\x02binary", "binary"),
        ("logs.json", b"timestamp,category\n", "doesn't contain JSON"),
        ("logs.csv", b'[{"a": 1}]', "contains JSON"),
        ("logs.json", b'[{"truncated": 1', "Invalid JSON"),
        ("logs.csv", "timestamp\n".encode("utf-16"), "binary"),
    ],
)
def test_unsafe_or_mismatched_files_are_refused(name, content, message):
    with pytest.raises(ParseError, match=message):
        parse_log(name, content, max_rows=10)


def test_row_limit_enforced():
    rows = ["2026-10-20T03:00:00Z,auth,login,success,10.0.0.1,a,," for _ in range(6)]
    with pytest.raises(ParseError, match="more than 5 rows"):
        parse_log("big.csv", csv_bytes(*rows), max_rows=5)


def test_path_in_filename_is_ignored():
    r = parse_log(
        "../../etc/passwd.csv",
        csv_bytes("2026-10-20T03:00:00Z,auth,login,success,10.0.0.1,a,,"),
        max_rows=5,
    )
    assert r.total == 1  # only the extension matters; the name is never used as a path
