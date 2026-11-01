"""Turn a speech transcript into a Polly roast or a José song request.

Polly only ever gets roast intents and José only ever gets song intents; anything
else (Polly asked to sing, José asked to roast, chatter) yields no intent.
Voice supplies only the *challenge* tag; adult_mode always comes from operator config.
"""
import re
from dataclasses import dataclass, field

from song_requests import normalize, strip_fillers

DEFAULT_POLLY_ALIASES = ['polly', 'poly', 'pauly', 'paulie', 'pollie', 'polley']
DEFAULT_JOSE_ALIASES = ['jose', 'josé', 'hosay', 'ho say', 'hose a']

INSULT = re.compile(r"\b(fuck|screw you|shut up|asshole|ass hole|bitch|you suck|sucks|stupid|idiot|dumb|"
                    r"ugly|hate you|go to hell|piss off|bite me|loser)\b")
REQUEST = re.compile(r"\b(roast|give me your worst|do your worst|insult me|insult us|make fun of|burn me|"
                     r"say something mean)\b")
CHALLENGE = re.compile(r"\b(come at me|bring it|try me|wanna cracker|want a cracker|bet you can ?t|"
                       r"you re not funny|youre not funny|you aren t funny)\b")
SONG_VERB = re.compile(r"\b(play|sing|put on|start)\b")


@dataclass(frozen=True)
class Intent:
    kind: str  # 'roast' | 'song'
    text: str
    tags: frozenset = field(default_factory=frozenset)
    song: dict | None = None
    random_song: bool = False


def _addressed(text, aliases):
    return any(re.search(rf"\b{re.escape(normalize(a))}\b", text) for a in aliases if normalize(a))


def roast_tags(text):
    tags = set()
    if INSULT.search(text):
        tags.add('direct_insult')
    if REQUEST.search(text):
        tags.add('roast_request')
    if CHALLENGE.search(text):
        # Taunts can draw from the larger roast_request pool too.
        tags.update({'roast_challenge', 'roast_request'})
    return frozenset(tags)


def song_query(text, aliases):
    """Words after the play/sing verb, with José's name and filler removed."""
    m = SONG_VERB.search(text)
    rest = text[m.end():] if m else ''
    for alias in aliases:
        rest = re.sub(rf"\b{re.escape(normalize(alias))}\b", ' ', rest)
    return strip_fillers(rest)


def parse_intent(transcript, catalog, polly_aliases=None, jose_aliases=None):
    text = normalize(transcript.replace("'", ' '))
    if not text:
        return None
    polly_aliases = polly_aliases or DEFAULT_POLLY_ALIASES
    jose_aliases = jose_aliases or DEFAULT_JOSE_ALIASES

    if _addressed(text, polly_aliases):
        tags = roast_tags(text)
        if tags:
            return Intent('roast', transcript, tags=tags)

    if _addressed(text, jose_aliases) and SONG_VERB.search(text):
        query = song_query(text, jose_aliases)
        if not query:
            return Intent('song', transcript, random_song=True)
        song = catalog.match(query)
        if song:
            return Intent('song', transcript, song=song)
    return None
