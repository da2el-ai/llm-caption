"""ローカル / 外部 LLM による自然言語キャプション生成。

OpenAI 互換 API（ローカルの llama-server、外部サーバーいずれも）を用いる。
LLM がやることは「画像とタグを受け取り、自然言語キャプションを返す」だけ。
ファイルの読み書きやタグ生成は呼び出し側（caption.py）が担う。

llama-server をマルチモーダルで動かすには mmproj が必要:
  llama-server.exe -m <model.gguf> --mmproj <mmproj.gguf> -ngl 99 --jinja --port 8080
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from openai import OpenAI

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert image captioner for training image-generation models. "
    "Write a single, fluent {language} caption that describes the image in natural prose: "
    "the subject, appearance, clothing, pose, expression, setting, lighting and composition. "
    "Danbooru tags may be provided as hints — use them to ground your description, "
    "but write flowing sentences, not a list of tags. "
    "Output only the caption text. Do not add preamble, quotes, or explanations."
)


def _image_to_data_uri(image_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(image_path))
    if mime is None:
        mime = "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


class LLMCaptioner:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 1024,
        send_image: bool = True,
        disable_thinking: bool = True,
        language: str = "English",
        system_prompt: str = "",
    ) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.send_image = send_image
        self.disable_thinking = disable_thinking
        self.language = language
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT.format(language=language)

    def _build_user_content(self, image_path: Path, danbooru_tags: str):
        parts: list[dict] = []
        if danbooru_tags:
            parts.append(
                {
                    "type": "text",
                    "text": f"Danbooru tags for this image:\n{danbooru_tags}",
                }
            )
        else:
            parts.append(
                {
                    "type": "text",
                    "text": "Describe this image.",
                }
            )
        if self.send_image:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _image_to_data_uri(image_path)},
                }
            )
        return parts

    def caption(self, image_path: Path, danbooru_tags: str = "") -> str:
        """画像（と任意の Danbooru タグ）から自然言語キャプションを返す。

        思考（reasoning）付きモデルでは思考が max_tokens を食い潰し content が空になるため、
        disable_thinking=True のとき jinja テンプレートの思考を無効化して回答のみ得る。
        """
        extra_body = {}
        if self.disable_thinking:
            # llama.cpp + Gemma 系の jinja テンプレートで思考を無効化する
            extra_body = {"chat_template_kwargs": {"enable_thinking": False}}

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": self._build_user_content(image_path, danbooru_tags)},
            ],
            extra_body=extra_body,
        )
        return (response.choices[0].message.content or "").strip()
