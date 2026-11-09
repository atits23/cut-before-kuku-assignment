# Cut Before — Find the Promos

**Atit Kumar Satsangi | 230241 | Civil Engineering**

Problem 1 of the Kuku AI Generalist assignment. Find and rank 20–60 second promo moments from a timestamped screenplay. Each result gives the episode, start/end times, hook, cliffhanger and reason. This version selects one continuous segment per retained episode. **No video editing, music or text overlays.**

## Run on a new story

Open [the Colab notebook](https://colab.research.google.com/github/atits23/cut-before-kuku-assignment/blob/main/Cut_Before.ipynb) and run its five steps:

1. **Set up:** download the tested code. No story is loaded.
2. **Upload:** select one screenplay TXT or one ZIP containing all episode TXT files.
3. **API settings:** choose Gemini, OpenAI or Other compatible API, then tick `RUN_API`. For Gemini, leave MODEL blank to select an available model in the next step.
4. **Find promos:** enter the key privately. The model reviews every uploaded episode; the code validates and ranks its cuts.
5. **Download:** get the report, CSV, JSON, raw responses and validation log.

No fixed story or saved model answer is included in the notebook. Setup downloads two Python files from a pinned commit and verifies their hashes. Expand the setup form to inspect it.

### Input format

Use the assignment's UTF-8 TXT format: `EPISODE NUMBER: Episode 1`, bold event labels, and `Start: (MM:SS.cc) | End: (MM:SS.cc)` lines. Episode numbers must be unique. Upload the full ZIP to process the full show. PDFs, video and other screenplay formats need conversion first.

### Model API settings

**Gemini key:** select **Gemini**. Leave MODEL blank, tick RUN_API, then run step 4 and enter the key privately. The notebook lists models available to your key; paste one exact ID from that list. It sets `https://generativelanguage.googleapis.com/v1beta`, `generateContent` and the `x-goog-api-key` header automatically. Do not pair a Gemini URL with the OpenAI Responses protocol.

**OpenAI key:** select **OpenAI**, enter the model ID and tick RUN_API. The endpoint and Responses format are filled automatically.

**Another compatible provider:** select **Other compatible API**, enter CUSTOM_BASE_URL and MODEL, and select CUSTOM_PROTOCOL. This route supports Bearer-authenticated Responses or Chat Completions. Expand the cell to change CHAT_TOKEN_FIELD to `max_tokens` if required by that provider.

The default output allowance is 4096 tokens. An incomplete reasoning response may need more. Gemini model discovery sends no screenplay and does not generate content; the subsequent review makes one generation request per uploaded episode. Only use a provider approved for the scripts. Charges and quota depend on the provider account.

Wrong-format Google URLs are caught before any request. Missing or unavailable Gemini model IDs trigger model selection from the returned list. Invalid JSON, truncated answers or invalid cut points stop the run and preserve raw responses. No automatic retries or fixed fallback answer are used. Native Vertex AI and other authentication schemes are not implemented.

## Run locally

Python 3.10+, standard library only. Use your actual input path and supplied model ID:

```sh
python api_review.py "your-story.zip" --out api_runs/show_01 --model PROVIDED_MODEL_ID --max-episodes 50
```

For a compatible chat provider, add `--protocol chat_completions --base-url https://PROVIDER_HOST/v1` and its `--chat-token-field`. For native Gemini, use `--protocol gemini`; its endpoint is set automatically and a blank `--model` prompts from the model list. Keys come from hidden input, `MODEL_API_KEY` or `GEMINI_API_KEY` for Gemini. The CLI defaults to a one-episode guard; set `--max-episodes` to at least your input's count for a full pack. It never silently reviews only part of an input. Use a new output folder per run.

## Without an API key

Use an approved free chat tool with the same prompts and validator:

```sh
python cut_before.py scan "your-story.zip" --out new_run
```

Give every file in `new_run/review_packets/` to the chat tool. Save its returned JSON files in `model_reviews/`, preserving the actual outputs and model name. Each episode must occur once. Then run:

```sh
python cut_before.py merge model_reviews --out merged
python cut_before.py finalize "your-story.zip" --review merged/review.json --out new_run
```

For one combined review JSON, skip `merge` and pass that file to `finalize`. Replaying a saved review reproduces its decisions; it does not call AI again.

## Outputs and checks

- `report.html`: ranked promos, cut points, hook, cliffhanger, reason, concerns and source evidence.
- `ranked_promos.csv` and `.json`: cut list and ordered segment data.
- `baseline.json` / `.html`: unreviewed rule suggestions, preserved separately.
- `review_packets/`: input timelines and prompts.
- `api_responses/`: unedited provider responses and extracted answers for API runs.
- `api_run.json`: model, endpoint, response IDs, usage and run status; never the key.
- `validation.json`: duration, boundaries, uncut dialogue, scores and coverage checks.

**Test first** means stronger ideas after a footage check. **Review further** means valid cuts with story or pacing concerns. **Not recommended** means no clip selected from that episode. The saved JSON uses `shortlist`, `reserve` and `reject` for these categories. Scores weight hook 30%, cliffhanger 35%, standalone clarity 25% and stakes 10%. They are judgments, not predicted performance.

## Verification and limits

```sh
python -m unittest -v test_cut_before test_api_review
```

Twenty-nine tests cover parsing, boundaries, scores, new inputs and simulated API responses. The notebook is also checked with simulated uploads and responses. Hosted Colab setup, upload and Gemini model listing were tested. The prior live generation attempt returned HTTP 404; successful live generation remains unverified. The original 50-episode submission used chat review, not the later API adapter. No audience uplift or frame accuracy is claimed.

Files under `examples/` are **automated-test fixtures only**. They are not loaded by the notebook or used as new-story results. There is no montage search. An editor must check the opening, ending, clarity and script-to-video timing. The submitted baseline and failure audit preserve actual mistakes.

Keep confidential scripts, responses and notebook outputs out of public repositories. Clear private cell outputs before sharing. The original Kuku ZIP is not bundled.

API references: [Gemini API](https://ai.google.dev/api), [OpenAI text generation](https://developers.openai.com/api/docs/guides/text), [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

## API connection troubleshooting

Open the latest notebook and rerun setup to load the corrected adapter. Tick RUN_API and TEST_CONNECTION_ONLY to test one small generation request without sending a screenplay. Untick TEST_CONNECTION_ONLY and rerun the settings cell before processing your upload.

Gemini uses x-goog-api-key; OpenAI uses Authorization: Bearer. Both send JSON Content-Type and Accept headers, plus an honest client User-Agent. No Mozilla/browser header is required. OpenAI root URLs and complete Responses/Chat endpoints are normalized to avoid duplicate paths. Custom providers must supply their documented base URL, protocol, model ID and token field.

401: check the provider/key. 403: check permissions. 404: check model availability and endpoint. 429: check quota/credits or rate limits. A model appearing in a listing does not prove generation access. Error messages now include recognized provider error codes and rejected token parameters without echoing private error bodies. No automatic retry or model substitution occurs.
