# The Understanding Score™

The Understanding Score is MindBridge's core innovation: an estimate, from 0–100, of how
likely it is that a listener **actually understood** an instruction — derived from their
read-back, not assumed from a successful translation.

## Why a read-back?

Traditional translators stop at output. MindBridge closes the loop the way safe industrial
teams already do verbally: the listener repeats the instruction back, and the system checks
whether the repetition preserves the *critical* content.

## How the offline score is computed

The deterministic engine (`app/engine/understanding.py`) produces a fully **explainable**
score — every point traces to a named factor. The original instruction and the read-back are
each reduced to content tokens (stop-words removed) and to *entities* (capitalised
references like `Filter B`, acronyms like `LOTO`, and numbers).

| Factor | Weight | Computation |
|--------|:------:|-------------|
| **Key-point coverage** | 40% | Fraction of original content words echoed in the read-back. |
| **Entity coverage** | 25% | Fraction of equipment/part references retained. |
| **Confirmation language** | 15% | Presence of affirmation ("understood", "I will", "confirmed"). |
| **Conversational clarity** | 10% | Penalised by confusion signals ("what?", "repeat", "not sure"). |
| **Contextual consistency** | 10% | Penalised when the read-back invents entities/numbers absent from the original, or is implausibly short. |

```
score = Σ (factor_score × weight)        # clamped to [0, 100]
```

A read-back is considered **understood** when the score meets the configurable threshold
(`MINDBRIDGE_UNDERSTANDING_THRESHOLD`, default **70**).

## Worked example

> **Instruction:** "Replace Filter B before restarting the machine."

| Read-back | Score | Verdict |
|-----------|:-----:|---------|
| "Understood, I will replace Filter B before restarting the machine." | **100** | ✅ Verified |
| "Okay, I'll restart the machine." | **~36** | ❌ Missing the filter step & entity |
| "What? Can you repeat that?" | **<40** | ❌ Confusion detected |

When understanding is low, MindBridge returns a **follow-up** that names exactly what was
missed ("Please confirm you also caught: reference to 'Filter B'…") and requests
clarification before the task proceeds.

## The Claude-enhanced path

When `ANTHROPIC_API_KEY` is set, verification is delegated to `claude-opus-4-8`, which
reasons about paraphrase, partial understanding, and domain nuance that keyword overlap
cannot capture — while returning the **same JSON shape** (score, factors, missing points,
follow-up) so the UI and API contract are unchanged. If the call fails for any reason, the
engine falls back to the deterministic score.

## Design principles

- **Explainable** — never a black-box number; the breakdown is always shown.
- **Conservative on safety** — high-risk messages demand a read-back and a high score.
- **Deterministic offline** — identical inputs yield identical scores, which makes the
  system testable and auditable.
