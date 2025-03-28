import random
import json
from pathlib import Path

PALETTES_PATH = Path(__file__).parent / "assets" / "glyph_palettes.json"

def load_palettes():
    with open(PALETTES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_ascii_art(lines=5, width=16):
    palettes = load_palettes()
    symbols = sum(palettes.values(), [])
    output = []
    for _ in range(lines):
        line = ''.join(random.choice(symbols) for _ in range(width))
        output.append(line)
    return "\n".join(output)

if __name__ == "__main__":
    print(generate_ascii_art())
