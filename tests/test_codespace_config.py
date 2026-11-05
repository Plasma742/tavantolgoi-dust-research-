"""Static checks for the GitHub Codespaces configuration (not a test of Earth Engine output)."""
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEV = ROOT / ".devcontainer"


class CodespaceConfigTests(unittest.TestCase):
    def test_devcontainer_forwards_only_the_dashboard(self):
        cfg = json.loads((DEV / "devcontainer.json").read_text())
        self.assertEqual(cfg["forwardPorts"], [5173])
        self.assertEqual(cfg["portsAttributes"]["8000"]["onAutoForward"], "silent")
        self.assertNotIn("public", json.dumps(cfg).lower().replace("keep public", ""))

    def test_scripts_are_valid_bash_and_store_no_secrets(self):
        for name in ("setup.sh", "start.sh"):
            path = DEV / name
            subprocess.run(["bash", "-n", str(path)], check=True)
            text = path.read_text()
            self.assertNotIn("private_key", text)
            self.assertNotIn("git add", text)
        start = (DEV / "start.sh").read_text()
        self.assertIn("--host 127.0.0.1", start)
        self.assertIn("earthengine authenticate", start)

    def test_env_file_is_ignored(self):
        self.assertIn(".env", (ROOT / ".gitignore").read_text().splitlines())


if __name__ == "__main__":
    unittest.main()
