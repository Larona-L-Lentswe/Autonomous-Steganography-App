"""
core/extract_engine.py
─────────────────────────────────────────────────────────────
Steganography Extract Engine — Sprint 2
Reads stego carrier images, extracts LSB-encoded fragments,
and reassembles the original file.

Public API
----------
extract(stego_folder, out_folder, progress_queue)
"""

import os
import base64
import json
from stegano import lsb
from core.fragment_manager import reassemble_fragments


def extract(
    stego_folder: str,
    out_folder: str,
    progress_queue,
) -> bool:
    """
    Full extract pipeline:
      1. Load and parse manifest.json
      2. LSB-extract each fragment from its stego carrier
      3. Decode and reassemble fragments
      4. Verify SHA-256 integrity and write output file

    Returns True on success, False on failure.
    """

    # ── Step 1: Load manifest
    progress_queue.put(("progress", 0, "Starting extract pipeline…"))
    manifest_path = os.path.join(stego_folder, "manifest.json")

    if not os.path.isfile(manifest_path):
        progress_queue.put(("error", 0,
            f"manifest.json not found in:\n{stego_folder}\n"
            "Make sure you selected the correct stego output folder."))
        return False

    progress_queue.put(("progress", 5, "Reading manifest…"))
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        progress_queue.put(("error", 0, f"Could not read manifest: {e}"))
        return False

    original_name   = manifest.get("original_name", "recovered_file")
    original_hash   = manifest.get("original_hash", "")
    total_fragments = manifest.get("total_fragments", 0)
    entries         = manifest.get("fragments", [])

    progress_queue.put(("progress", 10,
        f"Manifest OK — '{original_name}'  "
        f"({total_fragments} fragment(s))"))

    if not entries:
        progress_queue.put(("error", 0, "Manifest contains no fragment entries."))
        return False

    # ── Step 2: Extract fragments via LSB
    fragments = []
    for i, entry in enumerate(entries):
        stego_file = entry.get("stego_file", "")
        stego_path = os.path.join(stego_folder, stego_file)

        pct = 10 + int(60 * (i + 1) / total_fragments)
        progress_queue.put(("progress", pct,
            f"Extracting fragment {i + 1}/{total_fragments} ← {stego_file}…"))

        if not os.path.isfile(stego_path):
            progress_queue.put(("error", 0,
                f"Stego file missing: {stego_file}\n"
                f"Expected at: {stego_path}"))
            return False

        try:
            payload = lsb.reveal(stego_path)
        except Exception as e:
            progress_queue.put(("error", 0,
                f"LSB extraction failed on {stego_file}: {e}"))
            return False

        if payload is None:
            progress_queue.put(("error", 0,
                f"No hidden data found in {stego_file}.\n"
                "File may be corrupt or not a valid stego image."))
            return False

        # ── Decode payload: b64data|hash|name|index|total
        try:
            parts = payload.split("|")
            if len(parts) != 5:
                raise ValueError(f"Expected 5 parts, got {len(parts)}")
            b64_data, frag_hash, frag_name, frag_index, frag_total = parts
            raw_data = base64.b64decode(b64_data)
        except Exception as e:
            progress_queue.put(("error", 0,
                f"Payload decode failed for {stego_file}: {e}"))
            return False

        fragments.append({
            "index":          int(frag_index),
            "total":          int(frag_total),
            "data":           raw_data,
            "original_hash":  frag_hash,
            "original_name":  frag_name,
        })

    # ── Step 3 & 4: Reassemble + integrity check
    progress_queue.put(("progress", 72, "All fragments extracted — reassembling…"))
    os.makedirs(out_folder, exist_ok=True)
    out_path = os.path.join(out_folder, original_name)

    success = reassemble_fragments(fragments, out_path, original_hash, progress_queue)
    if not success:
        return False

    progress_queue.put(("progress", 100,
        f"Extract complete ✓  —  '{original_name}' saved to:\n{out_folder}"))
    progress_queue.put(("done", None, None))
    return True
