"""Conservative generic candidate for stateful streaming Iterable reuse.

Pattern:
- public Iterator<T> iterator() returns a NEW anonymous Iterator<T>
- hasNext() caches a next element by advancing a shared producer
- a second iterator() call discards that prefetched element
- no existing iterator cache in the source

Propose reusing a single iterator object to preserve lookahead state.
This is a hypothesis, not a guaranteed improvement to Iterable semantics:
it may be inappropriate for a rewindable collection. The operator must
remain opt-in and independently fully tested.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.java_sibling_guard_mutations import _mask_literals_and_comments, _closing_brace
from genesis.trust_root import digest_of

SCHEMA = "genesis-java-streaming-iterator-state-preservation-v1"
METHOD = re.compile(
    r"\bpublic\s+Iterator<(?P<type>[A-Za-z_$][\w$]*)>\s+iterator\s*\(\s*\)\s*\{"
)
ANON = re.compile(
    r"\breturn\s+new\s+Iterator<(?P<type>[A-Za-z_$][\w$]*)>\s*\(\s*\)\s*\{"
)
LOOKAHEAD = re.compile(
    r"\b(?:this\.)?[A-Za-z_$][\w$]*\s*=\s*(?:this\.)?[A-Za-z_$][\w$]*\s*\("
)


def _candidate(relative: str, source: str) -> list[dict[str, Any]]:
    masked = _mask_literals_and_comments(source)
    if 'implements' not in masked or 'Iterable<' not in masked:
        return []
    results = []
    for method in METHOD.finditer(masked):
        m_close = _closing_brace(masked, method.end()-1)
        if m_close is None:
            continue
        method_body = masked[method.end():m_close]
        anon = ANON.search(method_body)
        if not anon or anon['type']!=method['type']:
            continue
        anon_start = method.end()+anon.start()
        open_brace = method.end()+anon.end()-1
        close_brace = _closing_brace(masked,open_brace)
        if close_brace is None or close_brace>=m_close:
            continue
        semi = close_brace+1
        while semi < m_close and masked[semi].isspace():
            semi += 1
        if semi >= m_close or masked[semi]!=';':
            continue
        anon_body = masked[open_brace+1:close_brace]
        has_next = re.search(r"\bboolean\s+hasNext\s*\(\s*\)\s*\{",anon_body)
        if has_next is None:
            continue
        body_start=open_brace+1+has_next.end()
        body_end=_closing_brace(masked,body_start-1)
        if body_end is None or body_end>close_brace:
            continue
        has_next_body=masked[body_start:body_end]
        if not LOOKAHEAD.search(has_next_body):
            continue
        if 'return' not in has_next_body or '== null' not in has_next_body:
            continue
        # Avoid emitting a field that shadows pre-existing identifiers.
        base_name='genesisStreamingIterator'
        field=base_name
        count=1
        while re.search(r"\b"+re.escape(field)+r"\b",masked):
            count+=1
            field=base_name+str(count)
        m_type=method['type']
        # Replace the return new prefix, add singleton-lifetime memoization,
        # then insert the field immediately before the method declaration.
        updated = source
        changes=[
            (semi+1,semi+1,
                "\n        }\n        return this."+field+";\n"),
            (anon_start,anon_start+len("return"),
                "if (this."+field+" == null) {\n"
                "            this."+field+" ="),
        ]
        # The original text between return and new begins with ' new'.
        # Replacing exactly 'return' yields this.cache = new Iterator<T>() {...}.
        for a,b,repl in sorted(changes,key=lambda item:-item[0]):
            updated=updated[:a]+repl+updated[b:]
        declaration_start=source.rfind("\n",0,method.start())+1
        annotation_start=declaration_start
        # Java annotations belong to the method: a new field cannot be
        # inserted BETWEEN @Override and its annotated method.
        while annotation_start>0:
            previous_end=annotation_start-1
            previous_start=source.rfind("\n",0,previous_end)+1
            line=source[previous_start:previous_end].strip()
            if not line.startswith("@"):
                break
            annotation_start=previous_start
        indent=source[declaration_start:method.start()]
        insert=annotation_start
        updated=updated[:insert]+(
            indent+"private transient Iterator<"+m_type+"> "+field+";\n\n"
        )+updated[insert:]
        if updated==source:
            continue
        preimage=hashlib.sha256(source.encode()).hexdigest()
        payload={
            "schema":SCHEMA,
            "path":relative,
            "operator":"java_reuse_stateful_stream_iterator",
            "expected_sha256":preimage,
            "changed_sha256":hashlib.sha256(updated.encode()).hexdigest(),
            "method_start":method.start(),
            "type_arity":1,
        }
        digest=digest_of(payload)
        results.append({
            "id":"java-stream-iterator-"+digest[:14],
            "candidate_digest":digest,
            "path":relative,
            "operator":"java_reuse_stateful_stream_iterator",
            "expected_sha256":preimage,
            "content_utf8":updated,
            "detail":{
                "mode":"stateful_iterator_prefetch_reuse",
                "site_count":1,
                "source_line":source.count("\n",0,insert)+1,
                "pattern_origin":"buggy_source_iterator_structure",
            },
            "external_model_calls":0,
        })
    return results


def generate(root: str | Path, *,
             include_prefixes: Sequence[str]=(),
             max_candidates: int=64) -> dict[str, Any]:
    if not 1<=max_candidates<=500:
        raise ValueError('max_candidates must be in [1,500]')
    base=Path(root).resolve(strict=True)
    selectors=tuple(str(x).strip("/") for x in include_prefixes if str(x).strip("/"))
    generated=[]
    for file in sorted(base.rglob("*.java")):
        path=file.relative_to(base).as_posix()
        if (not file.is_file() or file.stat().st_size>512_000
            or any(part in ("test","tests","target","build",".git")
                   for part in file.relative_to(base).parts[:-1])):
            continue
        if selectors and not any(path==s or path.startswith(s+"/") for s in selectors):
            continue
        generated.extend(_candidate(path,file.read_text(encoding="utf-8")))
        if len(generated)>=max_candidates:
            generated=generated[:max_candidates]
            break
    body={"schema":SCHEMA,"candidate_count":len(generated),
          "candidates":generated,"external_model_calls":0}
    return {**body,"result_digest":digest_of(body)}
