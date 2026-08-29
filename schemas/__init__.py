"""EditIQ schema validators.

Empty on purpose -- this file's only job is to make `schemas/` a proper
Python package so `schemas/edit_plan_validate.py` can do
`from .validate import ...` and callers can do
`from schemas.edit_plan_validate import validate_edit_plan`.

Added as part of Phase 1; nothing in the pre-existing schemas/validate.py
or schemas/*.json files was touched by this addition.
"""
