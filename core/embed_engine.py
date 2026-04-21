"""
core/embed_engine.py
─────────────────────────────────────────────────────────────
Steganography Embed Engine — Sprint 2
Embeds binary fragments into carrier PNG images using LSB
steganography via the Stegano library.

Public API
----------
embed(file_path, carrier_folder, out_folder, fragment_size_bytes, progress_queue)
"""

import os
import base64
import json
from stegano import lsb
from core.fragment_manager import fragment_file, FRAGMENT_SIZES, _human


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


def _encode_fragment(frag: dict) -> str:
    """
    Encode a fragment dict into a string safe for LSB embedding.
    Format: base64(binary_data)|original_hash|original_name|index|total
    """
    b64_data = base64.b64encode(frag["data"]).decode("utf-8")
    return "|".join([
        b64_data,
        frag["original_hash"],
        frag["original_name"],
        str(frag["index"]),
        str(frag["total"]),
    ])


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
      3. LSB-embed each fragment into a carrier image
      4. Write a JSON manifest to the output folder

    Returns True on success, False on failure.
    """

    # ── Step 1: Fragment
    progress_queue.put(("progress", 0, "Starting embed pipeline…"))
    fragments = fragment_file(file_path, fragment_size_bytes, progress_queue)
    if not fragments:
        return False

    total = len(fragments)

    # ── Step 2: Validate carriers
    progress_queue.put(("progress", 22, "Scanning carrier images…"))
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

    progress_queue.put(("progress", 25,
        f"{len(carriers)} carrier(s) found — need {total}."))

    # ── Step 3: Embed fragments
    os.makedirs(out_folder, exist_ok=True)
    manifest_entries = []
    original_hash = fragments[0]["original_hash"]
    original_name = fragments[0]["original_name"]

    for i, frag in enumerate(fragments):
        carrier_path = carriers[i]
        carrier_name = os.path.basename(carrier_path)
        out_name     = f"stego_{i:04d}_{carrier_name}"
        # ensure .png extension (stegano requires lossless format)
        out_name     = os.path.splitext(out_name)[0] + ".png"
        out_path     = os.path.join(out_folder, out_name)

        pct = 25 + int(60 * (i + 1) / total)
        progress_queue.put(("progress", pct,
            f"Embedding fragment {i + 1}/{total} → {out_name}…"))

        payload = _encode_fragment(frag)

        try:
            stego_img = lsb.hide(carrier_path, payload)
            stego_img.save(out_path)
        except Exception as e:
            progress_queue.put(("error", 0,
                f"LSB embed failed on fragment {i + 1}: {e}"))
            return False

        manifest_entries.append({
            "fragment_index": i,
            "stego_file":     out_name,
            "carrier_source": carrier_name,
        })

    # ── Step 4: Write manifest
    progress_queue.put(("progress", 88, "Writing manifest…"))
    manifest = {
        "original_name":    original_name,
        "original_hash":    original_hash,
        "total_fragments":  total,
        "fragment_size_label": _size_label(fragment_size_bytes),
        "fragment_size_bytes": fragment_size_bytes,
        "fragments":        manifest_entries,
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
