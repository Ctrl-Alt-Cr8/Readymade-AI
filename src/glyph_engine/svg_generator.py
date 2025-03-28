import random
import json
import svgwrite
from pathlib import Path

STYLE_PATH = Path(__file__).parent / "assets" / "style_presets.json"
SVG_OUTPUT_DIR = Path(__file__).parent / "output"
SVG_OUTPUT_DIR.mkdir(exist_ok=True)

def load_styles():
    with open(STYLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_svg(style_name="cyber_sigil", filename="sigil.svg"):
    styles = load_styles()
    style = styles.get(style_name)

    if not style:
        raise ValueError(f"Style '{style_name}' not found in style_presets.json")

    # ⚠️ TEMPORARILY DISABLE "cyber_sigil"
    if style_name == "cyber_sigil":
        raise NotImplementedError("The 'cyber_sigil' style is temporarily disabled for refinement.")

    dwg = svgwrite.Drawing(SVG_OUTPUT_DIR / filename, size=("512px", "512px"))

    for _ in range(20):
        shape = random.choice(style["shapes"])
        color = random.choice(style["color_scheme"])
        
        if shape == "circle":
            dwg.add(dwg.circle(center=(random.randint(0, 512), random.randint(0, 512)),
                               r=random.randint(10, 50), fill=color))
        
        elif shape == "rect":
            dwg.add(dwg.rect(insert=(random.randint(0, 512), random.randint(0, 512)),
                             size=(random.randint(20, 80), random.randint(20, 80)),
                             fill=color))
        
        elif shape == "line":
            dwg.add(dwg.line(start=(random.randint(0, 512), random.randint(0, 512)),
                             end=(random.randint(0, 512), random.randint(0, 512)),
                             stroke=color, stroke_width=2))

    dwg.save()
    return SVG_OUTPUT_DIR / filename

if __name__ == "__main__":
    print("Generated SVG at:", generate_svg())
