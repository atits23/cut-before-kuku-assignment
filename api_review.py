"""Optional model API step. Standard library only; never needed by the offline demo."""
import argparse
import getpass
import json
import os
import re
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

import cut_before as cb


class APIReviewError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a key to a redirected host.


GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def gemini_base_url(base_url):
    parsed = urllib.parse.urlsplit(base_url.rstrip('/'))
    if (parsed.scheme != 'https' or parsed.netloc != 'generativelanguage.googleapis.com'
            or parsed.query or parsed.fragment or parsed.path not in ('', '/v1beta', '/v1')):
        raise APIReviewError("For Gemini use https://generativelanguage.googleapis.com/v1beta (no /models suffix).")
    return 'https://' + parsed.netloc + (parsed.path or '/v1beta')


def list_gemini_models(api_key, base_url=GEMINI_BASE):
    """List models available to the supplied key. Sends no screenplay or generation request."""
    base_url = gemini_base_url(base_url)
    models, token, seen = [], '', set()
    while True:
        url = base_url + '/models?pageSize=1000'
        if token:
            url += '&pageToken=' + urllib.parse.quote(token, safe='')
        payload = post_json(url, None, api_key)
        try:
            data = json.loads(payload)
            for model in data.get('models', []):
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    models.append(model['name'].removeprefix('models/'))
            token = data.get('nextPageToken', '')
        except (ValueError, TypeError, KeyError, AttributeError):
            raise APIReviewError("Could not read Gemini's model list. Check the key and API access.") from None
        if not token:
            break
        if token in seen:
            raise APIReviewError("Gemini model pagination repeated; stop and retry listing later.")
        seen.add(token)
    return sorted(set(models))


def choose_gemini_model(api_key, model='', base_url=GEMINI_BASE, choose=input):
    available = list_gemini_models(api_key, base_url)
    model = model.strip().removeprefix('models/')
    if model in available:
        return model
    if not available:
        raise APIReviewError("This key returned no models supporting generateContent. Check Gemini API access.")
    print("Choose a model available to this key (the previous model is blank or unavailable):")
    print('\n'.join(available))
    selected = choose("Paste one model ID from the list above: ").strip().removeprefix('models/')
    if selected not in available:
        raise APIReviewError("That model is not in the returned list. Run again and select an exact model ID.")
    return selected


def request_spec(protocol, base_url, model, prompt, max_tokens=4096,
                 chat_token_field="max_completion_tokens"):
    base_url = base_url.rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment):
        raise APIReviewError("Use an HTTPS API base URL without credentials, query or fragment.")
    if protocol not in ("responses", "chat_completions", "gemini"):
        raise APIReviewError("Protocol must be responses, chat_completions or gemini.")
    if parsed.hostname == 'generativelanguage.googleapis.com' and protocol != 'gemini' and not (protocol == 'chat_completions' and parsed.path.rstrip('/') == '/v1beta/openai'):
        raise APIReviewError("Gemini URL with the wrong API format. Select Gemini in the notebook, or use --protocol gemini with https://generativelanguage.googleapis.com/v1beta.")
    if not isinstance(model, str) or not model.strip():
        raise APIReviewError("Enter the exact model ID provided by the interviewer.")
    if type(max_tokens) is not int or not 256 <= max_tokens <= 32768:
        raise APIReviewError("Output token limit must be an integer from 256 to 32768.")
    if protocol == 'gemini':
        base_url = gemini_base_url(base_url)
        model = model.strip().removeprefix('models/')
        if not re.fullmatch(r'[A-Za-z0-9._-]+', model):
            raise APIReviewError("Use a Gemini model ID from the available model list, not a URL.")
        return base_url + '/models/' + model + ':generateContent', dict(
            contents=[dict(role='user', parts=[dict(text=prompt)])],
            generationConfig=dict(maxOutputTokens=max_tokens, responseMimeType='application/json'))
    if protocol == "responses":
        return base_url + "/responses", dict(model=model, input=prompt,
                                             max_output_tokens=max_tokens, store=False)
    if chat_token_field not in ("max_completion_tokens", "max_tokens"):
        raise APIReviewError("Choose max_completion_tokens or max_tokens for this provider.")
    return base_url + "/chat/completions", dict(model=model,
        messages=[dict(role="user", content=prompt)], **{chat_token_field: max_tokens})


def post_json(url, body, api_key, timeout=120):
    if not isinstance(api_key, str) or not api_key.strip() or any(c in api_key for c in "\r\n"):
        raise APIReviewError("A valid API key is required. Use hidden input or an environment variable.")
    native_gemini = (urllib.parse.urlsplit(url).hostname == 'generativelanguage.googleapis.com'
                     and '/openai/' not in urllib.parse.urlsplit(url).path)
    auth = {'x-goog-api-key': api_key.strip()} if native_gemini else {'Authorization': 'Bearer ' + api_key.strip()}
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET", headers={**auth, 'Content-Type':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as err:
        # Provider error bodies can echo prompts or credentials; never print them.
        status = err.code
        hints = {401: "Check the key.", 403: "Check model and account permissions.",
                 404: "Check the base URL, protocol and model ID.",
                 429: "Rate or quota limit; wait or check the account budget.",
                 400: "Check model parameters, token field and context length."}
        raise APIReviewError(f"API HTTP {status}. " + hints.get(status, "Check provider status and settings.") +
                             " No automatic retry was made.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise APIReviewError("API connection failed or timed out. No automatic retry was made; a request may still have been billed.") from None


def response_text(data, protocol):
    if protocol == 'gemini':
        candidates = data.get('candidates', [])
        if not candidates or candidates[0].get('finishReason') != 'STOP':
            raise APIReviewError("Gemini returned no complete answer (blocked or token limit). Inspect the saved response; increase output tokens if finishReason is MAX_TOKENS.")
        answer = ''.join(part.get('text', '') for part in candidates[0].get('content', {}).get('parts', [])
                         if not part.get('thought'))
    elif protocol == "responses":
        if data.get("status") != "completed":
            raise APIReviewError("Response did not complete. Inspect the saved response; check output budget or refusal.")
        chunks = [c.get("text", "") for item in data.get("output", [])
                  if item.get("type") == "message" for c in item.get("content", [])
                  if c.get("type") == "output_text"]
        answer = "".join(chunks)
    else:
        choices = data.get("choices", [])
        if not choices or choices[0].get("finish_reason") != "stop":
            raise APIReviewError("Chat response was truncated, refused or returned a tool call. Inspect the saved response.")
        message = choices[0].get("message", {})
        if message.get("refusal"):
            raise APIReviewError("Model refused the request. Inspect the saved response.")
        answer = message.get("content")
    if not isinstance(answer, str) or not answer.strip():
        raise APIReviewError("No text answer returned. Inspect the saved response.")
    return answer


def parse_review(answer, pack_hash, episode):
    text = answer.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3].strip()
    try:
        data = json.loads(text)
        if data.get("pack_sha256") != pack_hash:
            raise APIReviewError("Model returned the wrong input fingerprint.")
        reviews = data["reviews"]
        if not isinstance(reviews, list) or len(reviews) != 1 or type(reviews[0].get("episode")) is not int or reviews[0]["episode"] != episode:
            raise APIReviewError("Model must return exactly the requested episode once.")
        return reviews[0]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        raise APIReviewError("Model did not return the required JSON contract. Raw output is preserved; no fallback result was invented.") from None


def review_with_api(input_path, out, *, api_key, model, base_url="https://api.openai.com/v1",
                    protocol="responses", max_tokens=4096, max_episodes=1,
                    chat_token_field="max_completion_tokens", timeout=120):
    """One call per episode, then the same strict validator used by manual reviews.

    A new output directory is required. No auto retries, hidden fallback or paid demo.
    max_episodes is a guard, not a subset selector: the whole supplied input is reviewed.
    """
    input_path, out = Path(input_path), Path(out)
    episodes, pack_hash = cb.load_pack(input_path)
    if type(max_episodes) is not int or max_episodes < 1 or len(episodes) > max_episodes:
        raise APIReviewError(f"Input has {len(episodes)} episodes; limit is {max_episodes}. Use a one-episode TXT for the interview, or explicitly raise max_episodes for the full pack.")
    request_spec(protocol, base_url, model, "", max_tokens, chat_token_field)
    if not api_key or not api_key.strip():
        raise APIReviewError("Enter an API key before starting.")
    if out.exists():
        raise APIReviewError("Choose a new output directory to preserve earlier runs and failed responses.")
    out.mkdir(parents=True)
    cb.scan(input_path, out)
    raw = out / "api_responses"
    raw.mkdir()
    manifest = dict(protocol=protocol, base_url=base_url, requested_model=model,
                    pack_sha256=pack_hash, episodes=len(episodes), max_output_tokens=max_tokens,
                    automatic_retries=0, status="running", calls=[])
    cb.dump(out / "api_run.json", manifest)
    reviews = []
    try:
        for ep in episodes:
            number = ep["episode"]
            packet = (out / "review_packets" / f"episode_{number:03d}.txt").read_text(encoding="utf-8")
            url, body = request_spec(protocol, base_url, model, packet, max_tokens, chat_token_field)
            print(f"Requesting episode {number} ({len(reviews)+1}/{len(episodes)})...")
            payload = post_json(url, body, api_key, timeout)
            (raw / f"episode_{number:03d}.response.json").write_bytes(payload)
            try:
                response = json.loads(payload)
                if not isinstance(response, dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                raise APIReviewError("API returned invalid JSON. Raw response was saved.") from None
            manifest["calls"].append(dict(episode=number, response_id=response.get("id", response.get('responseId')),
                returned_model=response.get("model", response.get('modelVersion')), usage=response.get("usage", response.get('usageMetadata'))))
            cb.dump(out / "api_run.json", manifest)
            answer = response_text(response, protocol)
            (raw / f"episode_{number:03d}.answer.txt").write_text(answer, encoding="utf-8")
            reviews.append(parse_review(answer, pack_hash, number))
        review = dict(pack_sha256=pack_hash, reviewer=f"API {protocol}: {model}",
            method="One API call per episode using its full timeline and rule suggestions. Unedited provider responses and usage are in api_responses/ and api_run.json. No human approval or audience testing.", reviews=reviews)
        cb.dump(out / "ai_review.json", review)
        cb.finalize(input_path, out / "ai_review.json", out)
        manifest["status"] = "validated"
    except Exception:
        manifest["status"] = "failed"
        cb.dump(out / "api_run.json", manifest)
        raise
    cb.dump(out / "api_run.json", manifest)
    return out / "report.html"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default='')
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--protocol", choices=["responses", "chat_completions", "gemini"], default="responses")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-episodes", type=int, default=1)
    parser.add_argument("--chat-token-field", choices=["max_completion_tokens", "max_tokens"], default="max_completion_tokens")
    args = parser.parse_args()
    key = os.environ.get("MODEL_API_KEY") or (os.environ.get('GEMINI_API_KEY') if args.protocol=='gemini' else None) or getpass.getpass("Provider API key (hidden): ")
    try:
        args.base_url = args.base_url or (GEMINI_BASE if args.protocol=='gemini' else 'https://api.openai.com/v1')
        if args.protocol == 'gemini':
            args.model = choose_gemini_model(key, args.model, args.base_url)
        review_with_api(args.input, args.out, api_key=key, model=args.model,
            base_url=args.base_url, protocol=args.protocol, max_tokens=args.max_tokens,
            max_episodes=args.max_episodes, chat_token_field=args.chat_token_field)
    except (ValueError, KeyError, TypeError, OSError) as err:
        print("Run stopped:", str(err) if isinstance(err, APIReviewError) else "Output failed validation. Inspect saved output locally; do not use it as a valid report.")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()

