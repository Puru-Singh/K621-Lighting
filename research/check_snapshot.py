import json
from pathlib import Path

snapshot = json.loads(Path('research/captures/before-standalone.json').read_text())
events = [json.loads(line)['message'].get('payload', {}) for line in
          Path('research/captures/lighting-session.jsonl').read_text().splitlines()]
for address, opcode in (('c6', 3), ('c8', 8), ('cc', 9), ('d0', 9), ('d8', 4)):
    last = [p['before'] for p in events if p.get('kind') == 'HidD_SetFeature' and
            p['before'][:3] == [6, opcode, int(address, 16)]][-1]
    read = snapshot[address]
    diff = [(i, a, b) for i, (a, b) in enumerate(zip(read, last)) if i >= 8 and a != b]
    print(address, 'body diff count', len(diff), 'first', diff[:30])
print('C6 first 144', bytes(snapshot['c6'][:144]).hex(' '))
