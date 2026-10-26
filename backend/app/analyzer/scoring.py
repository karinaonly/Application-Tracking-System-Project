# Score weights. If a component is unavailable (e.g. no job description was selected,
# or no bullets were parsed), it is dropped and the remaining weights are rescaled to sum to 1.0.
SCORE_WEIGHTS = {"ats": 0.35, "bullets": 0.35, "keywords": 0.30}


def compute_overall(scores: dict) -> tuple[float, dict]:
    """Return (overall_score, weights_actually_used). `None` values are treated as unavailable."""
    used = {k: w for k, w in SCORE_WEIGHTS.items() if scores.get(k) is not None}
    if not used:
        return 0.0, {}
    total_w = sum(used.values())
    overall = sum(scores[k] * w for k, w in used.items()) / total_w
    return round(overall, 1), {k: round(w / total_w, 3) for k, w in used.items()}
