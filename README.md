# JND Subjective Experiment GUI

This implementation follows `jnd_ui_implementer_spec.md` as the only source of truth.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python main.py
```

Results are written under `Results/{subject_id}/{device}/{label_folder}/{recording_id}/`.

## Test

```bash
.venv/bin/python -m unittest discover -s tests -v
```
