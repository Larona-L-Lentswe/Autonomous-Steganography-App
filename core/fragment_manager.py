"""
core/fragment_manager.py
─────────────────────────────────────────────────────────────
Fragment Manager — Sprint 1
Handles fragmentation and reassembly of any binary file.

Public API
----------
fragment_sizes()            → dict of label → bytes
estimate_fragments(path, size_bytes) → int
fragment_file(path, size_bytes, progress_queue) → list[dict]
reassemble_fragments(fragments, out_path, original_hash, progress_queue) → bool
"""

import os
import math
import hashlib

# ── Fragment size options exposed to the GUI
FRAGMENT_SIZES: dict[str, int] = {
    "256 KB":  256   * 1024,
    "512 KB":  512   * 1024,
    "1024 KB": 1024  * 1024,
    "2 MB":    2     * 1024 * 1024,
    "3 MB":    3     * 1024 * 1024,
}


def fragment_sizes() -> dict[str, int]:
    """Return the available fragment size options."""
    return FRAGMENT_SIZES


def estimate_fragments(file_path: str, fragment_size_bytes: int) -> int:
    """
    Return how many fragments a file will produce for a given fragment size.
    Returns 0 if the file does not exist or is empty.
    """
    if not file_path or not os.path.isfile(file_path):
        return 0
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return 0
    return math.ceil(file_size / fragment_size_bytes)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fragment_file(
    file_path: str,
    fragment_size_bytes: int,
    progress_queue,
) -> list[dict]:
    """
    Read a binary file, compute its SHA-256 hash, and split it into
    equal-sized fragments (last fragment may be smaller).

    Each fragment dict contains:
        index       : int   – zero-based fragment number
        total       : int   – total number of fragments
        data        : bytes – raw binary payload for this fragment
        original_hash: str  – SHA-256 of the complete original file
        original_name: str  – original filename (for reassembly)

    Puts progress tuples onto progress_queue:
        ("progress", pct: int, msg: str)
        ("error",    0,        msg: str)

    Returns list of fragment dicts, or empty list on error.
    """
    # ── Validate
    if not file_path or not os.path.isfile(file_path):
        progress_queue.put(("error", 0, f"File not found: {file_path}"))
        return []

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        progress_queue.put(("error", 0, "File is empty — nothing to fragment."))
        return []

    original_name = os.path.basename(file_path)
    total = math.ceil(file_size / fragment_size_bytes)

    progress_queue.put(("progress", 5,
        f"Reading '{original_name}'  ({_human(file_size)})…"))

    # ── Read
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
    except OSError as e:
        progress_queue.put(("error", 0, f"Could not read file: {e}"))
        return []

    # ── Hash original
    progress_queue.put(("progress", 10, "Computing SHA-256 checksum…"))
    original_hash = _sha256(raw)
    progress_queue.put(("progress", 15,
        f"Hash: {original_hash[:16]}…  ({total} fragment(s) @ {_human(fragment_size_bytes)} each)"))

    # ── Slice
    fragments = []
    for i in range(total):
        start = i * fragment_size_bytes
        end   = start + fragment_size_bytes
        chunk = raw[start:end]
        fragments.append({
            "index":         i,
            "total":         total,
            "data":          chunk,
            "original_hash": original_hash,
            "original_name": original_name,
        })
        pct = 15 + int(70 * (i + 1) / total)
        progress_queue.put(("progress", pct,
            f"Fragment {i + 1}/{total}  ({_human(len(chunk))})"))

    progress_queue.put(("progress", 90,
        f"Fragmentation complete — {total} fragment(s) ready."))
    return fragments


def reassemble_fragments(
    fragments: list[dict],
    out_path: str,
    original_hash: str,
    progress_queue,
) -> bool:
    """
    Concatenate ordered fragment dicts back into the original file.

    fragments   : list of fragment dicts (must be sorted by 'index')
    out_path    : full path where the reconstructed file will be written
    original_hash: expected SHA-256 (from manifest) for integrity check
    progress_queue: queue for progress updates

    Returns True on success, False on failure.
    """
    if not fragments:
        progress_queue.put(("error", 0, "No fragments provided for reassembly."))
        return False

    # ── Sort by index to ensure correct order
    ordered = sorted(fragments, key=lambda f: f["index"])
    total   = ordered[0]["total"]

    if len(ordered) != total:
        progress_queue.put(("error", 0,
            f"Fragment count mismatch: expected {total}, got {len(ordered)}."))
        return False

    progress_queue.put(("progress", 55, f"Assembling {total} fragment(s)…"))

    # ── Concatenate
    raw = b""
    for frag in ordered:
        raw += frag["data"]
        pct = 55 + int(25 * (frag["index"] + 1) / total)
        progress_queue.put(("progress", pct,
            f"Joining fragment {frag['index'] + 1}/{total}…"))

    # ── Verify integrity
    progress_queue.put(("progress", 82, "Verifying SHA-256 checksum…"))
    computed = _sha256(raw)
    if computed != original_hash:
        progress_queue.put(("error", 0,
            f"Integrity check FAILED.\n"
            f"  Expected : {original_hash}\n"
            f"  Got      : {computed}"))
        return False

    progress_queue.put(("progress", 88, "Checksum verified ✓"))

    # ── Write output
    try:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(raw)
    except OSError as e:
        progress_queue.put(("error", 0, f"Could not write output file: {e}"))
        return False

    progress_queue.put(("progress", 95,
        f"Written to: {out_path}  ({_human(len(raw))})"))
    return True


# ── Internal helper
def _human(size_bytes: int) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
