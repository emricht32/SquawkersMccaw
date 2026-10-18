import json
import logging
import random
import re
import urllib.request

log = logging.getLogger("roast.brain")


def clean_reply(text: str, max_sentences: int) -> str:
    """Make LLM output safe for TTS: drop stage directions, emojis, and ramble."""
    text = re.sub(r"\*[^*]*\*", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"^\s*[A-Z]\w{0,19}:\s*", "", text)  # "Parrot: ..." speaker prefixes
    text = re.sub(r"[^\w\s.,!?'\-:;]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:max_sentences]).strip()


class RoastBrain:
    """Chat with an Ollama-served model (local or offloaded to another host)."""

    def __init__(self, llm_cfg: dict, persona_cfg: dict, bird_name: str, roast_notes: dict):
        host = llm_cfg.get("host", "http://localhost:11434").rstrip("/")
        if not host.startswith(("http://", "https://")):
            raise ValueError(f"llm.host must be an http(s) URL, got {host!r}")
        self.host = host
        self.model = llm_cfg["model"]
        self.timeout = float(llm_cfg.get("timeout", 30))
        self.history_turns = int(llm_cfg.get("history_turns", 6))
        self.max_sentences = int(llm_cfg.get("max_sentences", 2))
        self.keep_alive = llm_cfg.get("keep_alive", "60m")
        self.options = {
            "temperature": float(llm_cfg.get("temperature", 0.9)),
            "num_predict": int(llm_cfg.get("max_tokens", 60)),
        }
        self.system_prompt = persona_cfg["system_prompt"].format(name=bird_name)
        self.fallback_lines = persona_cfg.get("fallback_lines") or ["Squawk. I've got nothing, and neither do you."]
        self.roast_notes = roast_notes
        self.history: list[dict] = []
        # Ollama is local or on the LAN; never route it through an HTTP proxy.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            self.host + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self._opener.open(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def warm_up(self):
        """Load the model into RAM so the first roast isn't painfully slow."""
        try:
            self._post("/api/generate", {"model": self.model, "keep_alive": self.keep_alive})
            log.info("LLM %s warmed up on %s", self.model, self.host)
        except Exception as e:
            log.warning("LLM warm-up failed (%s); will retry on first request", e)

    def new_conversation(self):
        self.history = []

    def arrival_prompt(self, name: str | None) -> str:
        if not name:
            return "[SCENE: A stranger you don't recognize just walked up to you. Greet them with a roast.]"
        notes = self.roast_notes.get(name)
        about = f" What you know about them: {notes}." if notes else ""
        return f"[SCENE: {name} just walked up to you.{about} Greet them by name with a roast.]"

    def respond(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})
        self.history = self.history[-self.history_turns * 2:]
        messages = [{"role": "system", "content": self.system_prompt}] + self.history
        try:
            data = self._post(
                "/api/chat",
                {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": self.keep_alive,
                    "options": self.options,
                },
            )
            reply = clean_reply(data.get("message", {}).get("content", ""), self.max_sentences)
        except Exception as e:
            log.warning("LLM request failed: %s", e)
            reply = ""
        if not reply:
            reply = random.choice(self.fallback_lines)
        self.history.append({"role": "assistant", "content": reply})
        log.info("Heard: %r -> Reply: %r", user_text, reply)
        return reply
