#!/usr/bin/env python3
"""Offline Piper WAV + BirdPi-compatible timed singing ranges."""
import argparse
import json
import time
import wave
from pathlib import Path
from speech_animation import phonemes_to_ranges, pcm_to_ranges


def generate(text, voice_path, output_dir, bird):
    from piper import PiperVoice
    output_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    # In-memory patch requires onnx; gracefully handles models with no alignment support.
    voice = PiperVoice.load(str(voice_path), include_alignments=True)
    load_time = time.perf_counter() - t0
    t1 = time.perf_counter()
    sample_rate = None
    frames = bytearray()
    candidate_intervals = []
    aligned = True
    total_samples = 0
    for chunk in voice.synthesize(text, include_alignments=True):
        if sample_rate is None:
            sample_rate = chunk.sample_rate
        elif chunk.sample_rate != sample_rate:
            raise ValueError('Unexpected sample-rate change across chunks')
        pcm = chunk.audio_int16_bytes
        frames.extend(pcm)
        frame_count = len(pcm) // 2
        if chunk.phoneme_alignments is None:
            aligned = False
        else:
            # Keep chunk offset independent of alignment-internal punctuation/padding.
            ranges = phonemes_to_ranges(chunk.phoneme_alignments, sample_rate,
                                       gap=0.07, min_open=0.08,
                                       min_closed=0.06, max_open=0.25)
            candidate_intervals.extend((a + total_samples / sample_rate,
                                        b + total_samples / sample_rate) for a, b in ranges)
        total_samples += frame_count
    if not frames or sample_rate is None:
        raise RuntimeError('Piper generated no audio')
    synthesis_time = time.perf_counter() - t1
    from speech_animation import merge_ranges
    if aligned:
        ranges = merge_ranges(candidate_intervals)
        method = 'phoneme_alignments'
    else:
        ranges = pcm_to_ranges(bytes(frames), sample_rate)
        method = 'audio_energy_fallback'
    wav_path = output_dir / 'speech.wav'
    json_path = output_dir / 'speech.json'
    with wave.open(str(wav_path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    duration = total_samples / sample_rate
    payload = {
        'type': 'speech', 'bird': bird, 'text': text,
        'audio': wav_path.name, 'sample_rate': sample_rate,
        'duration': round(duration, 3), 'timing_method': method,
        'singing_ranges': ranges,
        'metrics': {
            'model_load_s': round(load_time, 3),
            'synthesis_s': round(synthesis_time, 3),
            'synthesis_realtime_factor': round(synthesis_time / duration, 3),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2) + '\n')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('text', help='Words to synthesize')
    parser.add_argument('--voice', type=Path, default=Path('voices/en_US-lessac-medium.onnx'))
    parser.add_argument('--out', type=Path, default=Path('output'))
    parser.add_argument('--bird', default='jose')
    args = parser.parse_args()
    if not args.voice.exists():
        parser.error(f'Missing voice: {args.voice}. Run ./install.sh first.')
    print(json.dumps(generate(args.text, args.voice, args.out, args.bird), indent=2))

if __name__ == '__main__':
    main()
