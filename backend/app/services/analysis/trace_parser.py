"""Playwright trace.zip parser (Phase 6, M2).

Reads the ``trace.trace`` NDJSON stream inside a trace archive and reduces it to
structured ``actions`` / ``network`` / ``console`` / ``snapshots`` lists for the
Trace viewer (and Phase 7 failure context). Unknown event types are skipped and
malformed lines tolerated so a Playwright version drift does not break ingestion.

The parser is adapted to the Python Playwright trace NDJSON contract (deviation
D3): ``before``/``after`` action events pair on ``callId``; ``request``/``response``
network events pair on ``sha1``; snapshot references are kept, HTML is not.
"""

import io
import json
import zipfile

ACTION_LIMIT = 2000
NETWORK_LIMIT = 1000
CONSOLE_LIMIT = 1000


class TraceParseError(Exception):
    """Raised when a trace archive cannot be parsed."""


def _num(value):
    return value if isinstance(value, (int, float)) else None


def _duration_ms(start, end) -> int | None:
    start, end = _num(start), _num(end)
    if start is None or end is None:
        return None
    return int(end - start)


def parse_trace(zip_bytes: bytes) -> dict:
    """Parse a trace.zip into {actions, network, console, snapshots, truncated}."""
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            if "trace.trace" not in zf.namelist():
                raise TraceParseError("trace.trace not found in archive")
            text = zf.read("trace.trace").decode("utf-8", errors="replace")
    except TraceParseError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface as TraceParseError
        raise TraceParseError(f"invalid trace archive: {exc}") from exc

    befores: dict[str, dict] = {}
    afters: dict[str, dict] = {}
    requests: dict[str, dict] = {}
    responses: dict[str, dict] = {}
    console: list[dict] = []
    snapshots: list[str] = []
    truncated = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate malformed / non-JSON lines

        etype = event.get("type")
        if etype == "before":
            if event.get("callId") is not None:
                befores[event["callId"]] = event
        elif etype == "after":
            if event.get("callId") is not None:
                afters[event["callId"]] = event
        elif etype == "console":
            if len(console) >= CONSOLE_LIMIT:
                truncated = True
                continue
            console.append({
                "type": event.get("messageType") or event.get("type", ""),
                "text": event.get("text", ""),
            })
        elif etype == "request":
            if event.get("sha1") is not None:
                requests[event["sha1"]] = event
        elif etype == "response":
            if event.get("sha1") is not None:
                responses[event["sha1"]] = event
        # unknown event type -> skip

    actions: list[dict] = []
    for call_id, before in befores.items():
        if len(actions) >= ACTION_LIMIT:
            truncated = True
            break
        after = afters.get(call_id)
        api_name = before.get("apiName")
        if not api_name:
            cls = before.get("class", "")
            meth = before.get("method", "")
            api_name = f"{cls}.{meth}".strip(".") or call_id or ""
        error = None
        if after and after.get("error"):
            err = after["error"]
            error = err.get("message") if isinstance(err, dict) else str(err)
        actions.append({
            "api_name": api_name,
            "error": error,
            "start_time": _num(before.get("startTime")),
            "end_time": _num(after.get("endTime")) if after else None,
            "duration_ms": _duration_ms(
                before.get("startTime"), after.get("endTime") if after else None
            ),
        })
        for key in ("beforeSnapshot", "afterSnapshot"):
            value = before.get(key) or (after.get(key) if after else None)
            if value and value not in snapshots:
                snapshots.append(value)

    network: list[dict] = []
    for sha1, request in requests.items():
        if len(network) >= NETWORK_LIMIT:
            truncated = True
            break
        response = responses.get(sha1)
        network.append({
            "url": request.get("url", ""),
            "method": request.get("method", ""),
            "status": (response or {}).get("status", request.get("status")),
            "resource_type": request.get("resourceType")
            or request.get("resource_type", ""),
            "duration_ms": _duration_ms(request.get("startTime"), request.get("endTime")),
        })

    return {
        "actions": actions,
        "network": network,
        "console": console,
        "snapshots": snapshots,
        "truncated": truncated,
    }
