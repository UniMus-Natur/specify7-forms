#!/usr/bin/env python3
"""Merge git-tracked WebLink definitions into Specify App Resource ``WebLinks``.

Reads ``resources/weblinks/*.xml`` (vector fragments with ``weblinkdef`` children),
fetches the discipline-scoped ``WebLinks`` resource via the public API, and merges
any missing definitions by ``name``.  Creates the app resource when missing.

Dry-run by default. Use ``--apply`` to write.

Usage:
  specli weblink status
  specli weblink push
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from _specify_client import (
    disable_insecure_request_warnings,
    iter_list_endpoint,
    load_env_from_repo,
    login,
    post_json,
    put_json,
    require_env,
    resolve_specify_user_id,
    resource_pk,
    strip_meta_for_put,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBLINKS_DIR = REPO_ROOT / "resources" / "weblinks"


def _load_defs_from_path(path: Path, *, asset_collection: str) -> list[ET.Element]:
    raw = path.read_text(encoding="utf-8")
    raw = raw.replace("{{ASSET_COLLECTION}}", asset_collection)
    root = ET.fromstring(raw)
    if root.tag == "weblinkdef":
        return [root]
    return list(root.findall("weblinkdef"))


def _load_extension_defs(asset_collection: str) -> list[tuple[str, ET.Element]]:
    if not WEBLINKS_DIR.exists():
        sys.exit(f"WebLinks directory not found: {WEBLINKS_DIR}")
    out: list[tuple[str, ET.Element]] = []
    for path in sorted(WEBLINKS_DIR.glob("*.xml")):
        if path.name == "defaults.xml":
            continue
        for element in _load_defs_from_path(path, asset_collection=asset_collection):
            name_el = element.find("name")
            name = (name_el.text or "").strip() if name_el is not None else ""
            if not name:
                sys.exit(f"{path}: weblinkdef missing <name>")
            out.append((name, element))
    return out


def _bootstrap_xml(asset_collection: str) -> str:
    defaults_path = WEBLINKS_DIR / "defaults.xml"
    if defaults_path.exists():
        root = ET.fromstring(defaults_path.read_text(encoding="utf-8"))
        if root.tag != "vector":
            sys.exit(f"{defaults_path}: expected <vector> root")
    else:
        root = ET.Element("vector")

    present = _existing_names(root)
    for name, element in _load_extension_defs(asset_collection):
        if name in present:
            continue
        root.append(element)
        present.add(name)

    merged = ET.tostring(root, encoding="unicode")
    if not merged.startswith("<?xml"):
        merged = '<?xml version="1.0" encoding="UTF-8"?>\n' + merged
    return merged


def _existing_names(root: ET.Element) -> set[str]:
    names: set[str] = set()
    for element in root.findall("weblinkdef"):
        name_el = element.find("name")
        if name_el is not None and name_el.text:
            names.add(name_el.text.strip())
    return names


def _merge_weblinks(
    existing_xml: str,
    extensions: list[tuple[str, ET.Element]],
) -> tuple[str, list[str]]:
    root = ET.fromstring(existing_xml)
    if root.tag != "vector":
        sys.exit(f"Expected <vector> root in WebLinks XML, got <{root.tag}>")
    present = _existing_names(root)
    added: list[str] = []
    for name, element in extensions:
        if name in present:
            continue
        root.append(element)
        present.add(name)
        added.append(name)
    if not added:
        return existing_xml, added
    merged = ET.tostring(root, encoding="unicode")
    if not merged.startswith("<?xml"):
        merged = '<?xml version="1.0" encoding="UTF-8"?>\n' + merged
    return merged, added


def _find_discipline_resource_dir(session, base: str, collection_id: int) -> int:
    rows = iter_list_endpoint(
        session,
        base,
        f"/api/specify/spappresourcedir/?collection={collection_id}&limit=100",
    )
    for row in rows:
        if not row.get("ispersonal") and not row.get("usertype"):
            dir_id = resource_pk(row.get("resource_uri"))
            if dir_id is not None:
                return dir_id
    for row in rows:
        if not row.get("ispersonal"):
            dir_id = resource_pk(row.get("resource_uri"))
            if dir_id is not None:
                return dir_id
    sys.exit("No discipline SpAppResourceDir found for this collection")


def _create_weblinks_resource(
    session,
    base: str,
    *,
    collection_id: int,
    specify_user_id: int,
    merged_xml: str,
) -> tuple[int, int]:
    dir_id = _find_discipline_resource_dir(session, base, collection_id)
    resource = post_json(
        session,
        base,
        "/api/specify/spappresource/",
        {
            "name": "WebLinks",
            "mimetype": "text/xml",
            "metadata": "Web Link Formats",
            "description": "Web Link Formats",
            "level": 3,
            "spappresourcedir": f"/api/specify/spappresourcedir/{dir_id}/",
            "specifyuser": f"/api/specify/specifyuser/{int(specify_user_id)}/",
        },
    )
    resource_id = resource_pk(resource.get("resource_uri"))
    if resource_id is None:
        sys.exit("Could not parse created spappresource id")

    data_row = post_json(
        session,
        base,
        "/api/specify/spappresourcedata/",
        {
            "data": merged_xml,
            "spappresource": f"/api/specify/spappresource/{resource_id}/",
        },
    )
    data_id = resource_pk(data_row.get("resource_uri"))
    if data_id is None:
        sys.exit("Could not parse created spappresourcedata id")
    return resource_id, data_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Import WebLink definitions into Specify")
    parser.add_argument(
        "--collection",
        default=os.getenv("SPECIFY7_COLLECTION") or None,
        help="Specify collection to log into (default: SPECIFY7_COLLECTION env, else first available)",
    )
    parser.add_argument(
        "--asset-collection",
        default=os.getenv("SPECIFY7_ASSET_COLLECTION", "NHM-karplanter"),
        help="Asset-server collection name for preview URLs (default: SPECIFY7_ASSET_COLLECTION or NHM-karplanter)",
    )
    parser.add_argument("--apply", action="store_true", help="Write merged WebLinks to Specify")
    args = parser.parse_args()

    load_env_from_repo()
    disable_insecure_request_warnings()

    base = require_env("SPECIFY7_URL").rstrip("/")
    user = require_env("SPECIFY7_USER")
    password = require_env("SPECIFY7_PASSWORD")
    collection_name = (args.collection or "").strip() or None
    asset_collection = str(args.asset_collection).strip()

    extensions = _load_extension_defs(asset_collection)
    if not extensions:
        print("[import_specify_weblinks] no extension definitions found", file=sys.stderr)
        return

    session, selected_collection, col_id = login(
        base,
        user,
        password,
        collection_name,
        log_prefix="import_specify_weblinks",
    )
    specify_user_id = resolve_specify_user_id(session, base, user)

    res = session.get(f"{base}/context/app_resource/?name=WebLinks", timeout=60)
    created = False

    if res.status_code == 404:
        merged_xml = _bootstrap_xml(asset_collection)
        added = [name for name, _ in extensions if name in _existing_names(ET.fromstring(merged_xml))]
        print(
            f"[import_specify_weblinks] WebLinks missing — would create with: {', '.join(added)} "
            f"(collection={selected_collection})",
            file=sys.stderr,
        )
        if not args.apply:
            print("[import_specify_weblinks] dry-run — pass --apply to write", file=sys.stderr)
            return
        resource_id, data_id = _create_weblinks_resource(
            session,
            base,
            collection_id=col_id,
            specify_user_id=specify_user_id,
            merged_xml=merged_xml,
        )
        print(
            f"[import_specify_weblinks] created WebLinks spappresource={resource_id} "
            f"spappresourcedata={data_id}; definitions: {', '.join(added)}",
            file=sys.stderr,
        )
        return

    if res.status_code != 200:
        sys.exit(f"GET WebLinks failed ({res.status_code}): {res.text[:500]}")

    resource_id = res.headers.get("X-Record-ID")
    if not resource_id:
        sys.exit("WebLinks response missing X-Record-ID header")

    merged_xml, added = _merge_weblinks(res.text, extensions)

    if not added:
        print(
            f"[import_specify_weblinks] nothing to do — all {len(extensions)} definition(s) already present "
            f"(collection={selected_collection})",
            file=sys.stderr,
        )
        return

    print(
        f"[import_specify_weblinks] would add: {', '.join(added)} (collection={selected_collection})",
        file=sys.stderr,
    )

    if not args.apply:
        print("[import_specify_weblinks] dry-run — pass --apply to write", file=sys.stderr)
        return

    data_rows = iter_list_endpoint(
        session,
        base,
        f"/api/specify/spappresourcedata/?spappresource={int(resource_id)}&limit=1",
    )
    if not data_rows:
        sys.exit(f"No spappresourcedata row for spappresource id={resource_id}")
    data_row = data_rows[0]
    data_id = resource_pk(data_row.get("resource_uri"))
    if data_id is None:
        sys.exit("Could not parse spappresourcedata id")

    body = strip_meta_for_put(data_row)
    body["data"] = merged_xml
    put_json(session, base, f"/api/specify/spappresourcedata/{data_id}/", body)
    print(
        f"[import_specify_weblinks] updated WebLinks (spappresourcedata id={data_id}); added: {', '.join(added)}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
