import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import config  # noqa: E402


def test_get_db_path_defaults_to_repo_root(monkeypatch, tmp_path):
    project_root = tmp_path / "Turtle_investment_framework"
    project_root.mkdir()

    monkeypatch.setattr(config, "PROJECT_ROOT", str(project_root))
    monkeypatch.delenv("TURTLE_DB_PATH", raising=False)

    assert config.get_db_path() == str(project_root / "stock_analysis.db")


def test_get_hk_new_financials_dir_falls_back_to_repo_sibling(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    project_root = workspace / "Turtle_investment_framework"
    hk_dir = workspace / "hk_new_financials"
    project_root.mkdir(parents=True)
    hk_dir.mkdir()

    monkeypatch.setattr(config, "PROJECT_ROOT", str(project_root))
    monkeypatch.delenv("TURTLE_CSMAR_HK_DIR", raising=False)
    monkeypatch.delenv("TURTLE_DATA_ROOT", raising=False)

    assert config.get_hk_new_financials_dir() == str(hk_dir)


def test_get_csmar_a_xlsx_prefers_env_override(monkeypatch, tmp_path):
    workbook = tmp_path / "custom.xlsx"
    workbook.write_text("stub", encoding="utf-8")

    monkeypatch.setenv("TURTLE_CSMAR_A_PATH", str(workbook))

    assert config.get_csmar_a_xlsx() == str(workbook)
