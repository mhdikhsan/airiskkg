from airiskkg.paths import ONTOLOGY_DIR


def test_paths_import() -> None:
    assert ONTOLOGY_DIR.name == "ontology"
