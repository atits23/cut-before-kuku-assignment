# Cut Before

**Atit Kumar Satsangi | 230241 | Civil Engineering**

**Find the moment. Keep the question.** A working submission for Kuku's AI Generalist assignment, Problem 1.

| Open | Link |
|---|---|
| Two-page solution | [Read PDF](https://atits23.github.io/cut-before-kuku-assignment/solution.pdf) |
| Submission website | [View report](https://atits23.github.io/cut-before-kuku-assignment/) |
| Runnable prototype | [Open in Colab](https://colab.research.google.com/github/atits23/cut-before-kuku-assignment/blob/main/Cut_Before.ipynb) |

The full run covered **50 episodes and 3,727 timed events**, with **17 test-first clips, 20 clips needing further review and 13 episodes not recommended**. Full results and unedited raw outputs are available through the complete encrypted review link supplied in the placement form. That link opens without an account. Its key is deliberately absent from this repository.

The notebook starts with your uploaded screenplay, then API settings, fresh review and output download. It has no preloaded story or fixed model answer. The original full-pack submission results came from chat review and remain available separately.

## Review access and confidentiality

`docs/review.enc` contains AES-256-GCM encrypted assignment outputs. The full review URL carries the key in its fragment, which is not included in the HTTP request. The browser decrypts locally; there are no analytics or third-party scripts. **Anyone with the complete link can read the material.** This is link-based sharing, not identity-based access. Do not post that link in public issues, README files or repository history. The original input ZIP is not uploaded. Generated review packets inside the protected download contain confidential source excerpts.

The PDF describes the solution and a few selected promo examples. Code and clearly labelled automated-test fixtures are public; test fixtures are not used by the notebook. Twenty code tests pass, including eight simulated-response API tests; no live paid API run is claimed. No audience performance has been measured.

## Run on a new story

Open [the Colab notebook](https://colab.research.google.com/github/atits23/cut-before-kuku-assignment/blob/main/Cut_Before.ipynb) and run its five steps:

1. **Set up:** download the tested code. No story is loaded.
2. **Upload:** select one screenplay TXT or one ZIP containing all episode TXT files.
3. **API settings:** enter the supplied base URL and model ID, choose the protocol and tick `RUN_API`.
4. **Find promos:** enter the key privately. The model reviews every uploaded episode; the code validates and ranks its cuts.
5. **Download:** get the report, CSV, JSON, raw responses and validation log.

No fixed story or saved model answer is included in the notebook. Setup downloads two Python files from a pinned commit and verifies their hashes. Expand the setup form to inspect it.

### Input format

Use the assignment's UTF-8 TXT format: `EPISODE NUMBER: Episode 1`, bold event labels, and `Start: (MM:SS.cc) | End: (MM:SS.cc)` lines. Episode numbers must be unique. Upload the full ZIP to process the full show. PDFs, video and other screenplay formats need conversion first.

### Model API settings

| Setting | Enter |
|---|---|
| `API_PROTOCOL` | `responses` or `chat_completions` |
| `API_BASE_URL` | Provider base URL; for OpenAI, `https://api.openai.com/v1` |
| `MODEL` | The exact model ID supplied to you |
| Key | Enter privately when step 4 asks; never put it in code |

Both protocols use HTTPS and Bearer authentication. Do not append `/responses` or `/chat/completions` to the base URL. For a compatible chat provider requiring `max_tokens`, expand step 3 and change `CHAT_TOKEN_FIELD` from `max_completion_tokens` to `max_tokens`. The default output allowance is 4096 tokens; an incomplete reasoning response may need more. Native APIs with different schemas or authentication need another adapter.

The upload step shows the request count: one request per episode. Only send scripts to an approved provider; charges may apply. There are no automatic retries. Invalid JSON, wrong episode IDs, wrong fingerprints, truncated responses and invalid cuts stop the run. Raw responses are preserved; no demo answer is substituted. Use a new run for a deliberate retry.

Change the model ID to switch models. Change the protocol and base URL too when moving to another compatible provider. Parsing and ranking remain the same.

## Run locally

Python 3.10+, standard library only. Use your actual input path and supplied model ID:

```sh
python api_review.py "your-story.zip" --out api_runs/show_01 --model PROVIDED_MODEL_ID --max-episodes 50
```

For a compatible chat provider, add `--protocol chat_completions --base-url https://PROVIDER_HOST/v1` and its `--chat-token-field`. The key comes from hidden input or `MODEL_API_KEY`. The CLI defaults to a one-episode guard; set `--max-episodes` to at least your input's count for a full pack. It never silently reviews only part of an input. Use a new output folder per run.

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

Twenty tests cover parsing, boundaries, scores, new inputs and simulated API responses. The notebook is also checked with simulated uploads and responses. A live paid API run and hosted Colab upload have not been tested. The original 50-episode submission used chat review, not the later API adapter. No audience uplift or frame accuracy is claimed.

Files under `examples/` are **automated-test fixtures only**. They are not loaded by the notebook or used as new-story results. There is no montage search. An editor must check the opening, ending, clarity and script-to-video timing. The submitted baseline and failure audit preserve actual mistakes.

Keep confidential scripts, responses and notebook outputs out of public repositories. Clear private cell outputs before sharing. The original Kuku ZIP is not bundled.

API references: [OpenAI text generation](https://developers.openai.com/api/docs/guides/text), [Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
