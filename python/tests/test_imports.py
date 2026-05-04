from airiskkg.paths import DATA_DIR


def test_paths_import() -> None:
    assert DATA_DIR.name == "data"
