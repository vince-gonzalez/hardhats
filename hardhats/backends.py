"""
hardHats model layer - one chat() over a federation of free backends.

Gemini (native) plus a set of OpenAI-compatible endpoints - Groq, OpenRouter,
Ollama, Cloudflare Workers AI, Mistral, Cohere and more - behind a single
chat(backend, prompt) call, so a crew can wear a different model on every hat.
Keys are read from the environment, or failing that the Windows user settings
that `setx` writes, and are NEVER printed. Standard library only; nothing is
pip-installed into the host environment. Add a key, gain a perspective.

  python -m hardhats.backends          # smoke-test which backends answer
"""
import json
import os
import time
import urllib.error
import urllib.request

# --- keys: environment first, then HKCU\Environment (what setx writes) ---------


def read_key(name: str) -> str | None:
    key = os.environ.get(name)
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0] or None
    except (ImportError, OSError, FileNotFoundError):
        return None


# --- backend registry ----------------------------------------------------------
# kind "gemini" uses Google's native API; "openai" uses the chat/completions
# shape that Groq, OpenRouter and Ollama all speak. Models are candidates: the
# smoke test reports which resolve, so no name is trusted without a check.
BACKENDS: dict[str, dict] = {
    "gemini": {
        "kind": "gemini", "key_env": "GEMINI_API_KEY",
        "models": ["gemini-flash-lite-latest", "gemini-3.5-flash"],
    },
    "groq": {
        "kind": "openai", "base": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY",
        # Live on this account's free tier 2026-10-16. gpt-oss is OpenAI's open model.
        "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
    },
    "openrouter": {
        "kind": "openai", "base": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY",
        # Live :free ids 2026-10-16 (OpenRouter rotates these; refresh from /models).
        "models": ["google/gemma-4-31b-it:free", "nvidia/nemotron-3-super-120b-a12b:free",
                   "google/gemma-4-26b-a4b-it:free"],
    },
    "ollama": {
        "kind": "openai", "base": "http://localhost:11434/v1", "key_env": None,
        "models": ["llama3.2", "qwen2.5"],
    },
    # --- additional free perspectives (OpenAI-compatible); add keys to enable ---
    "github": {  # GitHub Models: free frontier (GPT-4o, Llama) via a GitHub PAT
        "kind": "openai", "base": "https://models.github.ai/inference", "key_env": "GITHUB_MODELS_TOKEN",
        "models": ["openai/gpt-4o-mini", "openai/gpt-4o", "meta/Llama-3.3-70B-Instruct"],
    },
    "cloudflare": {  # Workers AI; base carries the account id, filled from env
        "kind": "openai", "base": "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/v1",
        "key_env": "CLOUDFLARE_API_TOKEN",
        "models": ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/openai/gpt-oss-120b"],
    },
    "cerebras": {
        "kind": "openai", "base": "https://api.cerebras.ai/v1", "key_env": "CEREBRAS_API_KEY",
        "models": ["llama-3.3-70b", "llama3.1-8b"],
    },
    "mistral": {
        "kind": "openai", "base": "https://api.mistral.ai/v1", "key_env": "MISTRAL_API_KEY",
        "models": ["mistral-small-latest", "open-mistral-nemo"],
    },
    "nvidia": {  # NIM: key valid, but the OpenAI-compat endpoint rejects its own
        # catalog ids (404/410) on this tier; deepseek-flash is reachable but slow.
        "kind": "openai", "base": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY",
        "models": ["deepseek-ai/deepseek-v4.1-flash"],
    },
    "sambanova": {  # key valid; returns 402 until the account is activated in the console
        "kind": "openai", "base": "https://api.sambanova.ai/v1", "key_env": "SAMBANOVA_API_KEY",
        "models": ["Meta-Llama-3.3-70B-Instruct", "gpt-oss-120b"],
    },
    "cohere": {  # non-commercial free tier - perspective/research only, not paid products
        "kind": "openai", "base": "https://api.cohere.ai/compatibility/v1", "key_env": "COHERE_API_KEY",
        # Live 2026-10-17 on this account's compat endpoint.
        "models": ["command-a-03-2025", "c4ai-aya-expanse-32b"],
    },
}


# A real browser User-Agent: Groq (and other Cloudflare-fronted APIs) answer 403
# "error 1010" to urllib's default agent. This is the same bot-screen seen on the
# worker's /verify. Sending a normal UA clears it.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")


def _post(url: str, body: bytes, headers: dict, timeout: int = 120) -> dict:
    headers = {"user-agent": UA, **headers}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _openai_chat(base: str, key: str | None, model: str, prompt: str,
                 temperature: float, max_tokens: int) -> str:
    headers = {"content-type": "application/json"}
    if key:
        headers["authorization"] = f"Bearer {key}"
    if "openrouter" in base:  # optional attribution headers OpenRouter asks for
        headers["HTTP-Referer"] = "https://coldhat.f-keys.com"
        headers["X-Title"] = "coldHat atom study"
    body = json.dumps({
        "model": model, "temperature": temperature, "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    data = _post(base + "/chat/completions", body, headers)
    msg = data["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning") or ""


def _gemini_chat(key: str, model: str, prompt: str,
                 temperature: float, max_tokens: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }).encode()
    data = _post(url, body, {"content-type": "application/json", "x-goog-api-key": key})
    return data["candidates"][0]["content"]["parts"][0]["text"]


def chat(backend: str, prompt: str, model: str | None = None,
         temperature: float = 0.0, max_tokens: int = 700,
         attempts: int = 4) -> str:
    """One completion. Falls back across the backend's candidate models on a
    bad-model error; waits out rate limits across `attempts` tries. Raises
    RuntimeError on total failure. Pass attempts=1 to fail fast (no backoff) -
    a council that spans many backends would rather roll to the next model than
    sit through a free-tier 429."""
    spec = BACKENDS[backend]
    key = read_key(spec["key_env"]) if spec["key_env"] else None
    if spec["key_env"] and not key:
        raise RuntimeError(f"{backend}: {spec['key_env']} is not set")
    base = spec.get("base", "")
    if "{acct}" in base:
        acct = read_key("CLOUDFLARE_ACCOUNT_ID")
        if not acct:
            raise RuntimeError(f"{backend}: CLOUDFLARE_ACCOUNT_ID is not set")
        base = base.replace("{acct}", acct)
    models = [model] if model else spec["models"]
    last = ""
    for m in models:
        for attempt in range(attempts):
            try:
                if spec["kind"] == "gemini":
                    return _gemini_chat(key, m, prompt, temperature, max_tokens)
                return _openai_chat(base, key, m, prompt, temperature, max_tokens)
            except urllib.error.HTTPError as e:
                last = f"{backend}/{m} HTTP {e.code}"
                if e.code in (429, 500, 502, 503) and attempt < attempts - 1:
                    time.sleep(12 * (attempt + 1))
                    continue
                break  # 400/401/404 -> try the next candidate model
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                last = f"{backend}/{m} unreadable: {e}"
                break
            except (TimeoutError, urllib.error.URLError) as e:
                last = f"{backend}/{m} no answer: {type(e).__name__}"
                if attempt < attempts - 1:
                    time.sleep(8)
                    continue
                break
    raise RuntimeError(last or f"{backend}: all models failed")


def smoke() -> None:
    """One tiny call per backend; reports which backend/model pair answers."""
    for name, spec in BACKENDS.items():
        key_ok = not spec["key_env"] or read_key(spec["key_env"])
        if not key_ok:
            print(f"  {name:11} SKIP  ({spec['key_env']} not set)")
            continue
        try:
            t0 = time.time()
            reply = chat(name, "Reply with exactly: OK", max_tokens=10)
            dt = time.time() - t0
            print(f"  {name:11} OK    {dt:4.1f}s  reply={reply.strip()[:30]!r}")
        except Exception as e:  # noqa: BLE001 - report, don't crash the sweep
            print(f"  {name:11} FAIL  {e}")


if __name__ == "__main__":
    print("backends smoke test (one call each):")
    smoke()
