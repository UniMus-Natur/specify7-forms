#!/usr/bin/env python3
"""Ensure the ``DeterminationAddendum`` pick list exists with MUSIT-aligned values.

Specli schema/form sync references this pick list but does not create it.
Run once per Specify collection before importing schema/forms that use it.

Usage (from specify7-forms root):
  python scripts/ensure_determination_addendum_picklist.py
  python scripts/ensure_determination_addendum_picklist.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _specify_client import (
    disable_insecure_request_warnings,
    iter_list_endpoint,
    load_env_from_repo,
    login,
    post_json,
    require_env,
)


def _load_values() -> list[str]:
    path = Path(__file__).resolve().parent.parent / "resources/picklists/determination_addendum.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    values = data.get("values") or []
    if not values:
        sys.exit(f"No values in {path}")
    return [str(v) for v in values]


def _find_picklist(session, base: str, name: str) -> dict | None:
    for row in iter_list_endpoint(session, base, "/api/specify/picklist/?limit=500"):
        if (row.get("name") or "").strip() == name:
            return row
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure DeterminationAddendum pick list exists.")
    parser.add_argument("--collection", default=None, help="Specify collection name")
    parser.add_argument("--apply", action="store_true", help="Create pick list / missing items")
    args = parser.parse_args()

    load_env_from_repo()
    disable_insecure_request_warnings()

    base = require_env("SPECIFY7_URL").rstrip("/")
    user = require_env("SPECIFY7_USER")
    password = require_env("SPECIFY7_PASSWORD")
    collection = args.collection or os.getenv("SPECIFY7_COLLECTION")

    session, collection_name, collection_id = login(
        base,
        user,
        password,
        collection,
        log_prefix="ensure_determination_addendum_picklist",
    )

    picklist_name = "DeterminationAddendum"
    desired_values = _load_values()
    existing = _find_picklist(session, base, picklist_name)

    if existing is None:
        print(f"[plan] pick list {picklist_name!r} missing — would create with {len(desired_values)} items")
        if not args.apply:
            return 0
        created = post_json(
            session,
            base,
            "/api/specify/picklist/",
            {
                "name": picklist_name,
                "collection": f"/api/specify/collection/{collection_id}/",
                "issystem": False,
                "readonly": False,
                "type": 0,
            },
        )
        picklist_id = int(created["id"])
        print(f"[apply] created pick list id={picklist_id}")
    else:
        picklist_id = int(existing["id"])
        print(f"[ok] pick list {picklist_name!r} exists (id={picklist_id})")

    existing_items = iter_list_endpoint(
        session,
        base,
        f"/api/specify/picklistitem/?picklist={picklist_id}&limit=500",
    )
    have = {(row.get("value") or row.get("title") or "").strip() for row in existing_items}
    missing = [v for v in desired_values if v not in have]

    if not missing:
        print(f"[ok] all {len(desired_values)} values present for collection={collection_name}")
        return 0

    print(f"[plan] missing values: {', '.join(missing)}")
    if not args.apply:
        return 0

    for ordinal, value in enumerate(desired_values):
        if value in have:
            continue
        post_json(
            session,
            base,
            "/api/specify/picklistitem/",
            {
                "picklist": f"/api/specify/picklist/{picklist_id}/",
                "title": value,
                "value": value,
                "ordinal": ordinal,
            },
        )
        print(f"[apply] added pick list item {value!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
