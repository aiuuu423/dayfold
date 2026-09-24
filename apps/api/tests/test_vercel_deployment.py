import importlib.util
import json
from pathlib import Path

from fastapi import FastAPI


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_vercel_entrypoint_exports_fastapi_app() -> None:
    entrypoint_path = REPOSITORY_ROOT / "app.py"
    spec = importlib.util.spec_from_file_location("dayfold_vercel_entrypoint", entrypoint_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert isinstance(module.app, FastAPI)


def test_vercel_configuration_targets_api_entrypoint() -> None:
    config = json.loads((REPOSITORY_ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["regions"] == ["hkg1"]
    assert config["functions"]["app.py"]["maxDuration"] == 180
    assert "rewrites" not in config


def test_root_requirements_include_api_dependencies() -> None:
    root_requirements = {
        line.strip()
        for line in (REPOSITORY_ROOT / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }
    api_requirements = {
        line.strip()
        for line in (REPOSITORY_ROOT / "apps/api/requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }

    assert root_requirements == api_requirements


def test_vercel_python_version_is_pinned() -> None:
    python_version = (REPOSITORY_ROOT / ".python-version").read_text(
        encoding="utf-8"
    )

    assert python_version.strip() == "3.12"
