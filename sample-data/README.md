# Sample data

Synthetic security logs for trying SentinelAI. Everything is invented: IPs are in documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or private ranges, and usernames are made up.

| File | Format | What it contains |
|---|---|---|
| `auth_network_24h.csv` | CSV | ~1,500 events over 24 hours: normal employee logins and network traffic, plus five planted attack scenarios |
| `auth_network_24h.ndjson` | NDJSON | The same scenarios with a different random seed, one JSON object per line |
| `with_errors.csv` | CSV | Six rows, four deliberately invalid, to show per-row validation |

Each file with planted scenarios should produce eight alerts, one per detection rule:

- Brute force against the `admin` account from 203.0.113.45 (AUTH-001)
- A password spray from 198.51.100.23 (AUTH-002) that ends in a successful `jdoe` login (AUTH-003) from an IP `jdoe` hasn't used before (AUTH-005)
- A port scan of 10.0.4.12 from 192.0.2.77 (NET-001), mostly blocked (NET-002)
- An off-hours login by `svc_backup` (AUTH-004)
- Traffic from blocklisted IP 203.0.113.66 (IOC-001)

Both files plant the same scenarios at the same times (only the background noise differs), so whichever you upload second creates no new alerts: alerts are deduplicated across uploads. They're dated 2026-10-20, so use the 30-day dashboard range, or regenerate them:

```bash
cd backend && python -m scripts.generate_sample
```
