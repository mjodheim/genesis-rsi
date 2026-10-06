"""Materialized, runtime-independent L9-OE1 v2 qualification population."""
from __future__ import annotations
import json
from pathlib import Path
from experiment.rsi_v25.commitments import ROOT, digest_bytes
from experiment.rsi_v35 import native

PATH = ROOT / "experiment/l9_oe1_v2/POPULATION.json"
QUALIFICATION_SEED = 86753117
EPOCHS = 12
TASKS_PER_EPOCH = 16
BLOCK = 3
TRANSFER_TARGETS = 8

def _load():
    value=json.loads(PATH.read_text(encoding="utf-8"))
    if set(value)!=set(native.DOMAINS):
        raise ValueError("V2 population domains changed")
    return value

def validate_task(task):
    required={"task_id","epoch","domain","slots","target","inputs"}
    if type(task) is not dict or set(task)!=required:
        raise ValueError("Invalid materialized V2 task")
    if task["domain"] not in native.DOMAINS or not 0<=task["epoch"]<EPOCHS:
        raise ValueError("Invalid V2 domain/epoch")
    if len(task["target"])!=task["slots"] or any(type(x) is not int or not 1<=x<=4 for x in task["target"]):
        raise ValueError("Invalid V2 target")
    if type(task["inputs"]) is not list or len(task["inputs"])!=4:
        raise ValueError("Invalid V2 contexts")
    return True

def stream(domain):
    rows=_load()[domain]
    if len(rows)!=EPOCHS*TASKS_PER_EPOCH:
        raise ValueError("V2 stream length changed")
    for task in rows: validate_task(task)
    if [r["epoch"] for r in rows]!=sorted(r["epoch"] for r in rows):
        raise ValueError("V2 tasks reordered")
    return rows

def population_file_sha256():
    return digest_bytes(PATH.read_bytes())

def population():
    return _load()
