import json
from datetime import datetime, timezone
from pathlib import Path

SOURCE_RECORDS_PATH = Path("data/source_records.json")


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    output = {
        "last_source_collection": datetime.now(timezone.utc).strftime("%d %B %Y"),
        "records": []
    }

    save_json(SOURCE_RECORDS_PATH, output)

    print(f"Wrote {SOURCE_RECORDS_PATH}")


if __name__ == "__main__":
    main()
