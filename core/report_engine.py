"""
core/report_engine.py
─────────────────────────────────────────────────────────────
Steganalysis Report Engine
Comp 401 Final Project | Larona Lusindo Lentswe

Reads a manifest.json and the corresponding stego images,
locates the original carrier images, and recomputes all
metrics (PSNR, SSIM) independently —
verifying the grades recorded at embed time.

Public API
----------
generate_report(manifest_path, carrier_folder, progress_queue) -> dict
"""

import os
import json
import numpy as np
from PIL import Image
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


# ── Thresholds for interpretation labels
THRESHOLDS = {
    "psnr":  {"excellent": 55,   "good": 45,   "poor": 35},
    "ssim":  {"excellent": 0.999,"good": 0.995,"poor": 0.98},
}


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def _to_array(img: Image.Image) -> np.ndarray:
    return np.array(img.convert("RGB"), dtype=np.uint8)


def _compute_psnr(orig: np.ndarray, stego: np.ndarray) -> float:
    val = peak_signal_noise_ratio(orig, stego, data_range=255)
    return float(min(val, 999.0)) if not np.isinf(val) else 999.0


def _compute_ssim(orig: np.ndarray, stego: np.ndarray) -> float:
    return float(structural_similarity(
        orig, stego, data_range=255, channel_axis=2
    ))


def _grade_label(metric: str, value: float) -> str:
    t = THRESHOLDS[metric]
    if value >= t["excellent"]: return "Excellent"
    if value >= t["good"]:      return "Good"
    if value >= t["poor"]:      return "Poor"
    return "Unacceptable"


# ─────────────────────────────────────────────
#  MAIN REPORT GENERATOR
# ─────────────────────────────────────────────
def generate_report(
    manifest_path:  str,
    carrier_folder: str,
    progress_queue,
) -> dict:
    """
    Generate a full steganalysis report from a manifest + carrier folder.

    Parameters
    ----------
    manifest_path  : path to manifest.json (inside the stego output folder)
    carrier_folder : path to the folder containing the original carrier images
    progress_queue : queue for GUI progress updates

    Returns
    -------
    Report dict:
    {
        "original_name"   : str,
        "original_hash"   : str,
        "total_fragments" : int,
        "pairing_method"  : str,
        "per_fragment"    : list[dict],   # one entry per fragment
        "summary"         : dict,         # averages + overall grade
        "error"           : str | None,
    }
    """
    stego_folder = os.path.dirname(manifest_path)

    report = {
        "original_name":   "",
        "original_hash":   "",
        "total_fragments": 0,
        "pairing_method":  "",
        "per_fragment":    [],
        "summary":         {},
        "error":           None,
    }

    # ── Load manifest
    progress_queue.put(("progress", 2, "Loading manifest…"))
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except Exception as e:
        report["error"] = f"Cannot read manifest: {e}"
        progress_queue.put(("error", 0, report["error"]))
        return report

    report["original_name"]   = manifest.get("original_name", "unknown")
    report["original_hash"]   = manifest.get("original_hash", "")
    report["total_fragments"] = manifest.get("total_fragments", 0)
    report["pairing_method"]  = manifest.get("pairing_method", "unknown")
    entries                   = manifest.get("fragments", [])

    if not entries:
        report["error"] = "Manifest contains no fragment entries."
        progress_queue.put(("error", 0, report["error"]))
        return report

    progress_queue.put(("progress", 8,
        f"Manifest loaded — {len(entries)} fragment(s) to analyse…"))

    # ── Process each fragment
    per_fragment = []
    n = len(entries)

    for i, entry in enumerate(entries):
        frag_index   = entry.get("fragment_index", i)
        stego_file   = entry.get("stego_file", "")
        carrier_src  = entry.get("carrier_source", "")

        stego_path   = os.path.join(stego_folder, stego_file)
        carrier_path = os.path.join(carrier_folder, carrier_src)

        pct = 10 + int(80 * (i + 1) / n)
        progress_queue.put(("progress", pct,
            f"Analysing fragment {i + 1}/{n}  [{stego_file}]…"))

        frag_result = {
            "fragment_index":   frag_index,
            "stego_file":       stego_file,
            "carrier_source":   carrier_src,
            "psnr":             None,
            "ssim":             None,
            "psnr_label":       None,
            "ssim_label":       None,
            # Recorded grades from embed time (from manifest)
            "recorded_psnr":    entry.get("psnr"),
            "recorded_ssim":    entry.get("ssim"),
            "recorded_grade":   entry.get("grade"),
            "error":            None,
        }

        # ── Validate paths
        if not os.path.isfile(stego_path):
            frag_result["error"] = f"Stego file not found: {stego_file}"
            per_fragment.append(frag_result)
            progress_queue.put(("progress", pct,
                f"  ✗ Skipped — stego file missing"))
            continue

        if not os.path.isfile(carrier_path):
            frag_result["error"] = (
                f"Original carrier not found: {carrier_src}\n"
                f"Searched in: {carrier_folder}"
            )
            per_fragment.append(frag_result)
            progress_queue.put(("progress", pct,
                f"  ✗ Skipped — original carrier missing"))
            continue

        # ── Load images
        try:
            orig_img  = Image.open(carrier_path).convert("RGB")
            stego_img = Image.open(stego_path).convert("RGB")
            orig_arr  = _to_array(orig_img)
            stego_arr = _to_array(stego_img)
        except Exception as e:
            frag_result["error"] = f"Image load failed: {e}"
            per_fragment.append(frag_result)
            continue

        # ── Resize stego to match carrier if dimensions differ
        if orig_arr.shape != stego_arr.shape:
            stego_img = stego_img.resize(orig_img.size, Image.LANCZOS)
            stego_arr = _to_array(stego_img)

        # ── Compute metrics
        try:
            psnr = _compute_psnr(orig_arr, stego_arr)
            ssim = _compute_ssim(orig_arr, stego_arr)

            frag_result.update({
                "psnr":          round(psnr, 4),
                "ssim":          round(ssim, 6),
                "psnr_label":    _grade_label("psnr", psnr),
                "ssim_label":    _grade_label("ssim", ssim),
            })

            progress_queue.put(("progress", pct,
                f"  PSNR={psnr:.2f} dB  SSIM={ssim:.4f}"))

        except Exception as e:
            frag_result["error"] = f"Metric computation failed: {e}"

        per_fragment.append(frag_result)

    # ── Summary statistics
    progress_queue.put(("progress", 92, "Computing summary statistics…"))

    valid = [f for f in per_fragment if f["psnr"] is not None]

    if valid:
        avg_psnr = np.mean([f["psnr"] for f in valid])
        avg_ssim = np.mean([f["ssim"] for f in valid])

        # Overall verdict based on PSNR and SSIM
        if avg_psnr >= THRESHOLDS["psnr"]["excellent"] and avg_ssim >= THRESHOLDS["ssim"]["excellent"]:
            verdict = "EXCELLENT QUALITY"
            verdict_color = "green"
        elif avg_psnr >= THRESHOLDS["psnr"]["good"] and avg_ssim >= THRESHOLDS["ssim"]["good"]:
            verdict = "GOOD QUALITY"
            verdict_color = "cyan"
        elif avg_psnr >= THRESHOLDS["psnr"]["poor"] and avg_ssim >= THRESHOLDS["ssim"]["poor"]:
            verdict = "ACCEPTABLE QUALITY"
            verdict_color = "orange"
        else:
            verdict = "POOR QUALITY"
            verdict_color = "red"

        report["summary"] = {
            "avg_psnr":        round(float(avg_psnr), 4),
            "avg_ssim":        round(float(avg_ssim), 6),
            "fragments_ok":    len(valid),
            "fragments_err":   len(per_fragment) - len(valid),
            "verdict":         verdict,
            "verdict_color":   verdict_color,
        }

        progress_queue.put(("progress", 96,
            f"Overall verdict: {verdict}"))
        progress_queue.put(("progress", 96,
            f"Avg PSNR={avg_psnr:.2f} dB  SSIM={avg_ssim:.4f}"))
    else:
        report["summary"] = {"verdict": "NO DATA", "verdict_color": "red"}

    report["per_fragment"] = per_fragment
    progress_queue.put(("progress", 100, "Report complete ✓"))
    progress_queue.put(("done", None, None))
    return report