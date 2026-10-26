"""Parse uploaded CSV / JSON / NDJSON logs into validated events.

Pure functions with no database or web imports, so they're fast to unit test.
A bad row is rejected with a reason; it never fails the whole file.
"""

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from app.ingest.schema import CANONICAL_FIELDS, FIELD_ALIASES, EventIn

Format = Literal["csv", "json"]
ALLOWED_EXTENSIONS = {".csv": "csv", ".json": "json", ".ndjson": "json", ".jsonl": "json"}
MAX_REJECTION_SAMPLES = 20


class ParseError(ValueError):
    """The file as a whole can't be processed (wrong type, unreadable, too many rows)."""


@dataclass
class ParsedRow:
    event: EventIn
    raw: dict[str, Any]


@dataclass
class ParseResult:
    format: Format
    rows: list[ParsedRow] = field(default_factory=list)
    rejected_count: int = 0
    rejection_samples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.rows) + self.rejected_count

    def reject(self, line: int, reason: str) -> None:
        self.rejected_count += 1
        if len(self.rejection_samples) < MAX_REJECTION_SAMPLES:
            self.rejection_samples.append({"line": line, "reason": reason})


def _extension(filename: str) -> str:
    name = filename.lower().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return "." + name.rsplit(".", 1)[-1] if "." in name else ""


def detect_format(filename: str, content: bytes) -> Format:
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ParseError("Unsupported file type. Upload a .csv, .json, or .ndjson file.")
    if b"\x00" in content[:8192]:
        raise ParseError("The file appears to be binary, not a text log.")
    declared: Format = ALLOWED_EXTENSIONS[ext]  # type: ignore[assignment]
    first = content.lstrip(b"\xef\xbb\xbf \t\r\n")[:1]
    looks_json = first in (b"[", b"{")
    # The extension must agree with the content; don't trust either alone.
    if declared == "json" and not looks_json:
        raise ParseError("File has a JSON extension but doesn't contain JSON.")
    if declared == "csv" and looks_json:
        raise ParseError("File has a .csv extension but contains JSON.")
    return declared


def _canonicalize(record: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in record.items():
        if not isinstance(key, str):
            continue
        k = key.strip().lower()
        k = FIELD_ALIASES.get(k, k)
        if k in CANONICAL_FIELDS and k not in out:
            out[k] = value
    return out


def _reason(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"])
    msg = err["msg"].removeprefix("Value error, ")
    return f"{loc}: {msg}" if loc else msg


def _validate(result: ParseResult, line: int, record: object) -> None:
    if not isinstance(record, dict):
        result.reject(line, "row is not an object")
        return
    try:
        event = EventIn.model_validate(_canonicalize(record))
    except ValidationError as exc:
        result.reject(line, _reason(exc))
        return
    # Keep the original row (bounded) for auditability.
    raw = {str(k)[:64]: (v if not isinstance(v, str) else v[:1000]) for k, v in record.items()}
    result.rows.append(ParsedRow(event=event, raw=raw))


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError("The file must be UTF-8 encoded text.") from exc


def _check_row_limit(count: int, max_rows: int) -> None:
    if count > max_rows:
        raise ParseError(f"The file has more than {max_rows:,} rows. Split it and upload again.")


def parse_log(filename: str, content: bytes, *, max_rows: int) -> ParseResult:
    fmt = detect_format(filename, content)
    text = _decode(content)
    result = ParseResult(format=fmt)

    if fmt == "csv":
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ParseError("The CSV file is empty or has no header row.")
        headers = {
            FIELD_ALIASES.get(h.strip().lower(), h.strip().lower()) for h in reader.fieldnames
        }
        missing = {"timestamp", "category", "action", "outcome", "src_ip"} - headers
        if missing:
            raise ParseError(
                f"CSV header is missing required columns: {', '.join(sorted(missing))}"
            )
        for i, row in enumerate(reader, start=2):  # line 1 is the header
            _check_row_limit(i - 1, max_rows)
            _validate(result, i, row)
        return result

    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            records = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ParseError(f"Invalid JSON: {exc.msg} (line {exc.lineno})") from exc
        if not isinstance(records, list):
            raise ParseError("JSON must be an array of event objects.")
        _check_row_limit(len(records), max_rows)
        for i, record in enumerate(records, start=1):
            _validate(result, i, record)
        return result

    # Newline-delimited JSON: one object per line.
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        _check_row_limit(result.total + 1, max_rows)
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            result.reject(i, "line is not valid JSON")
            continue
        _validate(result, i, record)
    return result
