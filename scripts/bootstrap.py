import os
import sys
import subprocess
import shutil
from pathlib import Path


ENV_NAME = "venv"


def run(cmd, env=None):
    """Run a shell command and stream output."""
    print(f"\n>> {' '.join(cmd)}")
    subprocess.check_call(cmd, env=env)


def get_venv_paths(env_name):
    """Return platform-specific paths."""
    if os.name == "nt":
        python_path = Path(env_name) / "Scripts" / "python.exe"
        pip_path = Path(env_name) / "Scripts" / "pip.exe"
    else:
        python_path = Path(env_name) / "bin" / "python"
        pip_path = Path(env_name) / "bin" / "pip"

    return python_path, pip_path


def create_venv(env_name, recreate=False):
    """Create or recreate virtual environment."""
    if Path(env_name).exists():
        if recreate:
            print(f"Removing existing venv: {env_name}")
            shutil.rmtree(env_name)
        else:
            print(f"Venv already exists: {env_name}")
            return

    print(f"Creating virtual environment: {env_name}")
    run([sys.executable, "-m", "venv", env_name])


def install_dependencies(pip_path):
    """Install dependencies."""
    # Upgrade pip first
    run([str(pip_path), "install", "--upgrade", "pip", "setuptools", "wheel"])

    # Install from requirements.txt if present
    if Path("requirements.txt").exists():
        print("Installing from requirements.txt...")
        run([str(pip_path), "install", "-r", "requirements.txt"])
    else:
        print("No requirements.txt found, skipping.")


def install_current_package(pip_path):
    """Install current project (useful for PyPI-style projects)."""
    if Path("pyproject.toml").exists() or Path("setup.py").exists():
        print("Installing current package...")
        run([str(pip_path), "install", "-e", "."])
    else:
        print("No project file found (pyproject.toml/setup.py), skipping.")


def main():
    recreate = "--recreate" in sys.argv

    print("🚀 Python environment bootstrap")

    create_venv(ENV_NAME, recreate=recreate)

    python_path, pip_path = get_venv_paths(ENV_NAME)

    if not python_path.exists():
        print("❌ Failed to locate venv Python executable")
        sys.exit(1)

    install_dependencies(pip_path)
    install_current_package(pip_path)

    print("\n✅ Setup complete!")

    if os.name == "nt":
        activate_cmd = f"{ENV_NAME}\\Scripts\\activate"
    else:
        activate_cmd = f"source {ENV_NAME}/bin/activate"

    print(f"\n👉 To activate the environment:\n{activate_cmd}")
    print(f"\n👉 Or run directly:\n{python_path} your_script.py")


if __name__ == "__main__":
    main()

