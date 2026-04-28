"""
core/pairing_algorithm.py
─────────────────────────────────────────────────────────────
Image-Fragment Pairing Algorithm
Comp 401 Final Project | Larona Lusindo Lentswe

Overview
--------
For each carrier image, every remaining unassigned fragment is
trial-embedded using LSB. The resulting stego image is compared
to the original carrier using PSNR and SSIM. A composite grade
is computed and the fragment with the best grade is permanently
assigned to that carrier. This greedy approach ensures each
carrier receives the fragment that causes the least perceptible
distortion.

Grading Formula
---------------
    grade = (w_psnr * norm_psnr) + (w_ssim * norm_ssim) + (w_kl * norm_kl)

    where:
        norm_psnr = min(psnr, PSNR_CAP) / PSNR_CAP   (0–1, higher = better)
        norm_ssim = (ssim + 1) / 2                    (0–1, ssim in [-1,1])
        norm_kl   = 1 / (1 + kl_divergence)           (0–1, lower KL = higher score)
        w_psnr    = 0.25  — perceptual signal quality
        w_ssim    = 0.45  — structural/perceptual similarity
        w_kl      = 0.30  — statistical undetectability (higher weight = stealth focus)

    KL Divergence rationale
    -----------------------
    KL divergence measures how much the pixel histogram distribution shifts
    after embedding. A shift toward zero means the stego image is statistically
    indistinguishable from the original — the core requirement for undetectability.
    It is computed per RGB channel and averaged, giving a single scalar that
    directly reflects how much the embedding disturbs the image's natural
    pixel distribution.

Public API
----------
grade_pairing(carrier_path, fragment, psnr_cap) -> dict
pair_fragments_to_carriers(carriers, fragments, progress_queue) -> list[dict]
"""

import io
import base64
import numpy as np
from PIL import Image
from stegano import lsb
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

# ── Grading weights (must sum to 1.0)
W_PSNR   = 0.25   # perceptual signal quality
W_SSIM   = 0.45   # structural/perceptual similarity
W_KL     = 0.30   # statistical undetectability
PSNR_CAP = 60.0   # dB ceiling for normalisation (beyond this is imperceptible)
KL_BINS  = 256    # histogram bins per channel (0–255 pixel values)


# ─────────────────────────────────────────────
#  ENCODE FRAGMENT  (mirrors embed_engine.py)
# ─────────────────────────────────────────────
def _encode_fragment(frag: dict) -> str:
    """Encode a fragment dict into an LSB-embeddable string."""
    b64_data = base64.b64encode(frag["data"]).decode("utf-8")
    return "|".join([
        b64_data,
        frag["original_hash"],
        frag["original_name"],
        str(frag["index"]),
        str(frag["total"]),
    ])


# ─────────────────────────────────────────────
#  TRIAL EMBED  (in-memory, no file written)
# ─────────────────────────────────────────────
def _trial_embed(carrier_path: str, fragment: dict) -> Image.Image | None:
    """
    LSB-embed a fragment into a carrier image entirely in memory.
    Returns the stego PIL Image, or None on failure.
    """
    try:
        payload     = _encode_fragment(fragment)
        stego_img   = lsb.hide(carrier_path, payload)
        return stego_img
    except Exception:
        return None


# ─────────────────────────────────────────────
#  PIL IMAGE → NUMPY ARRAY
# ─────────────────────────────────────────────
def _to_array(img: Image.Image) -> np.ndarray:
    """Convert a PIL Image to a uint8 numpy array (RGB)."""
    return np.array(img.convert("RGB"), dtype=np.uint8)


# ─────────────────────────────────────────────
#  KL DIVERGENCE
# ─────────────────────────────────────────────
def _kl_divergence(original_arr: np.ndarray, stego_arr: np.ndarray) -> float:
    """
    Compute the mean KL divergence between the pixel histogram distributions
    of the original carrier and the stego image, averaged across RGB channels.

    KL(P || Q) = sum(P * log(P / Q))

    where:
        P = normalised pixel histogram of the original carrier channel
        Q = normalised pixel histogram of the stego image channel

    A value close to 0 means the stego distribution is statistically
    indistinguishable from the original — the ideal outcome for stealth.

    A small epsilon is added to both histograms to prevent log(0) errors
    on channels with sparse pixel values.
    """
    epsilon = 1e-10
    kl_per_channel = []

    for ch in range(3):  # R, G, B
        p_hist, _ = np.histogram(
            original_arr[:, :, ch].flatten(),
            bins=KL_BINS, range=(0, 255), density=True
        )
        q_hist, _ = np.histogram(
            stego_arr[:, :, ch].flatten(),
            bins=KL_BINS, range=(0, 255), density=True
        )

        # Add epsilon to avoid division by zero and log(0)
        p = p_hist + epsilon
        q = q_hist + epsilon

        # Normalise to valid probability distributions
        p = p / p.sum()
        q = q / q.sum()

        kl = float(np.sum(p * np.log(p / q)))
        kl_per_channel.append(kl)

    return float(np.mean(kl_per_channel))


# ─────────────────────────────────────────────
#  GRADE A SINGLE PAIRING
# ─────────────────────────────────────────────
def grade_pairing(
    carrier_path: str,
    fragment: dict,
    psnr_cap: float = PSNR_CAP,
) -> dict:
    """
    Trial-embed one fragment into one carrier and return a grade report.

    Returns a dict:
        fragment_index : int
        psnr           : float  (dB,  higher = better)
        ssim           : float  (0–1, higher = better)
        kl_divergence  : float  (≥0,  lower  = better — closer to 0 = more undetectable)
        norm_psnr      : float  (0–1 normalised)
        norm_ssim      : float  (0–1 normalised)
        norm_kl        : float  (0–1 normalised, inverted so higher = better)
        grade          : float  (0–1 composite score)
        success        : bool
        error          : str | None
    """
    result = {
        "fragment_index": fragment["index"],
        "psnr":           0.0,
        "ssim":           0.0,
        "kl_divergence":  0.0,
        "norm_psnr":      0.0,
        "norm_ssim":      0.0,
        "norm_kl":        0.0,
        "grade":          0.0,
        "success":        False,
        "error":          None,
    }

    # ── Load original carrier
    try:
        original_img = Image.open(carrier_path).convert("RGB")
        original_arr = _to_array(original_img)
    except Exception as e:
        result["error"] = f"Cannot open carrier: {e}"
        return result

    # ── Trial embed
    stego_img = _trial_embed(carrier_path, fragment)
    if stego_img is None:
        result["error"] = "LSB embed failed (payload too large for carrier?)"
        return result

    stego_arr = _to_array(stego_img)

    # ── PSNR
    try:
        psnr = peak_signal_noise_ratio(original_arr, stego_arr, data_range=255)
        # psnr can be inf if images are identical (shouldn't happen but guard it)
        if np.isinf(psnr):
            psnr = psnr_cap
    except Exception as e:
        result["error"] = f"PSNR computation failed: {e}"
        return result

    # ── SSIM  (multichannel across RGB)
    try:
        ssim = structural_similarity(
            original_arr, stego_arr,
            data_range=255,
            channel_axis=2,       # RGB channels
        )
    except Exception as e:
        result["error"] = f"SSIM computation failed: {e}"
        return result

    # ── Normalise
    norm_psnr = min(psnr, psnr_cap) / psnr_cap          # 0–1
    norm_ssim = (ssim + 1.0) / 2.0                       # map [-1,1] → [0,1]

    # ── KL Divergence
    try:
        kl = _kl_divergence(original_arr, stego_arr)
    except Exception as e:
        result["error"] = f"KL divergence computation failed: {e}"
        return result

    # Normalise KL: invert so that lower KL → higher score
    # Using 1 / (1 + kl) maps [0, ∞) → (0, 1]
    # KL=0 → norm_kl=1.0 (perfect, undetectable)
    # KL=1 → norm_kl=0.5
    # KL→∞ → norm_kl→0
    norm_kl = 1.0 / (1.0 + kl)

    # ── Composite grade
    grade = (W_PSNR * norm_psnr) + (W_SSIM * norm_ssim) + (W_KL * norm_kl)

    result.update({
        "psnr":          round(psnr,      4),
        "ssim":          round(ssim,      6),
        "kl_divergence": round(kl,        8),
        "norm_psnr":     round(norm_psnr, 4),
        "norm_ssim":     round(norm_ssim, 4),
        "norm_kl":       round(norm_kl,   6),
        "grade":         round(grade,     6),
        "success":       True,
        "error":         None,
    })
    return result


# ─────────────────────────────────────────────
#  MAIN PAIRING ALGORITHM
# ─────────────────────────────────────────────
def pair_fragments_to_carriers(
    carriers:        list[str],
    fragments:       list[dict],
    progress_queue,
) -> list[dict]:
    """
    Greedy image-fragment pairing using PSNR + SSIM grading.

    For each carrier (in order):
        1. Trial-embed every remaining fragment into it
        2. Grade each trial
        3. Assign the fragment with the highest grade to that carrier
        4. Remove that fragment from the pool

    Parameters
    ----------
    carriers        : list of carrier image file paths
    fragments       : list of fragment dicts (from fragment_manager)
    progress_queue  : queue for GUI progress updates

    Returns
    -------
    List of assignment dicts, one per carrier, in carrier order:
        {
            carrier_path   : str
            carrier_name   : str
            fragment_index : int
            fragment       : dict        (the assigned fragment dict)
            psnr           : float
            ssim           : float
            grade          : float
            all_grades     : list[dict]  (grades for every trial on this carrier)
        }
    Returns empty list on error.
    """
    if not carriers:
        progress_queue.put(("error", 0, "No carrier images provided."))
        return []

    if not fragments:
        progress_queue.put(("error", 0, "No fragments provided."))
        return []

    if len(carriers) < len(fragments):
        progress_queue.put(("error", 0,
            f"Not enough carriers ({len(carriers)}) for fragments ({len(fragments)})."))
        return []

    import os
    n_carriers  = len(carriers)
    n_fragments = len(fragments)
    total_steps = n_carriers * n_fragments   # worst case trials

    progress_queue.put(("progress", 2,
        f"Starting pairing:  {n_fragments} fragment(s)  ×  {n_carriers} carrier(s)…"))

    remaining = list(fragments)   # pool of unassigned fragments
    assignments = []
    trials_done = 0

    for ci, carrier_path in enumerate(carriers):

        # If no fragments left, remaining carriers get no assignment
        if not remaining:
            break

        carrier_name = os.path.basename(carrier_path)
        progress_queue.put(("progress",
            int(5 + 85 * ci / n_carriers),
            f"Carrier {ci + 1}/{n_carriers}  [{carrier_name}]  "
            f"— grading {len(remaining)} candidate fragment(s)…"))

        all_grades = []

        # ── Grade every remaining fragment against this carrier
        for frag in remaining:
            trials_done += 1
            report = grade_pairing(carrier_path, frag)

            all_grades.append({
                "fragment_index": frag["index"],
                "psnr":           report["psnr"],
                "ssim":           report["ssim"],
                "kl_divergence":  report["kl_divergence"],
                "norm_kl":        report["norm_kl"],
                "grade":          report["grade"],
                "success":        report["success"],
                "error":          report.get("error"),
            })

            status = (
                f"  frag[{frag['index']}] → "
                f"PSNR={report['psnr']:.2f} dB  "
                f"SSIM={report['ssim']:.4f}  "
                f"KL={report['kl_divergence']:.6f}  "
                f"grade={report['grade']:.4f}"
                if report["success"]
                else f"  frag[{frag['index']}] → FAILED: {report['error']}"
            )
            progress_queue.put(("progress",
                int(5 + 85 * ci / n_carriers),
                status))

        # ── Select best graded fragment (highest composite score)
        successful = [g for g in all_grades if g["success"]]

        if not successful:
            progress_queue.put(("error", 0,
                f"All fragment trials failed for carrier: {carrier_name}"))
            return []

        best = max(successful, key=lambda g: g["grade"])
        best_frag = next(f for f in remaining if f["index"] == best["fragment_index"])

        assignments.append({
            "carrier_path":   carrier_path,
            "carrier_name":   carrier_name,
            "fragment_index": best["fragment_index"],
            "fragment":       best_frag,
            "psnr":           best["psnr"],
            "ssim":           best["ssim"],
            "kl_divergence":  best["kl_divergence"],
            "grade":          best["grade"],
            "all_grades":     all_grades,
        })

        progress_queue.put(("progress",
            int(5 + 85 * (ci + 1) / n_carriers),
            f"  ✓ Assigned frag[{best['fragment_index']}] → {carrier_name}  "
            f"(grade={best['grade']:.4f}  "
            f"PSNR={best['psnr']:.2f} dB  "
            f"SSIM={best['ssim']:.4f}  "
            f"KL={best['kl_divergence']:.6f})"))

        # ── Remove assigned fragment from pool
        remaining = [f for f in remaining if f["index"] != best["fragment_index"]]

    progress_queue.put(("progress", 92,
        f"Pairing complete — {len(assignments)} assignment(s) made."))

    # ── Summary log
    progress_queue.put(("progress", 94, "─── Pairing Summary ───"))
    for a in assignments:
        progress_queue.put(("progress", 94,
            f"  {a['carrier_name']}  ←  frag[{a['fragment_index']}]  "
            f"grade={a['grade']:.4f}"))

    return assignments


# ─────────────────────────────────────────────
#  GRADE TABLE HELPER  (for logging/reporting)
# ─────────────────────────────────────────────
def format_grade_table(assignments: list[dict]) -> str:
    """
    Return a formatted string table of all pairing grades.
    Useful for logging or displaying in the GUI log box.
    """
    lines = []
    lines.append(
        f"{'Carrier':<30} {'Frag':>5} {'PSNR (dB)':>10} "
        f"{'SSIM':>8} {'KL Div':>12} {'Grade':>8}"
    )
    lines.append("─" * 78)
    for a in assignments:
        lines.append(
            f"{a['carrier_name']:<30} "
            f"{a['fragment_index']:>5} "
            f"{a['psnr']:>10.4f} "
            f"{a['ssim']:>8.6f} "
            f"{a['kl_divergence']:>12.8f} "
            f"{a['grade']:>8.6f}"
        )
    lines.append("─" * 78)
    avg_grade = sum(a["grade"]         for a in assignments) / len(assignments) if assignments else 0
    avg_psnr  = sum(a["psnr"]          for a in assignments) / len(assignments) if assignments else 0
    avg_ssim  = sum(a["ssim"]          for a in assignments) / len(assignments) if assignments else 0
    avg_kl    = sum(a["kl_divergence"] for a in assignments) / len(assignments) if assignments else 0
    lines.append(
        f"{'AVERAGE':<30} {'':>5} "
        f"{avg_psnr:>10.4f} "
        f"{avg_ssim:>8.6f} "
        f"{avg_kl:>12.8f} "
        f"{avg_grade:>8.6f}"
    )
    lines.append("")
    lines.append(
        "  KL interpretation:  < 0.0001 = statistically undetectable  |  "
        "> 0.001 = detectable distribution shift"
    )
    return "\n".join(lines)