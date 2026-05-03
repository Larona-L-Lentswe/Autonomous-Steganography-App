"""
core/report_engine.py
─────────────────────────────────────────────────────────────
Steganalysis Report Engine
Comp 401 Final Project | Larona Lusindo Lentswe

Reads a manifest.json and the corresponding stego images,
locates the original carrier images, and recomputes all
metrics (PSNR, SSIM, KL Divergence, BER) independently —
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
    "kl":    {"excellent": 0.0001,"good": 0.001,"poor": 0.01},
    "ber":   {"excellent": 0.001, "good": 0.005,"poor": 0.02},
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


def _compute_kl(orig: np.ndarray, stego: np.ndarray) -> float:
    epsilon = 1e-10
    kl_channels = []
    for ch in range(3):
        p, _ = np.histogram(orig[:, :, ch].flatten(),
                            bins=256, range=(0, 255), density=True)
        q, _ = np.histogram(stego[:, :, ch].flatten(),
                            bins=256, range=(0, 255), density=True)
        p = (p + epsilon) / (p + epsilon).sum()
        q = (q + epsilon) / (q + epsilon).sum()
        kl_channels.append(float(np.sum(p * np.log(p / q))))
    return float(np.mean(kl_channels))


def _compute_ber(orig: np.ndarray, stego: np.ndarray) -> float:
    orig_bits  = np.unpackbits(orig.flatten())
    stego_bits = np.unpackbits(stego.flatten())
    return float(np.sum(orig_bits != stego_bits) / len(orig_bits))


def _embedding_rate(fragment_bytes: int, image_pixels: int) -> float:
    """Bits per pixel (bpp) — payload bits / available pixel bits."""
    payload_bits = fragment_bytes * 8
    pixel_bits   = image_pixels * 3   # 3 channels
    return payload_bits / pixel_bits


def _grade_label(metric: str, value: float) -> str:
    t = THRESHOLDS[metric]
    if metric in ("psnr", "ssim"):
        if value >= t["excellent"]: return "Excellent"
        if value >= t["good"]:      return "Good"
        if value >= t["poor"]:      return "Poor"
        return "Unacceptable"
    else:  # kl, ber — lower is better
        if value <= t["excellent"]: return "Excellent"
        if value <= t["good"]:      return "Good"
        if value <= t["poor"]:      return "Poor"
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
            "kl_divergence":    None,
            "ber":              None,
            "bpp":              None,
            "psnr_label":       None,
            "ssim_label":       None,
            "kl_label":         None,
            "ber_label":        None,
            # Recorded grades from embed time (from manifest)
            "recorded_psnr":    entry.get("psnr"),
            "recorded_ssim":    entry.get("ssim"),
            "recorded_kl":      entry.get("kl_divergence"),
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
            kl   = _compute_kl(orig_arr, stego_arr)
            ber  = _compute_ber(orig_arr, stego_arr)

            # BPP — use fragment_size_bytes from manifest if available
            frag_bytes = manifest.get("fragment_size_bytes",
                         int(len(stego_arr.tobytes()) * ber / 8))
            pixels     = orig_arr.shape[0] * orig_arr.shape[1]
            bpp        = _embedding_rate(frag_bytes, pixels)

            frag_result.update({
                "psnr":          round(psnr, 4),
                "ssim":          round(ssim, 6),
                "kl_divergence": round(kl,   8),
                "ber":           round(ber,   8),
                "bpp":           round(bpp,   6),
                "psnr_label":    _grade_label("psnr", psnr),
                "ssim_label":    _grade_label("ssim", ssim),
                "kl_label":      _grade_label("kl",   kl),
                "ber_label":     _grade_label("ber",  ber),
            })

            progress_queue.put(("progress", pct,
                f"  PSNR={psnr:.2f} dB  SSIM={ssim:.4f}  "
                f"KL={kl:.6f}  BER={ber:.6f}  BPP={bpp:.4f}"))

        except Exception as e:
            frag_result["error"] = f"Metric computation failed: {e}"

        per_fragment.append(frag_result)

    # ── Summary statistics
    progress_queue.put(("progress", 92, "Computing summary statistics…"))

    valid = [f for f in per_fragment if f["psnr"] is not None]

    if valid:
        avg_psnr = np.mean([f["psnr"] for f in valid])
        avg_ssim = np.mean([f["ssim"] for f in valid])
        avg_kl   = np.mean([f["kl_divergence"] for f in valid])
        avg_ber  = np.mean([f["ber"] for f in valid])
        avg_bpp  = np.mean([f["bpp"] for f in valid])

        # Overall stealth verdict
        kl_undetectable  = avg_kl  < THRESHOLDS["kl"]["excellent"]
        ber_undetectable = avg_ber < THRESHOLDS["ber"]["excellent"]
        bpp_safe         = avg_bpp < 0.1   # below academic detection threshold

        if kl_undetectable and ber_undetectable and bpp_safe:
            verdict = "STATISTICALLY UNDETECTABLE"
            verdict_color = "green"
        elif avg_kl < THRESHOLDS["kl"]["good"] and avg_ber < THRESHOLDS["ber"]["good"]:
            verdict = "LOW DETECTION RISK"
            verdict_color = "cyan"
        elif avg_kl < THRESHOLDS["kl"]["poor"]:
            verdict = "MODERATE DETECTION RISK"
            verdict_color = "orange"
        else:
            verdict = "HIGH DETECTION RISK"
            verdict_color = "red"

        report["summary"] = {
            "avg_psnr":        round(float(avg_psnr), 4),
            "avg_ssim":        round(float(avg_ssim), 6),
            "avg_kl":          round(float(avg_kl),   8),
            "avg_ber":         round(float(avg_ber),  8),
            "avg_bpp":         round(float(avg_bpp),  6),
            "fragments_ok":    len(valid),
            "fragments_err":   len(per_fragment) - len(valid),
            "verdict":         verdict,
            "verdict_color":   verdict_color,
            "bpp_safe":        bpp_safe,
            "kl_undetectable": kl_undetectable,
            "ber_undetectable":ber_undetectable,
        }

        progress_queue.put(("progress", 96,
            f"Overall verdict: {verdict}"))
        progress_queue.put(("progress", 96,
            f"Avg PSNR={avg_psnr:.2f} dB  SSIM={avg_ssim:.4f}  "
            f"KL={avg_kl:.6f}  BER={avg_ber:.6f}  BPP={avg_bpp:.4f}"))
    else:
        report["summary"] = {"verdict": "NO DATA", "verdict_color": "red"}

    report["per_fragment"] = per_fragment
    progress_queue.put(("progress", 100, "Report complete ✓"))
    progress_queue.put(("done", None, None))
    return report
