import argparse

from airiskkg.paths import DATA_DIR, NOTEBOOKS_DIR, PROCESSED_DATA_DIR, RAW_DATA_DIR, TAXONOMY_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Risk Knowledge Graph project utilities.")
    parser.add_argument("command", choices=["info"], help="Command to run.")
    args = parser.parse_args()

    if args.command == "info":
        print("AI Risk Knowledge Graph")
        print(f"data: {DATA_DIR}")
        print(f"raw: {RAW_DATA_DIR}")
        print(f"processed: {PROCESSED_DATA_DIR}")
        print(f"taxonomy: {TAXONOMY_DIR}")
        print(f"notebooks: {NOTEBOOKS_DIR}")
