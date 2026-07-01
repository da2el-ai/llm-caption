"""除外タグリストの読み込みと照合用正規化。

`IGNORE_TAGS_DIR` 直下の `*.csv`（Danbooru wildcards 形式）を読み込み、
除外対象タグの正規化済みセットを作る。CSV は 1 行目をヘッダとして読み飛ばし、
各行の先頭カラム（1 列目）をタグ名として扱う。
"""

from __future__ import annotations

import csv
from pathlib import Path


def normalize_tag(tag: str) -> str:
    """WD 出力タグと CSV タグの表記ゆれを吸収するための正規化。

    小文字化し、括弧エスケープ（\\( \\)）を除去し、アンダースコアを
    半角スペースに統一する。WD の整形後タグ（"hatsune miku"）でも
    CSV の生形式（"hatsune_miku"）でも同じ文字列になる。
    """
    return tag.replace("\\", "").replace("_", " ").strip().lower()


def load_ignore_tags(ignore_dir: Path) -> set[str]:
    """除外ディレクトリ直下の全 CSV を読み込み、正規化済みタグ集合を返す。

    ディレクトリが存在しない、または CSV が 1 つも無い場合は空集合を返す
    （＝除外を行わない）。各 CSV の 1 行目はヘッダとして読み飛ばす。
    """
    ignore_dir = Path(ignore_dir)
    if not ignore_dir.is_dir():
        return set()

    ignore: set[str] = set()
    for csv_path in sorted(ignore_dir.glob("*.csv")):
        # 配布 CSV には UTF-8 として不正なバイトを含む行が混じることがある。
        # そうしたタグは WD 出力（ASCII の Danbooru タグ）と一致しないため、
        # errors="replace" で読み飛ばして処理を止めない。
        with csv_path.open(encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # ヘッダ行を読み飛ばす
            for row in reader:
                if not row:
                    continue
                name = row[0].strip()
                if name:
                    ignore.add(normalize_tag(name))
    return ignore
