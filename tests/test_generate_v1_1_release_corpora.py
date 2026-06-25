import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_v1_1_release_corpora.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_v1_1_release_corpora", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GenerateV11ReleaseCorporaTest(unittest.TestCase):
    def test_answerable_rows_are_symptom_anchored_by_default(self):
        generator = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "repo_sources" / "demo" / "src" / "demo.c"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                "int launch_guard(int count) {\n"
                "  if (count == 0) return -1;\n"
                "  return launch(count);\n"
                "}\n",
                encoding="utf-8",
            )
            source = generator.Source(
                source_id="src:demo",
                project="demo",
                repo_name="demo",
                path="repo_sources/demo/src/demo.c",
                source_type="code",
                authority="primary_source",
                line_count=4,
            )
            selected = [
                generator.Signal(
                    signal_id="sig:demo:long-tail",
                    project="demo",
                    axis=2,
                    attribute="long_tail",
                    source_id="src:demo",
                    path=source.path,
                    lines="1",
                ),
                generator.Signal(
                    signal_id="sig:demo:implicit",
                    project="demo",
                    axis=3,
                    attribute="implicit_domain_knowledge",
                    source_id="src:demo",
                    path=source.path,
                    lines="2",
                ),
            ]

            row = generator.make_row(
                "demo",
                4,
                "L1",
                "answerable",
                selected,
                {"src:demo": source},
                repo_root,
            )

        self.assertNotIn("file_anchor_required", row["tags"])
        self.assertNotIn("repo_sources/demo/src/demo.c", row["query"])
        self.assertNotIn("demo.c", row["query"])

    def test_load_sources_excludes_low_quality_artifact_paths(self):
        generator = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            bundle.mkdir()
            good = root / "repo_sources" / "demo" / "src" / "main.c"
            external = root / "repo_sources" / "demo" / "external" / "protobuf" / "generated.cc"
            binary = root / "repo_sources" / "demo" / "sw" / "regression" / "golden" / "output.dimg"
            for path in (good, external, binary):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("line\n", encoding="utf-8")
            rows = [
                {
                    "source_id": "src:good",
                    "project": "demo",
                    "repo_name": "demo",
                    "path": str(good.relative_to(root)),
                    "source_type": "code.source",
                    "authority": "primary_source",
                    "line_count": 1,
                },
                {
                    "source_id": "src:external",
                    "project": "demo",
                    "repo_name": "demo",
                    "path": str(external.relative_to(root)),
                    "source_type": "code.source",
                    "authority": "primary_source",
                    "line_count": 1,
                },
                {
                    "source_id": "src:binary",
                    "project": "demo",
                    "repo_name": "demo",
                    "path": str(binary.relative_to(root)),
                    "source_type": "binary.asset",
                    "authority": "primary_source",
                    "line_count": 1,
                },
            ]
            (bundle / "source_inventory.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            sources = generator.load_sources(bundle, "demo", root)

        self.assertEqual(set(sources), {"src:good"})


if __name__ == "__main__":
    unittest.main()
