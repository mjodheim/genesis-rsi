"""Pluggable language reasoning tools around a language-independent V2 core.

Adapters are trusted, explicitly registered Python objects. The registry
NEVER imports user-provided module names or executes stored source strings.
A detached plugin cannot execute its proposals; signed hypothesis records
remain serializable in memory for later reattachment.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from genesis.trust_root import digest_of
from genesis.v2 import semantic_dsl

SCHEMA = "genesis-v21-semantic-language-module-record-v1"


class SemanticRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class LanguageModule:
    module_id: str
    language: str
    extensions: tuple[str, ...]
    propose: Callable[..., dict[str, Any]]
    compile: Callable[..., dict[str, Any]]
    version: str = "1"

    def manifest(self) -> dict[str, Any]:
        record={
            "module_id":self.module_id,
            "language":self.language,
            "extensions":list(self.extensions),
            "version":self.version,
            "can_modify_evaluator":False,
            "can_promote_itself":False,
        }
        return {**record,"module_digest":digest_of(record)}


class SemanticRegistry:
    def __init__(self):
        self._by_id: dict[str, LanguageModule] = {}

    def attach(self, module: LanguageModule) -> None:
        if not isinstance(module, LanguageModule):
            raise SemanticRegistryError("explicit trusted language adapter required")
        if not module.module_id or module.module_id in self._by_id:
            raise SemanticRegistryError("module must be unique and named")
        if not module.extensions or any(
            not x.startswith(".") or len(x)>12 for x in module.extensions
        ):
            raise SemanticRegistryError("invalid language extension contract")
        if any(
            set(other.extensions) & set(module.extensions)
            for other in self._by_id.values()
        ):
            raise SemanticRegistryError("ambiguous file extension route")
        self._by_id[module.module_id]=module

    def detach(self, module_id: str) -> None:
        if module_id not in self._by_id:
            raise SemanticRegistryError("module not attached")
        del self._by_id[module_id]

    def manifests(self) -> list[dict[str, Any]]:
        return [module.manifest() for _,module in sorted(self._by_id.items())]

    def _module_for_path(self, relative: str) -> LanguageModule:
        if not isinstance(relative,str):
            raise SemanticRegistryError("relative path must be text")
        candidates=[
            mod for mod in self._by_id.values()
            if Path(relative).suffix in mod.extensions
        ]
        if len(candidates)!=1:
            raise SemanticRegistryError("no unique installed semantic adapter for source")
        return candidates[0]

    def propose(
        self,
        root: str | Path,
        relative: str,
        *,
        max_hypotheses: int=16,
    ) -> dict[str, Any]:
        module=self._module_for_path(relative)
        response=module.propose(root,relative,max_hypotheses=max_hypotheses)
        if response.get("no_evaluator_feedback_seen") is not True:
            raise SemanticRegistryError("module proposal used evaluator information")
        manifest=module.manifest()
        payload={
            "schema":SCHEMA,
            "module_manifest":manifest,
            "source_path":relative,
            "proposal_response":response,
            "does_not_include_human_fix":True,
            "module_can_be_unloaded_without_losing_record":True,
        }
        return {**payload,"record_digest":digest_of(payload)}

    def compile(self,root: str | Path,record: Mapping[str, Any],hypothesis_index:int) -> dict[str, Any]:
        raw=dict(record)
        checksum=raw.pop("record_digest",None)
        if checksum!=digest_of(raw) or raw.get("schema")!=SCHEMA:
            raise SemanticRegistryError("stored module record checksum invalid")
        if type(hypothesis_index) is not int or hypothesis_index<0:
            raise SemanticRegistryError("invalid hypothesis index")
        module_id=record["module_manifest"]["module_id"]
        module=self._by_id.get(module_id)
        if module is None:
            raise SemanticRegistryError("module is detached; evidence is retained but cannot execute")
        if record["module_manifest"]!=module.manifest():
            raise SemanticRegistryError("module contract changed since proposal was saved")
        path=record["source_path"]
        if self._module_for_path(path).module_id!=module_id:
            raise SemanticRegistryError("source routed to another language adapter")
        candidates=record["proposal_response"]["proposals"]
        if hypothesis_index>=len(candidates):
            raise SemanticRegistryError("hypothesis index outside sealed proposal record")
        return module.compile(root,candidates[hypothesis_index])


def java_module() -> LanguageModule:
    return LanguageModule(
        module_id="v21.java.contract-inference",
        language="java",
        extensions=(".java",),
        propose=semantic_dsl.propose,
        compile=semantic_dsl.compile_hypothesis,
        version="1",
    )


def default_registry() -> SemanticRegistry:
    registry=SemanticRegistry()
    registry.attach(java_module())
    return registry
