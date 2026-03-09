from __future__ import annotations

import csv
import io
import json
from typing import Any


def _filtered_result(record: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    if not fields:
        return record
    return {field: record.get(field) for field in fields}


def render_json(payload: dict[str, Any], fields: list[str] | None = None) -> str:
    if fields and "results" in payload and isinstance(payload["results"], list):
        updated = dict(payload)
        updated["results"] = [_filtered_result(record, fields) for record in payload["results"]]
        payload = updated
    return json.dumps(payload, indent=2, sort_keys=False)


def render_jsonl(payload: dict[str, Any], fields: list[str] | None = None) -> str:
    results = payload.get("results")
    if not isinstance(results, list):
        return json.dumps(payload)
    meta = {key: value for key, value in payload.items() if key != "results"}
    lines = []
    for index, result in enumerate(results, start=1):
        row = dict(meta)
        row["result_index"] = index
        row.update(_filtered_result(result, fields))
        lines.append(json.dumps(row, sort_keys=False))
    return "\n".join(lines)


def render_csv(payload: dict[str, Any], fields: list[str] | None = None) -> str:
    results = payload.get("results")
    if not isinstance(results, list):
        rows = [payload]
    else:
        meta = {key: value for key, value in payload.items() if key != "results"}
        rows = []
        for result in results:
            row = dict(meta)
            row.update(_filtered_result(result, fields))
            rows.append(row)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().rstrip()


def render_text(payload: dict[str, Any], fields: list[str] | None = None, quiet: bool = False) -> str:
    lines: list[str] = []
    if not quiet:
        lines.append(payload.get("command", "mcfind").replace("-", " ").title())
        if payload.get("version_requested"):
            lines.append(
                f"Version: {payload.get('version_requested')} -> {payload.get('version_effective')}"
            )
        if payload.get("warnings"):
            for warning in payload["warnings"]:
                lines.append(f"Warning: {warning}")
    if payload.get("save"):
        save = payload["save"]
        lines.extend(
            [
                f'Save: {save.get("level_name")}',
                f'Seed: {save.get("seed")}',
                f'Spawn: {save.get("spawn", {}).get("x")}, {save.get("spawn", {}).get("z")}',
                f'Version: {save.get("version_name")}',
            ]
        )
    elif payload.get("profiles") is not None:
        for profile in payload["profiles"]:
            lines.append(
                f'{profile["name"]}: seed={profile.get("seed")} version={profile.get("version")} base={profile.get("base")}'
            )
    elif payload.get("region_versions") is not None:
        for index, entry in enumerate(payload["region_versions"], start=1):
            lines.append(
                f'{index}. ({entry["x1"]}, {entry["z1"]}) -> ({entry["x2"]}, {entry["z2"]}) = {entry["version"]}'
            )
    elif payload.get("info"):
        info = payload["info"]
        lines.append(f'Seed: {payload.get("seed")}')
        lines.append(f'Effective version: {payload.get("version_effective")}')
        lines.append("Supported structures:")
        for structure in info.get("supported_structures", []):
            lines.append(f"  - {structure}")
    results = payload.get("results")
    if isinstance(results, list):
        use_fields = fields or [
            "structure",
            "x",
            "z",
            "y",
            "distance_blocks",
            "bearing",
            "chunk_x",
            "chunk_z",
            "nether_equivalent_x",
            "nether_equivalent_z",
        ]
        for record in results:
            lines.append("")
            title = record.get("structure", "result").replace("_", " ").title()
            lines.append(title)
            for field in use_fields:
                if field in record:
                    label = field.replace("_", " ").title()
                    lines.append(f"{label}: {record.get(field)}")
            notes = record.get("notes") or []
            if notes:
                for note in notes:
                    lines.append(f"Note: {note}")
    if payload.get("route"):
        route = payload["route"]
        lines.append("")
        lines.append(f'Algorithm: {route.get("algorithm")}')
        lines.append(f'Total distance: {route.get("total_distance_blocks")}')
    if payload.get("explain"):
        explain = payload["explain"]
        lines.append("")
        lines.append("Explain")
        for value in explain.values():
            if isinstance(value, list):
                lines.extend(f"- {item}" for item in value)
            else:
                lines.append(f"- {value}")
    return "\n".join(lines).strip()


def render_payload(payload: dict[str, Any], fmt: str, fields: list[str] | None = None, quiet: bool = False) -> str:
    if fmt == "json":
        return render_json(payload, fields=fields)
    if fmt == "jsonl":
        return render_jsonl(payload, fields=fields)
    if fmt == "csv":
        return render_csv(payload, fields=fields)
    return render_text(payload, fields=fields, quiet=quiet)
