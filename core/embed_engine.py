"""
core/embed_engine.py
─────────────────────────────────────────────────────────────
Steganography Embed Engine — Sprint 2 (updated)
Uses the image-fragment pairing algorithm (PSNR + SSIM grading)
to decide which fragment goes into which carrier image before
performing the final LSB embedding.

Public API
----------
embed(file_path, carrier_folder, out_folder, fragment_size_bytes, progress_queue)
"""

import os
import json
from stegano import lsb

from core.fragment_manager import fragment_file, FRAGMENT_SIZES, _human
from core.pairing_algorithm import (
    pair_fragments_to_carriers,
    format_grade_table,
    _encode_fragment,
)

# Supported carrier image extensions
CARRIER_EXTENSIONS = {".png", ".bmp"}


def _collect_carriers(carrier_folder: str) -> list[str]:
    """Return sorted list of supported image paths in the carrier folder."""
    carriers = []
    for fname in sorted(os.listdir(carrier_folder)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in CARRIER_EXTENSIONS:
            carriers.append(os.path.join(carrier_folder, fname))
    return carriers


def embed(
    file_path: str,
    carrier_folder: str,
    out_folder: str,
    fragment_size_bytes: int,
    progress_queue,
) -> bool:
    """
    Full embed pipeline:
      1. Fragment the file
      2. Validate carrier images
      3. Run pairing algorithm (PSNR + SSIM grading)
      4. LSB-embed each fragment into its assigned carrier
      5. Write manifest.json

    Returns True on success, False on failure.
    """

    # ── Step 1: Fragment
    progress_queue.put(("progress", 0, "Starting embed pipeline…"))
    fragments = fragment_file(file_path, fragment_size_bytes, progress_queue)
    if not fragments:
        return False

    total = len(fragments)

    # ── Step 2: Validate carriers
    progress_queue.put(("progress", 18, "Scanning carrier images…"))
    carriers = _collect_carriers(carrier_folder)

    if not carriers:
        progress_queue.put(("error", 0,
            f"No supported carrier images found in:\n{carrier_folder}\n"
            f"(Supported: {', '.join(CARRIER_EXTENSIONS)})"))
        return False

    if len(carriers) < total:
        progress_queue.put(("error", 0,
            f"Not enough carrier images.\n"
            f"  Fragments : {total}\n"
            f"  Carriers  : {len(carriers)}\n"
            f"Please add more images or choose a larger fragment size."))
        return False

    progress_queue.put(("progress", 22,
        f"{len(carriers)} carrier(s) found — need {total}."))

    # ── Step 3: Pairing algorithm (PSNR + SSIM grading)
    progress_queue.put(("progress", 24,
        f"Running image-fragment pairing algorithm…"))

    # Only use as many carriers as there are fragments
    active_carriers = carriers[:total]

    assignments = pair_fragments_to_carriers(
        active_carriers, fragments, progress_queue
    )

    if not assignments:
        return False

    # Log the full grade table
    table = format_grade_table(assignments)
    for line in table.split("\n"):
        progress_queue.put(("progress", 92, line))

    # ── Step 4: LSB embed using assigned pairings
    progress_queue.put(("progress", 93, "Embedding fragments into assigned carriers…"))
    os.makedirs(out_folder, exist_ok=True)
    manifest_entries = []
    original_hash = fragments[0]["original_hash"]
    original_name = fragments[0]["original_name"]

    for i, assignment in enumerate(assignments):
        carrier_path = assignment["carrier_path"]
        carrier_name = assignment["carrier_name"]
        frag         = assignment["fragment"]

        out_name = f"stego_{frag['index']:04d}_{carrier_name}"
        out_name = os.path.splitext(out_name)[0] + ".png"
        out_path = os.path.join(out_folder, out_name)

        pct = 93 + int(5 * (i + 1) / total)
        progress_queue.put(("progress", pct,
            f"Embedding frag[{frag['index']}] → {out_name}  "
            f"(grade={assignment['grade']:.4f})…"))

        payload = _encode_fragment(frag)
        try:
            stego_img = lsb.hide(carrier_path, payload)
            stego_img.save(out_path)
        except Exception as e:
            progress_queue.put(("error", 0,
                f"LSB embed failed on fragment {frag['index']}: {e}"))
            return False

        manifest_entries.append({
            "fragment_index": frag["index"],
            "stego_file":     out_name,
            "carrier_source": carrier_name,
            "psnr":           assignment["psnr"],
            "ssim":           assignment["ssim"],
            "grade":          assignment["grade"],
        })

    # ── Step 5: Write manifest
    progress_queue.put(("progress", 98, "Writing manifest…"))

    # Sort manifest entries by fragment index for clean extraction
    manifest_entries.sort(key=lambda e: e["fragment_index"])

    manifest = {
        "original_name":       original_name,
        "original_hash":       original_hash,
        "total_fragments":     total,
        "fragment_size_label": _size_label(fragment_size_bytes),
        "fragment_size_bytes": fragment_size_bytes,
        "pairing_method":      "PSNR+SSIM greedy",
        "fragments":           manifest_entries,
    }
    manifest_path = os.path.join(out_folder, "manifest.json")
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
    except OSError as e:
        progress_queue.put(("error", 0, f"Could not write manifest: {e}"))
        return False

    progress_queue.put(("progress", 100,
        f"Embed complete ✓  —  {total} stego image(s) + manifest saved to:\n{out_folder}"))
    progress_queue.put(("done", None, None))
    return True


def _size_label(size_bytes: int) -> str:
    for label, val in FRAGMENT_SIZES.items():
        if val == size_bytes:
            return label
    return f"{size_bytes} B"
