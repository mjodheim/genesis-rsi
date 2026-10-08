"""Detach language module without losing versioned learned source hypotheses."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from genesis.v2.semantic_registry import (
    LanguageModule, SemanticRegistry, SemanticRegistryError, default_registry,
    java_module,
)
from tests.test_v21_semantic_dsl import fixture


class SemanticModuleTests(unittest.TestCase):
    def test_attach_detach_restore_and_preserve_hypothesis_evidence(self):
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/"Signal.java").write_text(fixture())
            registry=default_registry()
            artifact=registry.propose(root,"Signal.java")
            path=root/"retained_experience.json"
            path.write_text(json.dumps(artifact,indent=2,sort_keys=True))
            before=registry.compile(root,artifact,0)
            registry.detach("v21.java.contract-inference")
            self.assertEqual(registry.manifests(),[])
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(SemanticRegistryError,"detached"):
                registry.compile(root,json.loads(path.read_text()),0)
            registry.attach(java_module())
            after=registry.compile(root,json.loads(path.read_text()),0)
            self.assertEqual(before["candidate_sha256"],after["candidate_sha256"])
            self.assertIn("if (corrupt || peer.corrupt)",after["content_utf8"])

    def test_unknown_suffix_ambiguous_route_and_forged_record(self):
        registry=default_registry()
        with self.assertRaisesRegex(SemanticRegistryError,"no unique"):
            registry.propose(Path("/tmp"),"fake.cs")
        with self.assertRaisesRegex(SemanticRegistryError,"unique"):
            registry.attach(java_module())
        with self.assertRaisesRegex(SemanticRegistryError,"ambiguous"):
            registry.attach(LanguageModule(
                module_id="other.java",language="other",extensions=(".java",),
                propose=java_module().propose,compile=java_module().compile,
            ))
        with TemporaryDirectory() as td:
            root=Path(td)
            (root/"Signal.java").write_text(fixture())
            original=registry.propose(root,"Signal.java")
            modified=json.loads(json.dumps(original))
            modified["module_manifest"]["can_promote_itself"]=True
            with self.assertRaisesRegex(SemanticRegistryError,"checksum"):
                registry.compile(root,modified,0)

if __name__=="__main__":
    unittest.main()
