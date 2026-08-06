"""Versioned password grammars for generating and attacking passwords."""

from __future__ import annotations

GRAMMAR_VERSION = "1.0"

SHARED_WORDS = (
    "tiger",
    "orbit",
    "cobalt",
    "harbor",
    "ember",
    "signal",
    "vector",
    "comet",
    "meadow",
    "lantern",
    "quartz",
    "falcon",
)

HELD_OUT_WORDS = (
    "crimson",
    "velvet",
    "horizon",
    "nebula",
)

SYMBOLS = "!@#$%&*?"

COMMON_PASSWORDS = (
    "password",
    "123456",
    "qwerty",
    "admin",
    "welcome",
    "letmein",
    "dragon",
    "tiger",
    "orbit",
    "cobalt",
    "harbor",
    "ember",
)
