"""Convert Piper phoneme alignments or PCM audio into BirdPi singing ranges."""
import math
import struct

# Broad IPA vowel approximations. Physical beak movement is intentionally simplified.
VOWELS = set('aeiouyɑɐɒæɓəɚɛɜɞɤɨɪɯɵœøɔɶʉʊʌʏɘɜɝɐ')
SILENCE = {'', ' ', '_', 'sil', 'sp', 'pau', '‖', '|'}


def merge_ranges(ranges, gap=0.07, min_open=0.08, min_closed=0.06, max_open=0.25):
    """Merge close events, split long activations; apply conservative min on/off.

    max_open limits a continuous command, but is NOT a hardware duty-cycle safety guarantee.
    """
    if not ranges:
        return []
    merged = []
    for start, end in sorted((max(0.0, float(a)), float(b)) for a, b in ranges if b > a):
        if merged and start - merged[-1][1] < max(gap, min_closed):
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    result = []
    for start, end in merged:
        if end - start < min_open:
            end = start + min_open
        while end - start > max_open:
            result.append([round(start, 3), round(start + max_open, 3)])
            start += max_open + min_closed
        if end - start >= min_open:
            result.append([round(start, 3), round(end, 3)])
    return result


def phonemes_to_ranges(alignments, sample_rate, **settings):
    """alignments are objects with .phoneme/.num_samples or equivalent dicts."""
    cursor = 0
    intervals = []
    for item in alignments:
        phoneme = item['phoneme'] if isinstance(item, dict) else item.phoneme
        samples = item['num_samples'] if isinstance(item, dict) else item.num_samples
        duration = max(0, int(samples)) / sample_rate
        sym = str(phoneme).strip()
        if sym not in SILENCE and any(char in VOWELS for char in sym):
            intervals.append((cursor, cursor + duration))
        cursor += duration
    return merge_ranges(intervals, **settings)


def pcm_to_ranges(pcm, sample_rate, frame_ms=20, **settings):
    """Energy gate fallback with hysteresis, for mono signed 16-bit PCM."""
    count = len(pcm) // 2
    if count == 0:
        return []
    samples = struct.unpack('<' + 'h' * count, pcm[:count * 2])
    frame = max(1, int(sample_rate * frame_ms / 1000))
    energies = []
    for pos in range(0, count, frame):
        part = samples[pos:pos + frame]
        energies.append(math.sqrt(sum(x*x for x in part) / len(part)) / 32768)
    peak = max(energies, default=0)
    if peak < 0.003:
        return []
    open_threshold = max(0.01, peak * 0.19)
    close_threshold = max(0.006, peak * 0.10)
    opened = False
    start = 0
    ranges = []
    for i, energy in enumerate(energies):
        if not opened and energy >= open_threshold:
            opened, start = True, i * frame / sample_rate
        elif opened and energy <= close_threshold:
            ranges.append((start, i * frame / sample_rate))
            opened = False
    if opened:
        ranges.append((start, count / sample_rate))
    return merge_ranges(ranges, **settings)
