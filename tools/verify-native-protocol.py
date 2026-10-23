"""Compare C# packet hashes with the already verified Python implementation."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from k621_rgb.k621 import encode_static

result = json.loads(Path('artifacts/native/self-test.json').read_text())
config = bytearray((i * 13 + 7) % 256 for i in range(1032))
config[:8] = bytes.fromhex('06 83 c6 00 00 00 00 00')
config[14:16] = config[78:80] = bytes.fromhex('5a a5')
palette = bytearray((i * 31 + 9) % 256 for i in range(1032))
palette[:8] = bytes.fromhex('06 85 00 00 00 00 00 00')
for color, hashes in result['Samples'].items():
    colors, mode = encode_static(bytes(config), bytes(palette), color)
    assert hashlib.sha256(colors).hexdigest().upper() == hashes['Colors'], color
    assert hashlib.sha256(mode).hexdigest().upper() == hashes['Mode'], color
print('C# and verified Python encoders produce identical packets for all six test colors.')
