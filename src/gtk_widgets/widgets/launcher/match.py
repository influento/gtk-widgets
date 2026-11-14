"""Search matching for the launcher: tiers, secondary fields, ЙЦУКЕН keys.

Pure Python (no GTK) so it is cheap to test. A query matches a target's name
in one of five tiers, best first: exact, prefix, word start, substring, fuzzy
subsequence. Secondary fields (generic name, keywords, executable) match the
same way minus fuzzy, and rank just below a name match of the same tier.
"""

import re

EXACT, PREFIX, WORD, SUBSTR, FUZZY = range(5)

# Keys typed on the ru layout map to the Latin letter at the same position of
# the us layout, so "ашкуащч" (typed as f-i-r-e-f-o-x) finds Firefox.
_RU = "йцукенгшщзхъфывапролджэячсмитьбюё"
_US = "qwertyuiop[]asdfghjkl;'zxcvbnm,.`"
_RU_TO_US = str.maketrans(_RU, _US)

_SEPARATORS = re.compile(r"[\s\-_.,:;/\\|()\[\]{}]+")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def us_keys(text):
    """text with ЙЦУКЕН letters replaced by their us-layout Latin keys."""
    return text.translate(_RU_TO_US)


def query_variants(query):
    """The casefolded query, plus its us-layout mapping when that differs."""
    q = query.strip().casefold()
    if not q:
        return ()
    mapped = us_keys(q)
    return (q,) if mapped == q else (q, mapped)


class Field:
    """One searchable string, prepared once: casefolded, plus (on first use,
    it is the costly part for a long dmenu list) a copy where every word,
    after a separator or a camelCase bump, starts after a space."""

    __slots__ = ("text", "low", "_words")

    def __init__(self, text):
        self.text = text
        self.low = text.casefold()
        self._words = None

    @property
    def words(self):
        if self._words is None:
            self._words = " " + _SEPARATORS.sub(" ", _CAMEL.sub(" ", self.text)).casefold()
        return self._words


def _subsequence(q, s):
    pos = -1
    for ch in q:
        pos = s.find(ch, pos + 1)
        if pos < 0:
            return False
    return True


def tier(q, field, fuzzy=True):
    """Best tier q reaches in field, or None."""
    low = field.low
    if low == q:
        return EXACT
    if low.startswith(q):
        return PREFIX
    if " " + q in field.words:
        return WORD
    if q in low:
        return SUBSTR
    if fuzzy and _subsequence(q, low):
        return FUZZY
    return None


def rank(variants, name, extra=()):
    """Sort key of the best match (lower is better), or None. A name match of
    tier t ranks 2t, a secondary-field match 2t + 1."""
    best = None
    for q in variants:
        t = tier(q, name)
        if t is not None:
            key = 2 * t
        else:
            ts = [x for x in (tier(q, f, fuzzy=False) for f in extra) if x is not None]
            if not ts:
                continue
            key = 2 * min(ts) + 1
        if best is None or key < best:
            best = key
    return best
