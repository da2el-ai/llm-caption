"""画像キャプション生成のエントリポイント。

使い方:
  python caption.py --mode danbooru        # WD-EVA02 で Danbooru タグのみ生成
  python caption.py --mode natural         # LLM で自然言語キャプション生成（タグがあれば利用）
  python caption.py --mode both            # タグ生成 -> 自然言語キャプション生成（既定）
  python caption.py --report count         # 既存キャプションのタグ出現頻度を集計（生成なし）

入力フォルダやモデル設定は .env で指定する。--input で上書き可能。
キャプションは画像と同名の .txt に「Danbooruタグ」「自然言語」の順で書き込む。
既存キャプションは原則スキップし、--force で強制的に再生成する。
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from .config import IMAGE_EXTENSIONS, Settings

# キャプションファイル内で Danbooru ブロックと自然言語ブロックを区切る空行
_SEPARATOR = "\n\n"


def find_images(root: Path) -> list[Path]:
    """root 以下を再帰的に探索し、画像ファイルを返す。"""
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def read_caption(txt_path: Path) -> tuple[str, str]:
    """既存キャプションを (danbooru, natural) に分解する。

    先頭の空行（\\n\\n）で 2 ブロックに分ける。区切りが無い場合は
    全体を Danbooru ブロックとして扱う。
    """
    if not txt_path.exists():
        return "", ""
    content = txt_path.read_text(encoding="utf-8").strip()
    if not content:
        return "", ""
    if _SEPARATOR in content:
        danbooru, natural = content.split(_SEPARATOR, 1)
        return danbooru.strip(), natural.strip()
    return content.strip(), ""


def write_caption(txt_path: Path, danbooru: str, natural: str) -> None:
    danbooru = danbooru.strip()
    natural = natural.strip()
    if danbooru and natural:
        text = f"{danbooru}{_SEPARATOR}{natural}"
    else:
        text = danbooru or natural
    txt_path.write_text(text + "\n", encoding="utf-8")


def collect_danbooru_tags(images: list[Path]) -> tuple[Counter[str], int]:
    """各画像に対応する .txt の Danbooru ブロックからタグを集計する。

    戻り値は (タグの出現回数カウンタ, 読み込んだ .txt の件数)。
    自然言語ブロックは対象外。タグは保存された表記のまま数える。
    """
    counter: Counter[str] = Counter()
    txt_count = 0
    for image_path in images:
        txt_path = image_path.with_suffix(".txt")
        if not txt_path.exists():
            continue
        txt_count += 1
        danbooru, _ = read_caption(txt_path)
        if not danbooru:
            continue
        for tag in danbooru.split(","):
            tag = tag.strip()
            if tag:
                counter[tag] += 1
    return counter, txt_count


def run_report(image_dir: Path, images: list[Path], sort_by: str) -> int:
    """Danbooru タグ出現頻度を image_dir 直下の _report_.csv に書き出す。"""
    counter, txt_count = collect_danbooru_tags(images)

    if txt_count == 0:
        print(
            f"[エラー] 集計対象のキャプションファイル（.txt）が見つかりません: {image_dir}",
            file=sys.stderr,
        )
        return 1
    if not counter:
        print(
            "[警告] Danbooru タグが 1 件も見つからなかったため、レポートは作成しません。",
            file=sys.stderr,
        )
        return 0

    if sort_by == "count":
        # 出現回数の降順。同数はタグ名の昇順で安定させる。
        items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    else:  # "tag"
        items = sorted(counter.items(), key=lambda kv: kv[0])

    report_path = image_dir / "_report_.csv"
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tag", "count"])
        writer.writerows(items)

    print(f"レポート出力: {report_path}（{len(items)} タグ）")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WD-EVA02 タグ + LLM による画像キャプション生成",
    )
    parser.add_argument(
        "--mode",
        choices=("danbooru", "natural", "both"),
        default=None,
        help="生成するキャプションの種類（既定: both。--report のみ指定時は生成を省略）",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="画像フォルダ。未指定時は .env の IMAGE_DIR を使用",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="既存キャプションがあっても再生成して上書きする",
    )
    parser.add_argument(
        "--no-ignore-tags",
        action="store_true",
        help="除外タグリスト（IGNORE_TAGS_DIR）を無視し、全タグを残す（確認用）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="生成したキャプション（Danbooru タグ・LLM の応答）をコンソールに表示する",
    )
    parser.add_argument(
        "--report",
        choices=("count", "tag"),
        default=None,
        help="Danbooru タグ出現頻度を _report_.csv に集計（count=回数順 / tag=英数順）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings.load()

    image_dir = args.input or settings.image_dir
    if not image_dir.exists():
        print(f"[エラー] 入力フォルダが存在しません: {image_dir}", file=sys.stderr)
        return 1

    images = find_images(image_dir)
    if not images:
        print(f"[警告] 画像が見つかりませんでした: {image_dir}", file=sys.stderr)
        return 0

    # --report 単独指定（--mode 未指定）のときは生成せず集計のみ行う
    if args.report and args.mode is None:
        return run_report(image_dir, images, args.report)

    mode = args.mode or "both"
    print(f"対象画像: {len(images)} 件 / モード: {mode}")

    want_danbooru = mode in ("danbooru", "both")
    want_natural = mode in ("natural", "both")

    # 重い依存は必要なときだけ読み込む（遅延初期化）
    tagger = None
    captioner = None

    processed = 0
    skipped = 0
    failed = 0

    total = len(images)
    width = len(str(total))  # 総数の桁数でゼロ埋め幅を決める

    for idx, image_path in enumerate(images, start=1):
        prefix = f"[{idx:0{width}d}/{total}]"
        txt_path = image_path.with_suffix(".txt")
        danbooru, natural = read_caption(txt_path)

        need_danbooru = want_danbooru and (args.force or not danbooru)
        need_natural = want_natural and (args.force or not natural)

        if not need_danbooru and not need_natural:
            skipped += 1
            print(f"{prefix} [スキップ] {image_path.relative_to(image_dir)}")
            continue

        try:
            if need_danbooru:
                if tagger is None:
                    from .ignore_tags import load_ignore_tags
                    from .tagger import Tagger

                    if args.no_ignore_tags:
                        ignore_tags = set()
                        print("除外タグ: 無効（--no-ignore-tags）")
                    else:
                        ignore_tags = load_ignore_tags(settings.ignore_tags_dir)
                        if ignore_tags:
                            print(
                                f"除外タグ: {len(ignore_tags)} 件"
                                f"（{settings.ignore_tags_dir}）"
                            )
                    tagger = Tagger(
                        model_dir=settings.model_dir,
                        general_threshold=settings.general_threshold,
                        character_threshold=settings.character_threshold,
                        include_ratings=settings.include_ratings,
                        replace_underscore=settings.replace_underscore,
                        escape_parentheses=settings.escape_parentheses,
                        ignore_tags=ignore_tags,
                    )
                    tagger.load()
                danbooru = tagger.tag(image_path)
                if args.debug:
                    print(f"{prefix} [DEBUG] Danbooruタグ: {danbooru!r}")

            if need_natural:
                if captioner is None:
                    from .llm_caption import LLMCaptioner

                    captioner = LLMCaptioner(
                        base_url=settings.llm_base_url,
                        api_key=settings.llm_api_key,
                        model=settings.llm_model,
                        temperature=settings.llm_temperature,
                        max_tokens=settings.llm_max_tokens,
                        send_image=settings.llm_send_image,
                        disable_thinking=settings.llm_disable_thinking,
                        language=settings.caption_language,
                        system_prompt=settings.llm_system_prompt,
                    )
                natural = captioner.caption(image_path, danbooru)
                if args.debug:
                    print(f"{prefix} [DEBUG] LLM応答（{len(natural)} 文字）: {natural!r}")
                    if not natural:
                        print(
                            f"{prefix} [DEBUG] LLM が空文字を返したため自然言語は書き込まれません。"
                            " モデル/サーバー設定（--mmproj 有無、LLM_SEND_IMAGE）を確認してください。",
                            file=sys.stderr,
                        )

            write_caption(txt_path, danbooru, natural)
            processed += 1
            print(f"{prefix} [OK] {image_path.relative_to(image_dir)}")
        except Exception as exc:  # noqa: BLE001 - 1 枚の失敗で全体を止めない
            failed += 1
            print(f"{prefix} [失敗] {image_path}: {exc}", file=sys.stderr)

    print(f"完了: 生成 {processed} / スキップ {skipped} / 失敗 {failed}")
    exit_code = 1 if failed else 0

    # --mode と併用時は、キャプション生成後にレポートを作成する
    if args.report:
        report_code = run_report(image_dir, images, args.report)
        if report_code != 0:
            exit_code = report_code

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
