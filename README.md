# llm-caption

WD-EVA02 タガーとローカル / 外部 LLM を使い、画像から学習用キャプションを生成するツール。

1. **WD-EVA02** で Danbooru タグを推論
2. **LLM（Gemma 等）** に画像とタグを渡して自然言語キャプションを生成
3. 画像と同名の `.txt` に「タグ」「自然言語」の順で書き出す
4. 除外タグの指定が可能
5. danbooruタグの使用回数レポートを出力

実際の出力サンプルは `sample/` フォルダをご覧ください。

## 環境構築

Python 3.10 以上を推奨。

環境に合った PyTorch（CUDA 版）をインストールしてください。<br>
参考: https://pytorch.org/get-started/locally/

```powershell
# リポジトリをクローン
git clone https://github.com/da2el-ai/llm-caption.git
cd llm-caption

# 仮想環境（任意）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# pytorchインストール（RTX30xx / RTX40xx）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
# RTX50xx環境はこちらを使う
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130

# 本体と依存をインストール（editable）。これで `llm-caption` コマンドが使える
pip install -e .
```


### 設定ファイルのコピー

`.env.example` を `.env` にコピーして編集します。

```powershell
copy .env.example .env
```

最低限、`IMAGE_DIR`（画像フォルダ）と `MODEL_DIR`（モデルフォルダ）、`LLM_BASE_URL`（LLM API URL） を確認してください。

各キーの意味は [.env.example](.env.example) のコメントを参照。


## モデルの入手

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

キャラクター名や作品名などを Danbooru タグから除外したい場合、`.env` の `IGNORE_TAGS_DIR`
（既定 `./ignore_tags`）に除外タグの CSV を置きます。
直下の `*.csv` をすべて読み込みますので、ユーザーが自由に追加できます。

CSV を置かなければ除外は行われません。

```
ignore_tags/
├─ {任意の名前}.csv
└─ {任意の名前}.csv
```

**フォーマット：**

- 各行の先頭カラムのタグを出力から除外します
- 1 行目はヘッダとして読み飛ばします
- カンマ `,` は無くても問題ありません

```
tag,count # 1行目は無視されます
masterpiece,123
best quality
```

**おすすめ：**

Danbooruタグのデータットを使うのがおすすめです。

- キャラクター名: https://huggingface.co/datasets/X779/Danbooruwildcards/blob/main/character.csv
- 作品名: https://huggingface.co/datasets/X779/Danbooruwildcards/blob/main/copyright.csv



### LLM（Gemma）

ローカルでは llama.cpp の `llama-server` を使います。マルチモーダル（画像入力）には
**mmproj（vision projector）GGUF が必須** です。

mmproj を用意できない場合は、`.env` で `LLM_SEND_IMAGE=false` にするとタグのみから自然言語キャプションを生成できます（画像入力なし）。

**llama.cpp 起動方法：**

```powershell
# 画像入力ありで起動（mmproj が必要）
.\llama-server.exe -m "{モデル}" --mmproj "{モデル}" -ngl 99 --jinja --port 8080
```

下記の例では gemma4 派生の無検閲版を使っています。<br>

入手元: https://huggingface.co/llmfan46/gemma-4-12B-it-qat-q4_0-uncensored-heretic-GGUF



```powershell
# 画像入力ありで起動（mmproj が必要）
.\llama-server.exe -m "D:\models\gemma-4-12B-it-qat-q4_0-uncensored-heretic-Q4_0.gguf" --mmproj "D:\models\gemma-4-12B-it-qat-q4_0-uncensored-heretic-mmproj-BF16.gguf" -ngl 99 --jinja --port 8080
```

外部 LLM サーバーを使う場合は `.env` の `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` を変更します。


## 実行

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

# 別フォルダを指定 / 既存を強制再生成 / 使用回数レポート出力
llm-caption --mode both --input "D:\lora\dataset" --force --report count

# 除外タグを無効化して全タグを出力（キャラクター・作品タグの混入確認用）
llm-caption --mode danbooru --no-ignore-tags --force
```

### 引数

- `--mode {danbooru|natural|both}` — 生成するキャプションの種類（既定: `both`）。
  - `danbooru` … WD-EVA02 で Danbooru タグのみ生成
  - `natural` … LLM で自然言語キャプションのみ生成（既存タグがあれば利用）
  - `both` … タグ生成 → 自然言語キャプション生成
- `--input <path>` — 画像フォルダを指定。未指定時は `.env` の `IMAGE_DIR` を使用。
- `--force` — 既存キャプションがあっても再生成して上書きする（未指定時はスキップ）。
- `--report {count|tag}` — danbooruタグの使用回数レポートをに出力
  - `count` … 出現回数順
  - `tag` … タグの英数順
  - 出力先: `{画像フォルダ}/_report_.csv`
- `--no-ignore-tags` — 除外タグリスト（`.env` の `IGNORE_TAGS_DIR`）を無視し、全タグを残す。除外前にどのキャラクター・作品タグが出るかを確認したいときに使う。
- `--debug` — 生成した Danbooru タグ・LLM の応答をコンソールに表示する。

- 入力フォルダは **再帰的** に探索します（サブフォルダも対象）。

### 出力例

`foo.jpg` に対して `foo.txt` が作成される。

**出力フォーマット：**
```
{danbooruタグ}

{自然言語キャプション}
```

**例：**
```
1girl, long hair, smile, school uniform, outdoors

A young woman with long hair smiles warmly while standing outdoors in a school uniform, ...
```

## 自然言語生成プロンプト

LLM に自然言語を生成させるためのシステムプロンプトです。<br>
`.env` の `LLM_SYSTEM_PROMPT` で指定します。

文中の `{language}` は出力言語を指定しています。

### 標準
```
You are an expert image captioner for training image-generation models. Write a single, fluent {language} caption that describes the image in natural prose: the subject, appearance, clothing, pose, expression, setting, lighting and composition. Danbooru tags may be provided as hints — use them to ground your description, but write flowing sentences, not a list of tags. Output only the caption text. Do not add preamble, quotes, or explanations.
```

日本語訳:
```
あなたは画像生成モデルの学習用データを作成する、熟練の画像キャプション作成者です。画像を自然な散文で説明する、流暢な {language} のキャプションを 1 つ書いてください。対象・外見・服装・ポーズ・表情・背景・照明・構図を描写します。Danbooru タグがヒントとして与えられることがあります。それらを説明の根拠として活用しつつ、タグの羅列ではなく流れのある文章で書いてください。出力はキャプション本文のみとします。前置き・引用符・説明は加えないでください。
```

### 画風LoRA向け
```
You are an expert image captioner for training a STYLE LoRA for an image-generation model. The goal is to teach the model an art style, so your caption must describe WHAT is depicted (the content), never HOW it is drawn (the art style).Write a single, fluent {language} caption in natural prose that describes only the content: the subject and the number of characters, their appearance (hair color, hairstyle, eye color), clothing and accessories, pose and action, facial expression, the background or setting, and the camera angle or composition.Do NOT describe the art style itself. Never mention the coloring or shading technique, line quality, overall color palette or color grading, lighting mood, texture or grain, brushwork, art medium (e.g. watercolor, oil, cel shading), or any quality or aesthetic judgement (e.g. masterpiece, beautiful). Do not reference any artist. You may still state the concrete color of specific objects such as hair, eyes, or clothing.Danbooru tags may be provided as hints — use them to ground your description, but ignore any style, quality, rating, or artist tags, and write flowing sentences, not a list of tags. Output only the caption text. Do not add preamble, quotes, or explanations.
```

日本語訳:
```
あなたは画像生成モデルの「画風LoRA」学習用の、熟練した画像キャプション作成者です。目的はモデルに画風を学習させることなので、キャプションには「何が描かれているか（内容）」だけを書き、「どのように描かれているか（画風）」は決して書かないでください。

{language} で、自然な文章による単一のキャプションを書いてください。記述するのは内容のみです：被写体とキャラクターの人数、外見（髪の色、髪型、目の色）、服装と小物、ポーズと動作、表情、背景や場所、そしてカメラアングルや構図。

画風そのものは記述しないでください。塗りやシェーディングの技法、線の質感、全体の色使いや色調、光の雰囲気、テクスチャやグレイン、筆致、画材（例：水彩、油彩、セル塗り）、品質や美的評価（例：傑作、美しい）には一切触れないこと。特定の作家名も参照しないこと。ただし、髪・目・服など個々の対象の具体的な色は記述して構いません。

Danbooruタグがヒントとして与えられる場合があります。記述の裏付けに使ってよいですが、画風・品質・レーティング・作家タグは無視し、タグの羅列ではなく流れるような文章で書いてください。出力はキャプション本文のみとします。前置き、引用符、説明は付けないこと。
```

### キャラクターLoRA向け
```
You are an expert image captioner for training a CHARACTER LoRA for an image-generation model. The goal is to teach the model one specific character. A separate trigger token represents that character's fixed identity, so your caption must describe only what VARIES between images (which stays controllable at generation time) and must NOT restate the character's fixed identity (which is absorbed into the character).Write a single, fluent {language} caption in natural prose that describes only the variable content: the pose and action, facial expression, camera angle and composition, the background or setting, the lighting, and any clothing, accessories or props the character is wearing or holding.Do NOT describe the character's fixed identity. Never mention hair color, hairstyle, eye color, facial features, body type, skin tone, or any permanent distinctive marks that define the character — these must bind to the trigger token, not to words. Do not add quality or aesthetic judgements (e.g. masterpiece, beautiful) or artist names.Danbooru tags may be provided as hints — use them to ground your description, but ignore identity, quality, rating, and artist tags, and write flowing sentences, not a list of tags. Output only the caption text. Do not add preamble, quotes, or explanations.
```

日本語訳:
```
あなたは画像生成モデルの「キャラクターLoRA」学習用の、熟練した画像キャプション作成者です。目的はモデルに特定のキャラクターを1体学習させることです。キャラクターの固定的な identity（同一性）は別途トリガーワードが担うため、キャプションには画像ごとに「変動する要素」だけを書き（これは生成時に制御可能なまま残ります）、キャラクターの固定的な identity は書かないでください（これはキャラクターに吸収されます）。

{language} で、自然な文章による単一のキャプションを書いてください。記述するのは変動する内容のみです：ポーズと動作、表情、カメラアングルと構図、背景や場所、ライティング、そしてキャラクターが着ている・身につけている・持っている服・小物・アクセサリー。

キャラクターの固定的な identity は記述しないでください。髪の色、髪型、目の色、顔立ち、体型、肌の色、そのキャラクターを特徴づける恒常的な特徴には決して触れないこと——これらは言葉ではなくトリガーワードに紐づける必要があります。品質や美的評価（例：傑作、美しい）、作家名も付けないこと。

Danbooruタグがヒントとして与えられる場合があります。記述の裏付けに使ってよいですが、identity・品質・レーティング・作家タグは無視し、タグの羅列ではなく流れるような文章で書いてください。出力はキャプション本文のみとします。前置き、引用符、説明は付けないこと。
```

## ライセンス

MIT

