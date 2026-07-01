"""環境設定の読み込み。

.env から全パラメータを読み込む。ハードコーディングは行わない。
値が無い場合は妥当なデフォルトにフォールバックする。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# プロジェクトルートの .env を読み込む（既存の環境変数は上書きしない）
# このファイルは scripts/ 配下にあるため、ルートは 1 つ上の階層。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_bool(key: str, default: bool) -> bool:
    raw = _get(key)
    if raw == "":
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _get_float(key: str, default: float) -> float:
    raw = _get(key)
    return float(raw) if raw else default


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    return int(raw) if raw else default


# 画像ファイルとして扱う拡張子
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


@dataclass
class Settings:
    # 入出力
    image_dir: Path
    model_dir: Path
    ignore_tags_dir: Path

    # WD-EVA02 タガー
    general_threshold: float
    character_threshold: float
    include_ratings: bool
    replace_underscore: bool
    escape_parentheses: bool

    # LLM（OpenAI 互換 API）
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_send_image: bool
    llm_disable_thinking: bool
    caption_language: str
    llm_system_prompt: str

    @classmethod
    def load(cls) -> "Settings":
        image_dir = Path(_get("IMAGE_DIR", str(_PROJECT_ROOT / "images")))
        model_dir = Path(_get("MODEL_DIR", str(_PROJECT_ROOT / "model")))
        ignore_tags_dir = Path(_get("IGNORE_TAGS_DIR", str(_PROJECT_ROOT / "ignore_tags")))
        return cls(
            image_dir=image_dir,
            model_dir=model_dir,
            ignore_tags_dir=ignore_tags_dir,
            general_threshold=_get_float("GENERAL_THRESHOLD", 0.35),
            character_threshold=_get_float("CHARACTER_THRESHOLD", 0.85),
            include_ratings=_get_bool("INCLUDE_RATINGS", False),
            replace_underscore=_get_bool("REPLACE_UNDERSCORE", True),
            escape_parentheses=_get_bool("ESCAPE_PARENTHESES", True),
            llm_base_url=_get("LLM_BASE_URL", "http://localhost:8080/v1"),
            llm_api_key=_get("LLM_API_KEY", "local"),
            llm_model=_get("LLM_MODEL", "gemma"),
            llm_temperature=_get_float("LLM_TEMPERATURE", 0.4),
            llm_max_tokens=_get_int("LLM_MAX_TOKENS", 1024),
            llm_send_image=_get_bool("LLM_SEND_IMAGE", True),
            llm_disable_thinking=_get_bool("LLM_DISABLE_THINKING", True),
            caption_language=_get("CAPTION_LANGUAGE", "English"),
            llm_system_prompt=_get("LLM_SYSTEM_PROMPT", ""),
        )
