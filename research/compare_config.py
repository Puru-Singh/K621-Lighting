import json
from pathlib import Path

events = [json.loads(line) for line in Path('research/captures/lighting-session.jsonl').read_text().splitlines()]
last_read = None
for event in events:
    p = event['message'].get('payload', {})
    if p.get('kind') == 'HidD_GetFeature' and p['after'][:3] == [6, 131, 198]:
        last_read = p['after']
    if p.get('kind') == 'HidD_SetFeature' and p['before'][:3] == [6, 3, 198]:
        packet = p['before']
        diff = [(i, a, b) for i, (a, b) in enumerate(zip(last_read, packet)) if a != b]
        print(event['time'][11:23], 'diff count', len(diff), 'first', diff[:30])
