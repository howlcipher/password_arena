import random

from password_arena.attacker import AdaptiveAttacker, AttackContext, PassphraseStrategy
from password_arena.grammars import HELD_OUT_WORDS, SHARED_WORDS


def test_passphrase_candidates_reachable():
    """Prove that benchmark cases (e.g. 4-word passphrases with 3-digit suffix) are reachable."""
    # We restrict the words to a small set so the iterator exhausts quickly
    words = ("tiger", "orbit", "cobalt", "harbor")
    
    ctx = AttackContext(password_length=30, known_words=words, rng=random.Random())
    strat = PassphraseStrategy()
    candidates = strat.candidates(ctx)
    
    target = "tiger-orbit-cobalt-harbor456"
    
    # 'in' consumes the iterator until it finds the target or exhausts
    assert target in candidates, f"Target {target} should be reachable by attacker grammar"


def test_held_out_cases_novel():
    """Prove that held-out cases remain genuinely novel to the attacker."""
    rng = random.Random(42)
    attacker = AdaptiveAttacker(rng)
    
    # Create a password using a held-out word
    password_with_held_out = f"{HELD_OUT_WORDS[0]}-{SHARED_WORDS[0]}-{SHARED_WORDS[1]}123"
    
    # Even with a large guess budget, the attacker should fail because it doesn't know the word
    result = attacker.attack(password_with_held_out, difficulty=5, max_guesses=100000)
    assert not result.solved, "Attacker should not solve passphrases using held-out words"
