#!/usr/bin/env python3
"""Interactive Polly squawk audition. Runs as a file so input() uses the terminal."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SOUNDS = [
    'BRAAWK!', 'BRRRAAWK!', 'BRAAAAWK!', 'RAAAWK!', 'RAWWK!', 'ARRAWK!',
    'AWK!', 'AWK AWK!', 'AWK-AWK!', 'AWWK!', 'SKEE-EE!', 'SKREEE!',
    'SKRAAA!', 'REEEE!', 'REE-REE!', 'KREEE!', 'KRAAA!', 'KREE-AWK!',
    'CHIRP CHIRP!', 'CHIRRUP!', 'CHEEP CHEEP!', 'CHREE CHREE!',
    'WEE-WEE!', 'WRAK WRAK!', 'KRAK KRAK!', 'BRAAWK! AWK AWK!',
    'SKREEE! BRAAWK!', 'AWK AWK! KRAAA!', 'RAAAWK! RAAAWWK!',
    'KREEE! AWK!', 'Buh-RAAWK!', 'Ah-RAAWK!', 'Guh-RAAWK!',
    'Wah-RAAWK!', 'Kah-KAH! BRAAWK!',
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='voices/en_GB-semaine-medium.onnx')
    parser.add_argument('--speaker', default='3')
    parser.add_argument('--out', type=Path, default=Path('output/polly_squawk_tests'))
    parser.add_argument('--no-rating', action='store_true', help='Auto-play all clips; useful without an interactive terminal')
    args = parser.parse_args()
    if not Path(args.model).is_file():
        parser.error(f'Missing {args.model}; run ./install_polly_voice.sh')
    args.out.mkdir(parents=True, exist_ok=True)
    ratings_path = args.out / 'ratings.json'
    previous = json.loads(ratings_path.read_text()) if ratings_path.exists() else []
    by_number = {r['number']: r for r in previous}
    for i, sound in enumerate(SOUNDS, 1):
        wav = args.out / f'{i:02d}.wav'
        if not wav.is_file():
            subprocess.run([sys.executable,'-m','piper','-m',args.model,
                            '--speaker',args.speaker,'-f',str(wav)],
                           input=sound+'\n', text=True, check=True)
        print(f'[{i}/{len(SOUNDS)}] {sound} -> {wav}',flush=True)
        subprocess.run(['aplay','-q',str(wav)],check=True)
        if args.no_rating:continue
        while True:
            try:answer = input('1=parrot 2=promising 3=synthetic R=replay S=skip Q=quit: ').strip().upper()
            except EOFError:
                print('No interactive stdin; use --no-rating or run this script in a terminal.')
                return
            if answer=='R':subprocess.run(['aplay','-q',str(wav)],check=True);continue
            if answer in {'1','2','3','S','Q'}:break
        by_number[i]={'number':i,'text':sound,'rating':answer,'file':str(wav)}
        ratings_path.write_text(json.dumps([by_number[k] for k in sorted(by_number)],indent=2)+'\n')
        if answer=='Q':break
    print('Ratings:',ratings_path)

if __name__=='__main__':main()
