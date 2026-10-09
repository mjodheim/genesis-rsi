"""Literal evidence consistency; causal explanations still require external tests."""
import json
from pathlib import Path
from typing import Mapping

from genesis.repair_bench import RepairBenchError, _production_target
from genesis.repair_branches import find_parent

EVIDENCE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["observed_signal", "previous_assessment", "facts", "explanation", "prediction"],
    "properties": {
        "observed_signal": {"type": "string"},
        "previous_assessment": {"type": "string", "enum": ["none", "signal_unchanged", "signal_changed"]},
        "explanation": {"type": "string", "maxLength": 1200},
        "prediction": {"type": "string", "maxLength": 600,
                       "description": "Why these edits should remove the observed signal; a changed signal alone is not success."},
        "facts": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["path", "line", "quote", "term", "relation"],
            "properties": {"path": {"type": "string"}, "line": {"type": "integer", "minimum": 1},
                "quote": {"type": "string", "maxLength": 2000}, "term": {"type": "string", "maxLength": 300},
                "relation": {"type": "string", "enum": ["present", "absent"]}}}},
    },
}


def signal(text):
    for line in str(text).splitlines():
        line = line.strip()
        if line and not line.startswith(('---', 'at ', '...')):
            return line[:1000]
    return '<no failure signal available>'


def observation(evidence, history):
    if history:
        candidate, verdict = history[-1]
        current = signal(verdict.get('feedback', ''))
        prior = (candidate.provenance or {}).get('causal_evidence')
        assessment = ('signal_unchanged' if prior['observed_signal'] == current else 'signal_changed') if prior else 'none'
        return dict(observed_signal=current, previous_assessment=assessment,
                    stage=verdict['stopped_at'], candidate_digest=candidate.digest)
    traces = evidence.get('traces') or []
    return dict(observed_signal=signal(traces[0].get('trace', '') if traces else ''),
                previous_assessment='none', stage='baseline', candidate_digest=None)


def context(evidence, history):
    return ('## Host evidence consistency record\n' + json.dumps(observation(evidence, history)) +
        '\nEvery candidate needs causal_evidence matching this observed_signal and previous_assessment. '
        'Quote 1-3 complete production source lines (without numbered prefixes; boundary spaces '
        'are optional, internal characters must match), with path, 1-based line, term and relation '
        'present/absent IN THE NORMALIZED SOURCE LINE. Quotes refer to the selected '
        'parent virtual tree, or original for parent="". Read declarations before making absence '
        'claims. Facts establish literal text only; do not infer an entire object graph from a line. '
        'Explain the mechanism and predict removal of the observed signal. signal_unchanged means '
        'the preceding prediction did not remove it; acknowledge that before proposing another cause. '
        'signal_changed is not proof of correctness. Keep the evidence concise.')


def check(root, evidence, history, parent_identity, record):
    """Return a concrete rejection or None, without writing files or grading a repair."""
    if not isinstance(record, Mapping):
        return 'causal_evidence must be an object'
    observed = observation(evidence, history)
    for key in ('observed_signal', 'previous_assessment'):
        if record.get(key) != observed[key]:
            return f'{key} contradicts host record: expected {observed[key]}'
    for key, limit in [('explanation', 1200), ('prediction', 600)]:
        value = record.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            return f'{key} must be nonempty and at most {limit} characters'
    facts = record.get('facts')
    if not isinstance(facts, list) or not 1 <= len(facts) <= 3:
        return 'require 1-3 quoted source facts'
    parent = find_parent(history, parent_identity) if parent_identity else None
    if not isinstance(parent_identity, str) or parent_identity and parent is None:
        return 'unknown source branch'
    virtual = {Path(path).as_posix(): text for path, text in parent.files} if parent else {}
    try:
        for fact in facts:
            if not isinstance(fact, Mapping):
                return 'source fact must be an object'
            target = _production_target(root, fact['path'], evidence['source_directory'], evidence['test_directory'])
            path = target.relative_to(root).as_posix()
            lines = virtual.get(path, target.read_text(encoding='utf-8', errors='replace')).splitlines()
            number, quote, term = fact['line'], fact['quote'], fact['term']
            if type(number) is not int or not 1 <= number <= len(lines):
                return 'source line outside file'
            if not isinstance(quote, str) or not quote.strip() or len(quote) > 2000 or quote.strip() != lines[number - 1].strip():
                return f'source quote does not match {path}:{number} in selected tree'
            if not isinstance(term, str) or not term.strip() or len(term) > 300:
                return 'source fact term must be nonempty and bounded'
            if fact.get('relation') not in ('present', 'absent'):
                return 'source fact relation must be present or absent'
            present = term in lines[number - 1].strip()
            if present != (fact['relation'] == 'present'):
                return f'source fact contradicts quoted line: term {term!r} is ' + ('present' if present else 'absent')
    except (RepairBenchError, ValueError, OSError, KeyError, TypeError):
        return 'source fact path or layout refused'
    return None
