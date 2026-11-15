import json
import re
import time

from config.settings import GROQ_API_KEY, GROQ_MAX_TOKENS, GROQ_MODEL

_TRANSIENT = ("429", "rate limit", "rate_limit", "timeout", "timed out", "502", "503", "504",
              "overloaded", "connection", "temporarily")


def get_llm(temperature=0.0, json_mode=False, model=None, max_tokens=None):
    from langchain_groq import ChatGroq
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is missing. Add it to your .env file.")
    llm = ChatGroq(model=model or GROQ_MODEL, api_key=GROQ_API_KEY,
                   temperature=temperature, max_tokens=max_tokens or GROQ_MAX_TOKENS)
    return llm.bind(response_format={"type": "json_object"}) if json_mode else llm


def invoke_with_retry(llm, messages, retries=4):
    """Retry only transient errors (rate limit, timeout, 5xx) with back-off 4, 8, 16 s.
    Anything else (bad key, bad request) fails immediately instead of after a long wait."""
    for attempt in range(retries):
        try:
            return llm.invoke(messages)
        except Exception as error:
            transient = any(t in str(error).lower() for t in _TRANSIENT)
            if not transient or attempt == retries - 1:
                raise
            time.sleep(4 * (2 ** attempt))


_JSON_FAIL = ("json_validate_failed", "failed to validate json", "unreadable response")


def invoke_json(messages, model=None, retries=4):
    """Ask for a JSON object. If JSON mode fails (typically an EMPTY reply because a reasoning model
    used its whole token budget thinking), retry once without JSON mode and with a larger budget,
    then extract the JSON from the text."""
    try:
        return parse_json(invoke_with_retry(get_llm(json_mode=True, model=model), messages, retries).content)
    except Exception as error:
        if not any(t in str(error).lower() for t in _JSON_FAIL):
            raise
    llm = get_llm(json_mode=False, model=model, max_tokens=max(GROQ_MAX_TOKENS, 8000))
    return parse_json(invoke_with_retry(llm, messages, retries).content)


def parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    raise RuntimeError("The AI returned an unreadable response. Please try again.")
