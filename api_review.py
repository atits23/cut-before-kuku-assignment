"""Optional model API step. Standard library only; never needed by the offline demo."""
import argparse
import getpass
import json
import os
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


def request_spec(protocol, base_url, model, prompt, max_tokens=4096,
                 chat_token_field="max_completion_tokens"):
    base_url = base_url.rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment):
        raise APIReviewError("Use an HTTPS API base URL without credentials, query or fragment.")
    if protocol not in ("responses", "chat_completions"):
        raise APIReviewError("Protocol must be responses or chat_completions.")
    if not isinstance(model, str) or not model.strip():
        raise APIReviewError("Enter the exact model ID provided by the interviewer.")
    if type(max_tokens) is not int or not 256 <= max_tokens <= 32768:
        raise APIReviewError("Output token limit must be an integer from 256 to 32768.")
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
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + api_key.strip(), "Content-Type": "application/json"})
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
    if protocol == "responses":
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
            manifest["calls"].append(dict(episode=number, response_id=response.get("id"),
                returned_model=response.get("model"), usage=response.get("usage")))
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
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="https://api.openai.com/v1")
    parser.add_argument("--protocol", choices=["responses", "chat_completions"], default="responses")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-episodes", type=int, default=1)
    parser.add_argument("--chat-token-field", choices=["max_completion_tokens", "max_tokens"], default="max_completion_tokens")
    args = parser.parse_args()
    key = os.environ.get("MODEL_API_KEY") or getpass.getpass("Provider API key (hidden): ")
    try:
        review_with_api(args.input, args.out, api_key=key, model=args.model,
            base_url=args.base_url, protocol=args.protocol, max_tokens=args.max_tokens,
            max_episodes=args.max_episodes, chat_token_field=args.chat_token_field)
    except (ValueError, KeyError, TypeError, OSError) as err:
        print("Run stopped:", str(err) if isinstance(err, APIReviewError) else "Output failed validation. Inspect saved output locally; do not use it as a valid report.")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
