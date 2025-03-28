import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from glyph_engine.ascii_generator import generate_ascii_art
from glyph_engine.svg_generator import generate_svg
from PIL import Image, ImageDraw, ImageFont
import cairosvg
from io import BytesIO
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path(__file__).parent / "output"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 675

def overlay_ascii_on_image(png_path, ascii_text, output_path):
    image = Image.open(png_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(FONT_PATH, 20)
    except IOError:
        font = ImageFont.load_default()
    lines = ascii_text.split("\n")
    line_height = font.getbbox("A")[3]
    x = 20
    y = image.height - (line_height * len(lines)) - 20
    for line in lines:
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 180))
        y += line_height
    image.save(output_path)
    return output_path

def compose_hybrid_output():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ascii_art = generate_ascii_art(lines=6, width=28)
    filename = f"glyph_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    svg_path = generate_svg(style_name="cyber_sigil", filename=f"{filename}.svg")
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()
    png_bytes = BytesIO()
    cairosvg.svg2png(bytestring=svg_content.encode("utf-8"), write_to=png_bytes,
                     output_width=DEFAULT_WIDTH, output_height=DEFAULT_HEIGHT)
    base_png_path = OUTPUT_DIR / f"{filename}_base.png"
    with open(base_png_path, "wb") as f:
        f.write(png_bytes.getvalue())
    final_png_path = OUTPUT_DIR / f"{filename}_final.png"
    overlay_ascii_on_image(base_png_path, ascii_art, final_png_path)
    caption = "[glyph transmission initiated]"
    return caption, str(final_png_path)

if __name__ == "__main__":
    caption, path = compose_hybrid_output()
    print(caption, path)
