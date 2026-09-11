"""Transcribe the VO locally (faster-whisper, $0) -> word-level timestamps."""
import json
from pathlib import Path
from faster_whisper import WhisperModel

BASE = str(Path(__file__).resolve().parents[2] / 'work' / 'houston-no-zoning')
vo = BASE + '/voiceover.mp3'
out = BASE + '/tmp/words.json'

model = WhisperModel('base.en', device='cpu', compute_type='int8')
segs, info = model.transcribe(vo, word_timestamps=True)
words = []
for s in segs:
    for w in (s.words or []):
        words.append({'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)})
json.dump(words, open(out, 'w'))
print('words:', len(words), '| last end:', words[-1]['e'] if words else 0)
for x in words[:10]:
    print(f"  {x['s']:6.2f}-{x['e']:6.2f}  {x['w']}")
print('  ...')
for x in words:
    d = x['w'].strip('.,')
    if d.isdigit() and len(d) == 4:
        print(f"  YEAR {d} spoken @ {x['s']:.2f}s")
