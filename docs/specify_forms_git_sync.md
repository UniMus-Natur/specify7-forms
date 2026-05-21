# Specify forms git sync

This repository tracks Specify 7 form/view XML and provides scripts to round-trip
definitions between a Specify instance and git.

Entry point: **`specli form`** (wraps `export_specify_forms.py` and `import_specify_forms.py`).

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

- `export` — pull forms from Specify to files
- `plan` — dry-run sync plan from files to Specify
- `import` — apply files to Specify (only with `--apply`)

## Export forms from Specify to git

Full export (recommended baseline for git history):

```bash
specli form export --clean --output-dir forms
```

XML-focused export (skip per-form manifests):

```bash
specli form export --clean --no-manifests --output-dir forms
```

Behavior:

- Scans Specify views via `/context/views.json`.
- Writes one directory per `table/view_name`.
- Writes baseline XML as `default.xml` (prefers `common` where available).
- Writes non-baseline variants under `overrides/<level>/<viewset-name>.xml`.
- Always writes top-level `summary.json`.

## Plan and import forms from git to Specify

`plan` is always dry-run.  
`import` is dry-run unless `--apply` is provided.

Dry-run:

```bash
specli form plan --forms-dir forms
```

Apply changes (discipline viewset example):

```bash
specli form plan --forms-dir forms_all \
  --viewset-name "Karplaner - standard" --source-mode overrides

specli form import --forms-dir forms_all \
  --viewset-name "Karplaner - standard" --source-mode overrides --apply
```

Apply with backup of current remote viewset XML:

```bash
specli form import \
  --forms-dir forms \
  --backup tmp/viewset-backup.xml \
  --apply
```

Seed a DB viewset with all forms from defaults (IaC bootstrap):

```bash
specli form plan --forms-dir forms --source-mode defaults --create-missing-views
specli form import --forms-dir forms --source-mode defaults --create-missing-views --backup tmp/viewset-before-seed.xml --apply
```

Import behavior:

- Logs into Specify with collection context.
- Targets one viewset (auto-discovered from `/context/views.json`, or `--viewset-name`).
- Loads current remote XML from `spappresourcedata`.
- Replaces matching `<view>` and `<viewdef>` entries from local XML files.
- Can create missing `<view>` entries when `--create-missing-views` is enabled.
- PUTs updated `spappresourcedata` only when `--apply` is set and content changed.

Use `plan` with `--verbose-missing` to print unmapped files (when not using `--create-missing-views`):

```bash
specli form plan --forms-dir forms --verbose-missing
```

## On-disk layout

```
forms/<table>/<view_name>/
  default.xml
  overrides/<level>/<viewset-slug>.xml
  manifest.json          # optional
summary.json             # export metadata
```

## Suggested git workflow

1. Export full baseline once:
   - `specli form export --clean --no-manifests --output-dir forms`
2. (Optional, one-time) seed DB viewset from defaults:
   - `specli form import --forms-dir forms --source-mode defaults --create-missing-views --backup tmp/viewset-before-seed.xml --apply`
3. Commit all XML files (large initial commit).
4. For each admin edit cycle:
   - Re-export to `forms`
   - Review git diff
   - Commit XML changes
5. Push local XML back when needed:
   - Run `plan` first
   - Then run `import --apply`

## Schema configuration (same repo)

Field visibility and labels are **not** in form XML — they live in discipline
schema config. See [specify_schema_git_sync.md](specify_schema_git_sync.md).

When you add a field to a form, also set `"ishidden": false` for that field in
`schema/<slug>/schema.en.json` (or export schema after enabling it in UI).

## Direct script usage

You can also call the underlying scripts:

- `scripts/export_specify_forms.py`
- `scripts/import_specify_forms.py`
- `scripts/export_specify_schema.py`
- `scripts/import_specify_schema.py`

See their module docstrings for flags (same as `specli form` / `specli schema` subcommands).
