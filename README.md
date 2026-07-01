# llm-caption

WD-EVA02 タガーとローカル / 外部 LLM を使い、画像から学習用キャプションを生成するツール。

1. **WD-EVA02** で Danbooru タグを推論
2. **LLM（Gemma 等）** に画像とタグを渡して自然言語キャプションを生成
3. 画像と同名の `.txt` に「タグ」「自然言語」の順で書き出す

## 1. 環境構築

Python 3.10 以上を推奨。

```powershell
# リポジトリをクローン
git clone https://github.com/da2el-ai/llm-caption.git
cd llm-caption

# 仮想環境（任意）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# pytorchインストール
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
# RTX50xx環境はこっち
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# 本体と依存をインストール（editable）。これで `llm-caption` コマンドが使える
pip install -e .
```

GPU を使う場合は環境に合った PyTorch（CUDA 版）を別途インストールしてください。
参考: https://pytorch.org/get-started/locally/

## 2. モデルの入手

### WD-EVA02-Large-Tagger-v3

`MODEL_DIR`（既定 `./model`）に以下 3 点を配置します。

- `wd-eva02-large-tagger-v3.safetensors`（重み, 約 1.2GB）
- `config.json`
- `selected_tags.csv`

入手元: https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3

```
model/
├─ wd-eva02-large-tagger-v3.safetensors
├─ config.json
└─ selected_tags.csv
```

### 除外タグリスト（任意）

キャラクター名や作品名を Danbooru タグから除外したい場合、`IGNORE_TAGS_DIR`
（既定 `./ignore_tags`）に除外タグの CSV を置きます。直下の `*.csv` をすべて読み込み、
各行の先頭カラムのタグを出力から除外します（1 行目はヘッダとして読み飛ばし）。
CSV を置かなければ除外は行われません。

入手元（Danbooru wildcards）:

- キャラクター名: https://huggingface.co/datasets/X779/Danbooruwildcards/blob/main/character.csv
- 作品名: https://huggingface.co/datasets/X779/Danbooruwildcards/blob/main/copyright.csv

```
ignore_tags/
├─ character.csv
└─ copyright.csv
```

### LLM（Gemma）

ローカルでは llama.cpp の `llama-server` を使います。マルチモーダル（画像入力）には
**mmproj（vision projector）GGUF が必須** です。

```powershell
# 画像入力ありで起動（mmproj が必要）
.\llama-server.exe -m "{モデルパス}\gemma-4-12B-it-abliterated-uncensored-i1-GGUF\gemma-4-12B-it-abliterated-uncensored.i1-Q5_K_M.gguf" --mmproj "{モデルパス}\gemma-4-12B-it-qat-q4_0-uncensored-heretic-mmproj-BF16.gguf" -ngl 99 --jinja --port 8080
```

mmproj を用意できない場合は、`.env` で `LLM_SEND_IMAGE=false` にするとタグのみから
自然言語キャプションを生成できます（画像入力なし）。

外部 LLM サーバーを使う場合は `.env` の `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` を変更します。

## 3. 設定

`.env.example` を `.env` にコピーして編集します。

```powershell
copy .env.example .env
```

最低限、`IMAGE_DIR`（画像フォルダ）と `MODEL_DIR`、`LLM_BASE_URL` を確認してください。
各キーの意味は [.env.example](.env.example) のコメントを参照。

## 4. 実行

`pip install -e .` で導入した `llm-caption` コマンドを使います。

```powershell
# 仮想環境に入っていなければ入る
.\.venv\Scripts\Activate.ps1

# Danbooru タグのみ
llm-caption --mode danbooru

# 自然言語のみ（既存タグがあれば利用）
llm-caption --mode natural

# タグ → 自然言語（既定）
llm-caption --mode both

# 別フォルダを指定 / 既存を強制再生成
llm-caption --mode both --input "D:\lora\dataset" --force

# 除外タグを無効化して全タグを出力（キャラクター・作品タグの混入確認用）
llm-caption --mode danbooru --no-ignore-tags --force
```

- 入力フォルダは **再帰的** に探索します（サブフォルダも対象）。
- 既存キャプションは原則スキップし、`--force` で上書き再生成します。
- `--no-ignore-tags` は除外タグリスト（`IGNORE_TAGS_DIR`）を無視し、全タグを残します。
  除外前にどのキャラクター・作品タグが出るかを確認したいときに使います。

## 出力例

`foo.jpg` に対して `foo.txt`：

```
1girl, long hair, smile, school uniform, outdoors

A young woman with long hair smiles warmly while standing outdoors in a school uniform, ...
```

## ドキュメント

- 仕様: [.claude/spec.md](.claude/spec.md)
- 留意事項: [.claude/knowledge.md](.claude/knowledge.md)
- コーディング規約: [.claude/coding-guide.md](.claude/coding-guide.md)
