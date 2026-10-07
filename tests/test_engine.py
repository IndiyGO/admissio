from pathlib import Path

from admissio.config import Placement, RulesConfig, load_config
from admissio.directories.memory import MemoryDirectory
from admissio.engine import sync
from admissio.logins import LoginGenerator
from admissio.models import NewHire, Status
from admissio.rules import Rules
from admissio.sources import load_new_hires

ROOT = Path(__file__).resolve().parents[1]

RULES = Rules(
    RulesConfig(
        default=Placement(email_domain="example.org", ou="ou=people"),
        match={"São Paulo": Placement(email_domain="sp.example.org", ou="ou=sp", groups=["cn=sp"])},
    )
)
GEN = LoginGenerator(["{first}.{last}", "{second}.{last}", "{first}.{last}{n}"])


def run(hires, directory=None, dry_run=False):
    directory = directory or MemoryDirectory()
    return sync(hires, directory, RULES, GEN, lambda: "Pw-123456789", dry_run=dry_run), directory


def test_collision_with_directory_falls_back_to_second_name():
    directory = MemoryDirectory({"ana.souza": "E0042"})
    results, _ = run([NewHire("E1", "Ana Beatriz Souza")], directory)
    assert results[0].login == "beatriz.souza"


def test_collision_within_same_batch():
    results, _ = run([NewHire("E1", "Ana Souza"), NewHire("E2", "Ana Souza")])
    assert [r.login for r in results] == ["ana.souza", "ana.souza2"]


def test_rerun_is_idempotent():
    hires = [NewHire("E1", "Lucas Ferreira")]
    _, directory = run(hires)
    results, _ = run(hires, directory)
    assert results[0].status is Status.EXISTS
    assert results[0].login == "lucas.ferreira"


def test_rules_are_accent_and_case_insensitive():
    results, directory = run([NewHire("E1", "Lucas Ferreira", branch="SAO PAULO")])
    assert results[0].email == "lucas.ferreira@sp.example.org"
    assert directory.created[0].groups == ["cn=sp"]


def test_dry_run_changes_nothing():
    results, directory = run([NewHire("E1", "Lucas Ferreira")], dry_run=True)
    assert results[0].status is Status.WOULD_CREATE
    assert directory.accounts == {}


def test_invalid_and_duplicate_rows():
    results, _ = run([NewHire("E1", ""), NewHire("E2", "Ana Souza"), NewHire("E2", "Ana Souza")])
    assert [r.status for r in results] == [Status.INVALID, Status.CREATED, Status.DUPLICATE]


def test_example_csv_end_to_end():
    cfg = load_config(ROOT / "config.example.yaml")
    hires = load_new_hires(cfg.source)
    results, _ = run(hires, MemoryDirectory({"ana.souza": "E0042"}))
    by_id = {r.employee_id: r for r in results if r.status is Status.CREATED}
    assert by_id["E1001"].login == "paula.souza"
    assert by_id["E1006"].login == "maria.davila"
    assert by_id["E1004"].login == "joao.oliveira"
    assert by_id["E1005"].login == "joao.oliveira2"


def test_packed_bpm_export():
    cfg = load_config(ROOT / "examples" / "bpm_export.yaml")
    hires = load_new_hires(cfg.source)
    assert [(h.employee_id, h.full_name, h.branch) for h in hires] == [
        ("B2001", "Carla Mendes Rocha", "Rio de Janeiro"),
        ("B2002", "Rafael Lima", "São Paulo"),
    ]
