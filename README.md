# JND Subjective Experiment GUI

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements.txt` selects a compatible `PySide6` automatically:

- Python 3.8 -> `PySide6==6.6.3.1`
- Python 3.9+ -> `PySide6==6.10.2`

## Run

```bash
.venv/bin/python main.py
```

Results are written under `Results/{subject_id}/{device}/{label_folder}/{recording_id}/`.

## Test

```bash
.venv/bin/python -m unittest discover -s tests -v
```
