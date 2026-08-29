"""Semantic validation for EditIQ operations-based edit plans.

JSON Schema (schemas/edit_plan.schema.json, checked via schemas/validate.py's
generic dependency-free engine) catches structural problems: unknown
fields, wrong types, missing required fields for known def references.

It cannot catch:
- timestamps outside the media duration
- start >= end
- per-operation-type required fields (operations are validated generically
  as {"type": <enum>} at the JSON Schema level -- see the comment in
  schemas/edit_plan.schema.json's "operation" $def for why)
- overlaps that a given operation type does not permit
- basic temporal ordering

This module is a separate file from schemas/validate.py so the existing,
already-tested style-profile validator is not touched by Phase 1 work.
"""

from __future__ import annotations

from .validate import (
    DEFAULT_SCHEMA_PATH as _STYLE_PROFILE_SCHEMA_PATH,  # re-exported only for reference
    SchemaValidationError,
    _validate_node,
    load_schema,
)
from pathlib import Path

EDIT_PLAN_SCHEMA_PATH = Path(__file__).parent / "edit_plan.schema.json"

# type -> required fields beyond "type" itself, and whether it uses
# start/end (True) or a single instant "at" (False, e.g. transition).
_OPERATION_SPECS = {
    "cut": {"required": ["start", "end"], "interval": True},
    "caption": {"required": ["start", "end", "text"], "interval": True},
    "emphasis": {"required": ["start", "end", "word"], "interval": True},
    "zoom": {"required": ["start", "end"], "interval": True},
    "broll": {"required": ["start", "end", "query"], "interval": True},
    "transition": {"required": ["at", "style"], "interval": False},
}

# Operation types whose instances must NOT overlap each other. Types not
# listed here (e.g. "broll", which is only a suggestion overlay) may
# overlap freely.
_NO_SELF_OVERLAP_TYPES = {"cut", "caption", "zoom"}


def validate_edit_plan_schema(plan: dict, schema_path=EDIT_PLAN_SCHEMA_PATH) -> None:
    """Structural (JSON Schema) validation only. Raises SchemaValidationError."""

    schema = load_schema(schema_path)
    errors = _validate_node(plan, schema, schema, "plan")
    if errors:
        raise SchemaValidationError(errors)


def _check_operation_fields(op: dict, index: int) -> list:
    errors = []
    path = f"plan.operations[{index}]"
    op_type = op.get("type")
    if op_type not in _OPERATION_SPECS:
        errors.append(f"{path}: unknown or missing operation type {op_type!r}")
        return errors

    spec = _OPERATION_SPECS[op_type]
    for field in spec["required"]:
        if field not in op:
            errors.append(f"{path}: operation type '{op_type}' missing required field '{field}'")

    if spec["interval"] and "start" in op and "end" in op:
        start, end = op["start"], op["end"]
        if not isinstance(start, (int, float)) or isinstance(start, bool):
            errors.append(f"{path}: start must be a number")
        elif start < 0:
            errors.append(f"{path}: start ({start}) is negative")
        if not isinstance(end, (int, float)) or isinstance(end, bool):
            errors.append(f"{path}: end must be a number")
        elif isinstance(start, (int, float)) and end <= start:
            errors.append(f"{path}: end ({end}) must be greater than start ({start})")
    elif not spec["interval"] and "at" in op:
        at = op["at"]
        if not isinstance(at, (int, float)) or isinstance(at, bool):
            errors.append(f"{path}: at must be a number")
        elif at < 0:
            errors.append(f"{path}: at ({at}) is negative")

    return errors


def _check_media_bounds(op: dict, index: int, media_duration) -> list:
    if media_duration is None:
        return []
    errors = []
    path = f"plan.operations[{index}]"
    for field in ("start", "end", "at"):
        if field in op:
            value = op[field]
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value > media_duration:
                errors.append(
                    f"{path}: {field} ({value}) exceeds media duration ({media_duration})"
                )
    return errors


def _check_overlaps(operations: list) -> list:
    errors = []
    by_type = {}
    for i, op in enumerate(operations):
        op_type = op.get("type")
        if op_type in _NO_SELF_OVERLAP_TYPES and "start" in op and "end" in op:
            by_type.setdefault(op_type, []).append((op["start"], op["end"], i))

    for op_type, intervals in by_type.items():
        ordered = sorted(intervals, key=lambda t: t[0])
        for (s1, e1, i1), (s2, e2, i2) in zip(ordered, ordered[1:]):
            if s2 < e1:  # next starts before previous ends
                errors.append(
                    f"plan.operations: overlapping '{op_type}' operations at indices {i1} and {i2} "
                    f"({s1}-{e1} overlaps {s2}-{e2}); operation type '{op_type}' does not permit overlap"
                )
    return errors


def validate_edit_plan_semantics(plan: dict, media_duration=None) -> None:
    """Timestamp/required-field/overlap validation. Raises SchemaValidationError."""

    errors = []
    operations = plan.get("operations", [])
    if not isinstance(operations, list):
        raise SchemaValidationError(["plan.operations: expected a list"])

    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            errors.append(f"plan.operations[{i}]: expected an object")
            continue
        errors += _check_operation_fields(op, i)
        errors += _check_media_bounds(op, i, media_duration)

    errors += _check_overlaps([op for op in operations if isinstance(op, dict)])

    if errors:
        raise SchemaValidationError(errors)


def validate_edit_plan(plan: dict, media_duration=None, schema_path=EDIT_PLAN_SCHEMA_PATH) -> None:
    """Full validation: JSON Schema structure + semantic checks.

    Raises SchemaValidationError (from schemas.validate) listing every
    problem found, not just the first.
    """

    errors = []
    try:
        validate_edit_plan_schema(plan, schema_path)
    except SchemaValidationError as exc:
        errors += exc.errors

    try:
        validate_edit_plan_semantics(plan, media_duration)
    except SchemaValidationError as exc:
        errors += exc.errors

    if errors:
        raise SchemaValidationError(errors)
