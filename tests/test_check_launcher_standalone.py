import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.ci import check_launcher_standalone as guard


class LauncherStandalone(unittest.TestCase):
    def tree(self, files: dict) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(subprocess.run, ["rm", "-rf", str(root)])
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        return root

    def found(self, files: dict) -> list:
        root = self.tree(files)
        return guard.problems(root, guard.tracked(root))

    def test_paths_inside_the_launcher_pass(self):
        self.assertEqual(self.found({
            "launcher/Cargo.toml": '[workspace]\nmembers = ["crates/a"]\n[dependencies]\na = { path = "crates/a" }\n',
            "launcher/crates/a/Cargo.toml": '[dependencies]\nb = { path = "../b" }\n',
            "launcher/crates/a/src/lib.rs": 'const L: &str = include_str!("../../../lang/en.json");\n'
                                            '#[path = "x_tests.rs"]\nmod tests;\n'
                                            'fn f() { Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures"); }\n',
            "outside.rs": 'include_str!("../../etc/passwd");\n',
        }), [])

    def test_every_way_out_is_named(self):
        found = self.found({
            "launcher/Cargo.toml": '[dependencies]\ngame = { path = "../crates/game" }\n'
                                   '[patch.crates-io]\nx = { path = "/opt/x" }\n',
            "launcher/src/main.rs": 'const V: &str = include_str!("../../tools/ci/rust-version");\n'
                                    '#[path = "../../crates/game/src/shared.rs"]\nmod shared;\n'
                                    'fn f() { Path::new(env!("CARGO_MANIFEST_DIR")).join(".."); }\n'
                                    'const W: &str = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../README.md"));\n',
        })
        self.assertEqual(len(found), 6, found)
        self.assertIn("launcher/Cargo.toml: path '../crates/game' leaves launcher/", found)
        self.assertIn("launcher/src/main.rs:1: '../../tools/ci/rust-version' leaves launcher/", found)
        self.assertTrue(any(":4: '..' leaves" in problem for problem in found), found)

    def test_this_repository_launcher_builds_from_its_own_files(self):
        self.assertEqual(guard.problems(guard.ROOT, guard.tracked(guard.ROOT)), [])


if __name__ == "__main__":
    unittest.main()
