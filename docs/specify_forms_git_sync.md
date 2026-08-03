# Specify forms git sync

This repository tracks Specify 7 form/view XML and provides scripts to round-trip
definitions between a Specify instance and git.

Entry point: **`specli form`** — `pull` / `status` / `push` (wraps `export_specify_forms.py` and `import_specify_forms.py`).

Credentials are read from `.env` in the repository root (see `example.env`).

## Setup

```bash
./install.sh
source .venv/bin/activate
cp example.env .env
# edit .env with your Specify URL and credentials
```

Run commands from the repository root (`specli` on PATH, or `./bin/specli`).

## Required env vars

- `SPECIFY7_URL`
- `SPECIFY7_USER`
- `SPECIFY7_PASSWORD`
- `SPECIFY7_COLLECTION` (optional; defaults to first available collection if unset)

## Commands

| Command | Direction |
|---------|-----------|
| `pull` | Specify → git |
| `status` | dry-run push |
| `push` | git → Specify |

Legacy aliases: `export` / `plan` / `import` (import still needs `--apply` to write).

## Pull forms from Specify to git

Full pull (recommended baseline for git history):

```bash
specli form pull --clean --output-dir forms
```

XML-focused pull (skip per-form manifests):

```bash
specli form pull --clean --no-manifests --output-dir forms
```

Behavior:

- Scans Specify views via `/context/views.json`.
- Writes one directory per `table/view_name`.
- Writes baseline XML as `default.xml` (prefers `common` where available).
- Writes non-baseline variants under `overrides/<level>/<viewset-name>.xml`.
- Always writes top-level `summary.json`.

## Status and push forms from git to Specify

`status` is always dry-run.  
`push` writes unless `--dry-run` is set.

Dry-run:

```bash
specli form status --forms-dir forms
```

Apply changes (discipline viewset example):

```bash
specli form status --forms-dir forms_all \
  --viewset-name "Karplaner - standard" --source-mode overrides

specli form push --forms-dir forms_all \
  --viewset-name "Karplaner - standard" --source-mode overrides
```

Apply with backup of current remote viewset XML:

```bash
specli form push \
  --forms-dir forms \
  --backup tmp/viewset-backup.xml
```

Seed a DB viewset with all forms from defaults (IaC bootstrap):

```bash
specli form status --forms-dir forms --source-mode defaults --create-missing-views
specli form push --forms-dir forms --source-mode defaults --create-missing-views --backup tmp/viewset-before-seed.xml
```

Push behavior:

- Logs into Specify with collection context.
- Targets one viewset (auto-discovered from `/context/views.json`, or `--viewset-name`).
- Loads current remote XML from `spappresourcedata`.
- Replaces matching `<view>` and `<viewdef>` entries from local XML files.
- Can create missing `<view>` entries when `--create-missing-views` is enabled.
- PUTs updated `spappresourcedata` only when content changed.

Use `status` with `--verbose-missing` to print unmapped files (when not using `--create-missing-views`):

```bash
specli form status --forms-dir forms --verbose-missing
```

## On-disk layout

```
forms/<table>/<view_name>/
  default.xml
  overrides/<level>/<viewset-slug>.xml
  manifest.json          # optional
summary.json             # pull metadata
```

## Suggested git workflow

1. Pull full baseline once:
   - `specli form pull --clean --no-manifests --output-dir forms`
2. (Optional, one-time) seed DB viewset from defaults:
   - `specli form push --forms-dir forms --source-mode defaults --create-missing-views --backup tmp/viewset-before-seed.xml`
3. Commit all XML files (large initial commit).
4. For each admin edit cycle:
   - Re-pull to `forms`
   - Review git diff
   - Commit XML changes
5. Push local XML back when needed:
   - Run `status` first
   - Then run `push`

## Schema configuration (same repo)

Field visibility and labels are **not** in form XML — they live in discipline
schema config. See [specify_schema_git_sync.md](specify_schema_git_sync.md).

When you add a field to a form, also set `"ishidden": false` for that field in
`schema/<slug>/schema.en.json` (or export schema after enabling it in UI).

Pick lists referenced by schema or form XML are **not** created by specli — run the
matching `scripts/ensure_*_picklist.py` script (with `--apply`) before schema/form
push. Example: `ensure_determination_addendum_picklist.py` for
`Determination.addendum` / `DeterminationAddendum`.

UI field formatters (`format` on schema fields) are managed by
[`specli formatter`](specify_formatters_git_sync.md) — push those **before**
schema push when adding new formatter names.

## Direct script usage

You can also call the underlying scripts:

- `scripts/export_specify_forms.py`
- `scripts/import_specify_forms.py`
- `scripts/export_specify_schema.py`
- `scripts/import_specify_schema.py`
- `scripts/import_specify_formatters.py`
- `scripts/import_specify_weblinks.py`

See their module docstrings for flags (same as `specli …` subcommands).
