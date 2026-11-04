# Cut Before

**Find the moment. Keep the question.** A working prototype for Kuku's AI Generalist assignment, Problem 1.

| Open | Link |
|---|---|
| Two-page solution | [Read PDF](https://atits23.github.io/cut-before-kuku-assignment/solution.pdf) |
| Public sample demo | [View report](https://atits23.github.io/cut-before-kuku-assignment/) |
| Runnable prototype | [Open in Colab](https://colab.research.google.com/github/atits23/cut-before-kuku-assignment/blob/main/Cut_Before.ipynb) |

The assignment run covered **50 episodes and 3,727 timed events**. It produced **17 shortlist, 20 reserve and 13 reject decisions**. The confidential raw results are not included in this public repository and must be shared separately with the assignment reviewers.

The public demo uses an original flooded-vault story. It is a saved report; use the notebook or Python commands below to run a new input. The AI review is a separate model step, not an API call hidden inside the scanner. Twelve code tests pass. No audience performance has been measured.

## Try it in one minute

Needs Python 3.10 or later. There are **no packages to install, API keys or network calls** in the Python tool. Open a terminal in this folder:

```sh
python cut_before.py scan examples/new_story.txt --out demo
```

Open `demo/baseline.html` in a browser. This uses an original, unrelated test story. The output is explicitly marked **unreviewed**.

For a notebook version, upload `Cut_Before.ipynb` to Google Colab or open it in Jupyter. The notebook embeds the same Python tool and original test story; its demo cells require no external files. The Colab upload cell is optional. Hosted Colab itself was not tested here; its plain Python demo cells were tested locally.

## Run on a new show

```sh
python cut_before.py scan "path/to/scripts.zip" --out new_run
```

The input can also be a directory of `.txt` files or one `.txt` file. Use the supplied pack's format: `EPISODE NUMBER: Episode 1`, bold event labels, and `Start: (MM:SS.cc) | End: (MM:SS.cc)` lines. See `examples/new_story.txt`. UTF-8 text only. Episode numbers must be unique within a show. Bad formats fail clearly rather than silently dropping lines.

The script searches continuous 20-60 second windows, keeps up to three varied suggestions per episode and writes a complete episode coverage log. Some short or quiet episodes may yield fewer suggestions. It uses generic English signals for danger, betrayal, identity and arrivals. It does not contain the show's character names or saved promo timestamps.

## The AI step: simple, replaceable and explicit

`scan` is a rule-based first pass. **It does not call an AI model.** AI decides whether the story makes sense and whether the ending is really unresolved.

1. Open a file in `new_run/review_packets/`. It contains the review prompt, original event timeline, exact timestamps and suggested windows.
2. Give it to an AI tool approved for that input. Ask for the JSON described in the prompt. A free chat tool can be used. Try one episode in an interview; process all episodes for a full show. Several small packets can be reviewed together.
3. Save each returned JSON in a separate `model_reviews/` directory. Record the actual tool used. Keep the model's output so failures remain inspectable. Each episode must occur exactly once across the files.
4. Merge the reviews, then validate them:

```sh
python cut_before.py merge model_reviews --out merged
python cut_before.py finalize "path/to/scripts.zip" --review merged/review.json --out new_run
```

If the model returns one combined JSON covering every episode, skip `merge`. If validation fails, correct the review with the model and save the correction separately. The code refuses wrong-input reviews, missing/duplicate episodes, invented boundaries, clipped speech and invalid scores. It cannot prove that a model's explanation is true.

**To change models:** use the same review packets and JSON contract in a different approved tool. No parser or ranking code needs to change. There is no API adapter in this version. A batch API adapter is a next step, not a claimed feature.

## What the editor gets

- `report.html`: searchable ranked cards, status/episode filters, cut points, reasons, risks and source evidence. Works offline after generation.
- `ranked_promos.json`: ordered segment lists and the full scoring breakdown.
- `ranked_promos.csv`: a flat edit list for the editor's usual tools.
- `baseline.json` and `baseline.html`: the unreviewed suggestions, kept separate.
- `run_manifest.json`: coverage, source fingerprints, event count and measured scan time.
- `validation.json`: the checks that passed and the things not tested.
- `review_packets/`: reusable prompts and source timelines. These inherit the source's confidentiality.

Clips use original episode-relative timestamps. Duration is end minus start. There is exactly one continuous segment per clip in this version. No frame rate or video was supplied, so these are script cut points, not frame-accurate edit decisions. Every clip still needs a footage check.

The AI scores hook, cliffhanger, standalone clarity and stakes from 0 to 5. The weighted score is `6*hook + 7*cliffhanger + 5*clarity + 2*stakes`, out of 100. Shortlisted clips appear before reserve clips. Within each group, score descends and episode number breaks ties. These numbers express editorial judgment, not a probability of success. An editor can keep a higher-scoring clip in reserve because of a spoiler, weak opening or slow middle.

## Quality checks

```sh
python -m unittest -v test_cut_before
```

Tests cover a new story, source boundaries, clipped speech, input fingerprints, missing/duplicate reviews, score limits, malformed input, ZIP path handling and HTML escaping. The synthetic review in the tests is a fixture, not a live model output.

The private assignment results also include an AI self-audit of the baseline's top ten. It is not an independent editor study. Do not present it as accuracy or measured ad performance.

## Limits and next steps

- English rules miss visual-only hooks, irony and softer drama. They also confuse literal threats with harmless words such as a hearth fire.
- This parser supports the supplied screenplay format, not PDFs, video or every screenplay format.
- AI can invent motives or borrow context from the full episode. Review the clip alone and check the quoted evidence.
- No cross-episode montages, video rendering, audience testing, model API integration or automatic posting.
- Within-episode suggestions are spread out by overlap. Similar story beats across different episodes still need an editor's judgment.
- At larger volume, cache parsed episodes by source fingerprint, review episode batches through an approved model API and send only the shortlist to an editor. Model review is the slow step; the local scan is small.

## Confidentiality and reproducibility

The public prototype contains only code, a notebook and original synthetic examples. **Do not upload the supplied Kuku scripts, review packets or private outputs to a public code repository.** Keep assignment-derived results in the evaluator submission channel. The original input ZIP is not bundled here.

For the supplied show, the exact replay commands are in the private submission's `START_HERE.md`. Replaying a saved AI review reproduces that review's ranking; it does not call a model again or claim a fresh AI judgment.
