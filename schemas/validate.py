"""
Schema validator for EditIQ style profiles.

Deliberately dependency-free: implements only the subset of JSON Schema
(Draft 2020-12) actually used by schemas/style_profile.schema.json
(type, properties, additionalProperties, required, $ref/$defs, enum,
pattern, minimum/maximum/exclusiveMinimum/exclusiveMaximum, minLength,
minProperties, items). This avoids adding a hard runtime dependency on
the `jsonschema` package just to validate our own, fully-controlled
schema, while still catching the errors that matter (unknown fields,
missing required fields, bad types, bad color hex, bad ranges).

If the `jsonschema` package happens to be installed, it is not used —
this module is the single source of truth for validation in this repo
so behavior is identical everywhere it runs.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_SCHEMA_PATH = Path(__file__).parent / "style_profile.schema.json"

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}


class SchemaValidationError(ValueError):
    """Raised when a style profile fails validation. Carries all errors found."""

    def __init__(self, errors):
        self.errors = list(errors)
        message = "Style profile failed validation:\n  - " + "\n  - ".join(self.errors)
        super().__init__(message)


def _is_number(value):
    # bool is a subclass of int in Python; JSON booleans must not pass as numbers.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_type(value, expected_type, path):
    if expected_type == "number":
        if not _is_number(value):
            return [f"{path}: expected number, got {type(value).__name__}"]
        return []
    if expected_type == "integer":
        if not _is_number(value) or (isinstance(value, float) and not value.is_integer()):
            return [f"{path}: expected integer, got {type(value).__name__}"]
        return []

    py_type = _TYPE_MAP.get(expected_type)
    if py_type is None:
        return []
    if not isinstance(value, py_type):
        return [f"{path}: expected {expected_type}, got {type(value).__name__}"]
    return []


def _resolve_ref(ref, root):
    # Only local "#/$defs/<name>" refs are used in this schema.
    assert ref.startswith("#/$defs/"), f"Unsupported $ref: {ref}"
    name = ref.split("/")[-1]
    return root["$defs"][name]


def _validate_node(instance, schema, root, path):
    errors = []

    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)

    if "type" in schema:
        errors += _check_type(instance, schema["type"], path)
        if errors:
            return errors  # further checks would be noise once the type is wrong

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")

    if isinstance(instance, str):
        if "pattern" in schema and not re.match(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength {schema['minLength']}")

    if _is_number(instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is less than minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is greater than maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {instance} must be > {schema['exclusiveMinimum']}")
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: {instance} must be < {schema['exclusiveMaximum']}")

    if isinstance(instance, dict):
        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            errors.append(f"{path}: object has fewer than minProperties {schema['minProperties']}")

        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required property '{key}'")

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)

        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors += _validate_node(value, properties[key], root, child_path)
            elif isinstance(additional, dict):
                errors += _validate_node(value, additional, root, child_path)
            elif additional is False:
                errors.append(f"{path}: unexpected additional property '{key}'")
            # additional is True (or absent): anything goes, no further checks

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors += _validate_node(item, schema["items"], root, f"{path}[{index}]")

    return errors


def load_schema(schema_path=DEFAULT_SCHEMA_PATH):
    with open(schema_path, "r", encoding="utf-8") as file:
        return json.load(file)


def validate_style_profile(profile, schema_path=DEFAULT_SCHEMA_PATH):
    """
    Validate `profile` (a dict) against the style profile schema.

    Returns None on success. Raises SchemaValidationError (with a full
    list of every problem found, not just the first) on failure.
    """
    schema = load_schema(schema_path)
    errors = _validate_node(profile, schema, schema, "profile")
    if errors:
        raise SchemaValidationError(errors)


def validate_style_profile_file(path, schema_path=DEFAULT_SCHEMA_PATH):
    with open(path, "r", encoding="utf-8") as file:
        profile = json.load(file)
    validate_style_profile(profile, schema_path)
    return profile


def main():
    parser = argparse.ArgumentParser(description="Validate an EditIQ style profile JSON file.")
    parser.add_argument("profile", help="Path to style profile JSON to validate")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Path to schema JSON")
    args = parser.parse_args()

    try:
        validate_style_profile_file(args.profile, args.schema)
    except SchemaValidationError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Could not read/parse {args.profile}: {error}", file=sys.stderr)
        sys.exit(2)

    print(f"OK: {args.profile} is a valid style profile.")


if __name__ == "__main__":
    main()
