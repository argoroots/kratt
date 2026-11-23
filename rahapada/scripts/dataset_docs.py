"""Make the db_write ops for the dashboard's datasets after the files are uploaded.

Usage:
  python3 dataset_docs.py WORK URLS.json [--op set|update] [--only id ...]

URLS.json: {"<file name>": "/_blob/<id>", ...} from upload_asset (e.g. {"months.json": "/_blob/…"}).
Empty datasets need no upload of their own: upload one file "empty.json" with the text [] and give it as
"empty.json"; every empty dataset then points to it.
Prints a JSON list of ops (datasets/<id>) to pass to db_write as is. With --op update, add ifVersion to each op
from db_list datasets.
"""
import argparse
import datetime as dt
import json
import os

from common import load_json

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work")
    parser.add_argument("urls")
    parser.add_argument("--op", default="set")
    parser.add_argument("--only", nargs="*", default=None)
    arguments = parser.parse_args()

    titles = load_json(os.path.join(HERE, "..", "templates", "datasets.json"))
    urls = load_json(arguments.urls)
    out_dir = os.path.join(arguments.work, "out", "datasets")
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ops = []
    for dataset in sorted(titles):
        if arguments.only is not None and dataset not in arguments.only:
            continue
        rows = load_json(os.path.join(out_dir, dataset + ".json"))
        name = dataset + ".json" if rows else "empty.json"
        if name not in urls:
            raise SystemExit(f"{name}: url puudub ({dataset})")
        document = dict(
            title=titles[dataset]["title"],
            description=titles[dataset]["description"],
            source=dict(kind="file", url=urls[name], name=dataset + ".json", format="json"),
            fixed=True,
            updated=dict(at=now, by="Rahapada"),
        )
        ops.append(dict(op=arguments.op, path="datasets/" + dataset, data=document))
    print(json.dumps(ops, ensure_ascii=False))


if __name__ == "__main__":
    main()
