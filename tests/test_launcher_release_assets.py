import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "launcher/src/backend/release_assets.rs"


def platforms() -> list:
    """(OS, architecture, the game's asset) for each system the launcher's `PLATFORMS` names."""
    found = re.findall(r'\(\s*"(\w+)",\s*"(\w+)",\s*"(sunrise-[^"]+)"', ASSETS.read_text(encoding="utf-8"))
    if not found:
        raise AssertionError(f"{ASSETS} names no platform")
    return found


class LauncherReleaseAssets(unittest.TestCase):
    def test_every_game_asset_a_launcher_looks_for_is_built_signed_and_published(self):
        build = (ROOT / ".github/workflows/game-build.yml").read_text(encoding="utf-8")
        nightly = (ROOT / ".github/workflows/nightly-build.yml").read_text(encoding="utf-8")
        for os_name, arch, game in platforms():
            with self.subTest(asset=game):
                self.assertIn(f"asset: {game}", build, f"game-build.yml builds no {game}")
                named = nightly.count(f"dist/{game}")
                # Windows ARM64's and, for a snapshot, Intel macOS's build may fail without holding the release.
                optional = (os_name, arch) in (("windows", "aarch64"), ("macos", "x86_64"))
                self.assertTrue(named == 2 or (optional and named > 2),
                                f"nightly-build.yml must sign and publish {game} ({os_name} {arch})")


if __name__ == "__main__":
    unittest.main()
