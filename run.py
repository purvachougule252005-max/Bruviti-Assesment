"""One command: python run.py. Installs once, then serves locally on port 8000."""

from pathlib import Path
import subprocess
import sys
import venv


def main() -> int:
    if sys.version_info < (3, 11):
        print("PartTrace requires Python 3.11 or newer.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parent
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        print("Creating local virtual environment...", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    # Query the target interpreter, not the caller's environment. This lets an
    # installed service restart without asking a package index for anything.
    requirements = [line.strip().split("==") for line in
                    (root / "requirements.txt").read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
    check = (
        "import importlib.metadata as m, sys; "
        f"required = {requirements!r}; "
        "sys.exit(0 if all(m.version(name) == version for name, version in required) else 1)"
    )
    installed = subprocess.run([str(python), "-c", check], cwd=root, capture_output=True)
    if installed.returncode:
        print("Installing pinned service dependencies...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        "--no-input", "-r", str(root / "requirements.txt")], cwd=root, check=True)
    print("PartTrace: http://127.0.0.1:8000/ (Ctrl+C to stop)", flush=True)
    try:
        return subprocess.call([str(python), "-m", "uvicorn", "parttrace.api:app",
                                "--host", "127.0.0.1", "--port", "8000", "--lifespan", "on"], cwd=root)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Startup failed: {error}", file=sys.stderr)
        raise SystemExit(1)
