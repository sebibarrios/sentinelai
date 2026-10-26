"""Write the synthetic sample logs in ../sample-data (fixed dates, so files are stable).

Usage:  python -m scripts.generate_sample
"""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from app.ingest.synthetic import generate

OUT = Path(__file__).resolve().parents[2] / "sample-data"
END = datetime(2026, 10, 20, 23, 59, tzinfo=UTC)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    log = generate(end=END, seed=7)

    with (OUT / "auth_network_24h.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(log.rows[0]))
        writer.writeheader()
        writer.writerows(log.rows)

    # Same scenarios, different seed and format, to show JSON support.
    other = generate(end=END, seed=21)
    with (OUT / "auth_network_24h.ndjson").open("w") as f:
        for row in other.rows:
            f.write(json.dumps({k: v for k, v in row.items() if v not in ("", None)}) + "\n")

    # A small file with deliberate mistakes, to show per-row validation.
    bad = [
        "timestamp,category,action,outcome,src_ip,username,dst_ip,dst_port",
        "2026-10-20T09:00:00Z,auth,login,success,10.20.0.2,anguyen,,",
        "2026-10-20T09:01:00Z,auth,login,success,999.10.10.10,anguyen,,",
        "yesterday,auth,login,failure,10.20.0.3,spatel,,",
        "2026-10-20T09:02:00Z,auth,login,failure,10.20.0.3,,,",
        "2026-10-20T09:03:00Z,network,connection,denied,192.0.2.10,,10.0.1.10,99999",
        "2026-10-20T09:04:00Z,network,connection,allowed,10.20.0.4,,10.0.1.10,443",
    ]
    (OUT / "with_errors.csv").write_text("\n".join(bad) + "\n")

    print(f"wrote {len(log.rows)} + {len(other.rows)} events and an error sample to {OUT}")
    for s in log.scenarios:
        print(" -", s)


if __name__ == "__main__":
    main()
