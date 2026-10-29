# B10: overall-score weights.
#
# The three core pillars are weighted equally and grammar is a smaller quality
# signal, so a resume cannot score highly on formatting alone. The weights sum
# to 1.0 so `weights_used` reads as real percentages in the UI.
#
#   ats      0.30  format/ATS compatibility (tables, layout, contact, sections)
#   bullets  0.30  impact of the experience/project bullets (verbs, metrics)
#   keywords 0.30  coverage of the job description (weighted by B8)
#   grammar  0.10  spelling/typo quality
#
# If a component is unavailable (e.g. no job description was selected, or no
# bullets were parsed), it is dropped and the remaining weights are rescaled to
# sum to 1.0 -- an unavailable component is never treated as 100.
SCORE_WEIGHTS = {"ats": 0.30, "bullets": 0.30, "keywords": 0.30, "grammar": 0.10}


def compute_overall(scores: dict) -> tuple[float, dict]:
    """Return (overall_score, weights_actually_used). `None` values are treated as unavailable."""
    used = {k: w for k, w in SCORE_WEIGHTS.items() if scores.get(k) is not None}
    if not used:
        return 0.0, {}
    total_w = sum(used.values())
    overall = sum(scores[k] * w for k, w in used.items()) / total_w
    return round(overall, 1), {k: round(w / total_w, 3) for k, w in used.items()}
