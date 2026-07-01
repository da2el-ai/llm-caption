"""WD-EVA02-Large-Tagger-v3 による Danbooru タグ推論。

SmilingWolf の timm / safetensors 版モデルを使用する。
推論方法は公式モデルカードに準拠する:
  1. timm の transform で前処理
  2. RGB -> BGR にチャンネルを入れ替え
  3. sigmoid を適用して各タグの確率を得る
参照: https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3

必要ファイル（model_dir 内）:
  - *.safetensors        モデル重み
  - config.json          timm モデル設定（architecture / model_args / pretrained_cfg）
  - selected_tags.csv    タグ ID と名前の対応表
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import timm
import torch
import torch.nn.functional as F
from PIL import Image
from safetensors.torch import load_file
from timm.data import create_transform, resolve_data_config

from .ignore_tags import normalize_tag

# selected_tags.csv の category 列の意味
_CATEGORY_RATING = 9
_CATEGORY_GENERAL = 0
_CATEGORY_CHARACTER = 4


def _find_safetensors(model_dir: Path) -> Path:
    candidates = sorted(model_dir.glob("*.safetensors"))
    if not candidates:
        raise FileNotFoundError(
            f"{model_dir} に .safetensors ファイルが見つかりません。"
        )
    return candidates[0]


class Tagger:
    """WD-EVA02 タガー。モデルは初回の tag() 呼び出し前に load() で読み込む。"""

    def __init__(
        self,
        model_dir: Path,
        general_threshold: float = 0.35,
        character_threshold: float = 0.85,
        include_ratings: bool = False,
        replace_underscore: bool = True,
        escape_parentheses: bool = True,
        ignore_tags: set[str] | None = None,
        device: str | None = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.general_threshold = general_threshold
        self.character_threshold = character_threshold
        self.include_ratings = include_ratings
        self.replace_underscore = replace_underscore
        self.escape_parentheses = escape_parentheses
        # 除外タグ（正規化済みセット）。名前一致でカテゴリを問わず除外する。
        self.ignore_tags = ignore_tags or set()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self._model = None
        self._transform = None
        self._tags: list[str] = []
        self._categories: list[int] = []

    def load(self) -> None:
        config_path = self.model_dir / "config.json"
        csv_path = self.model_dir / "selected_tags.csv"
        for required in (config_path, csv_path):
            if not required.exists():
                raise FileNotFoundError(
                    f"{required} が見つかりません。"
                    " Hugging Face のモデルリポジトリから取得して model フォルダに配置してください。"
                )

        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        model = timm.create_model(
            cfg["architecture"],
            pretrained=False,
            num_classes=cfg["num_classes"],
            **cfg.get("model_args", {}),
        )
        model.pretrained_cfg = cfg["pretrained_cfg"]

        state_dict = load_file(str(_find_safetensors(self.model_dir)))
        model.load_state_dict(state_dict)
        model.eval().to(self.device)

        data_config = resolve_data_config(cfg["pretrained_cfg"], model=model)
        self._transform = create_transform(**data_config)
        self._model = model

        df = pd.read_csv(csv_path)
        self._tags = df["name"].tolist()
        self._categories = df["category"].tolist()

    @staticmethod
    def _to_rgb(image: Image.Image) -> Image.Image:
        """透過画像は白背景に合成する（WD タガーは白背景を前提とする）。"""
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            background = Image.new("RGBA", image.size, (255, 255, 255, 255))
            image = Image.alpha_composite(background, image)
        return image.convert("RGB")

    def _format(self, tag: str) -> str:
        if self.replace_underscore:
            tag = tag.replace("_", " ")
        if self.escape_parentheses:
            tag = tag.replace("(", "\\(").replace(")", "\\)")
        return tag

    @torch.inference_mode()
    def _predict(self, image: Image.Image) -> torch.Tensor:
        tensor = self._transform(self._to_rgb(image)).unsqueeze(0)
        tensor = tensor[:, [2, 1, 0]]  # RGB -> BGR
        tensor = tensor.to(self.device)
        logits = self._model(tensor)
        return F.sigmoid(logits)[0].cpu()

    def tag(self, image_path: Path) -> str:
        """画像 1 枚から Danbooru タグキャプション（カンマ区切り文字列）を返す。"""
        if self._model is None:
            self.load()

        with Image.open(image_path) as img:
            probs = self._predict(img)

        ratings: list[tuple[str, float]] = []
        characters: list[tuple[str, float]] = []
        generals: list[tuple[str, float]] = []
        for idx, score in enumerate(probs.tolist()):
            category = self._categories[idx]
            name = self._tags[idx]
            if category == _CATEGORY_RATING:
                ratings.append((name, score))
            elif category == _CATEGORY_CHARACTER:
                if score >= self.character_threshold:
                    characters.append((name, score))
            elif category == _CATEGORY_GENERAL:
                if score >= self.general_threshold:
                    generals.append((name, score))

        # 確信度の高い順に並べる
        characters.sort(key=lambda x: x[1], reverse=True)
        generals.sort(key=lambda x: x[1], reverse=True)

        ordered: list[str] = []
        if self.include_ratings and ratings:
            top_rating = max(ratings, key=lambda x: x[1])
            ordered.append(top_rating[0])
        # キャラクタータグ -> 一般タグの順（LoRA 学習で一般的な並び）
        ordered.extend(name for name, _ in characters)
        ordered.extend(name for name, _ in generals)

        # 除外リストに載るタグを取り除く（正規化して名前一致で判定）
        if self.ignore_tags:
            ordered = [t for t in ordered if normalize_tag(t) not in self.ignore_tags]

        return ", ".join(self._format(t) for t in ordered)
