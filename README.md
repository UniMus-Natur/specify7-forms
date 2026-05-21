# specify7-forms

Git-tracked Specify 7 form/view XML for Unimus deployment, with scripts to export
from and import into a running Specify instance.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp example.env .env
# edit .env

python3 scripts/form.py export --clean --no-manifests --output-dir forms
python3 scripts/form.py plan --forms-dir forms
python3 scripts/form.py import --forms-dir forms --apply
```

## Documentation

See [docs/specify_forms_git_sync.md](docs/specify_forms_git_sync.md) for the full
workflow, env vars, layout, and examples (including discipline viewsets such as
`Karplaner - standard`).

## Repository layout

| Path | Purpose |
|------|---------|
| `scripts/form.py` | CLI entry point (`export`, `plan`, `import`) |
| `scripts/export_specify_forms.py` | Export from Specify API to files |
| `scripts/import_specify_forms.py` | Import from files into DB viewset (`spappresourcedata`) |
| `forms/` / `forms_all/` | Exported form XML trees |
| `example.env` | Template for `.env` credentials |
