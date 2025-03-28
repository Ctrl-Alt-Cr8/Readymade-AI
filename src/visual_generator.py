import hashlib
import random
import math
import logging

logger = logging.getLogger("visual_generator")

class VisualGenerator:
    """Generate SVG visuals for Readymade.AI's tweets"""
    
    @staticmethod
    def generate_svg_from_text(text, width=600, height=400):
        """Generate an abstract SVG image based on input text"""
        try:
            # Use the text as a seed for pseudorandom generation
            hash_value = hashlib.md5(text.encode()).hexdigest()
            random.seed(hash_value)
            
            # SVG header
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">\n'
            
            # Generate a gradient background
            gradient_id = f"grad_{hash_value[:6]}"
            color1 = f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"
            color2 = f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"
            
            svg += f'  <defs>\n'
            svg += f'    <linearGradient id="{gradient_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            svg += f'      <stop offset="0%" stop-color="{color1}" stop-opacity="0.2" />\n'
            svg += f'      <stop offset="100%" stop-color="{color2}" stop-opacity="0.2" />\n'
            svg += f'    </linearGradient>\n'
            svg += f'  </defs>\n'
            
            # Add background
            svg += f'  <rect width="{width}" height="{height}" fill="url(#{gradient_id})" />\n'
            
            # Generate dadaist patterns
            svg += VisualGenerator._generate_glitch_pattern(text, width, height)
            
            # Generate shapes based on text
            svg += VisualGenerator._generate_shapes_from_text(text, width, height)
            
            # Add some "code-like" elements for digital aesthetic
            svg += VisualGenerator._generate_code_elements(text, width, height)
            
            # Close SVG
            svg += '</svg>'
            
            return svg
        except Exception as e:
            logger.error(f"Error generating SVG: {e}")
            return None
    
    @staticmethod
    def _generate_glitch_pattern(text, width, height):
        """Generate glitch-like effects inspired by digital dadaism"""
        svg = ""
        words = text.split()
        num_lines = min(len(words) * 2, 30)
        
        for i in range(num_lines):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height//4) * 4  # Align to a grid for glitch effect
            x2 = random.randint(0, width)
            
            # Horizontal glitch lines
            stroke_width = random.uniform(0.5, 3)
            opacity = random.uniform(0.1, 0.7)
            color = f"#{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}"
            
            svg += f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y1}" '
            svg += f'stroke="{color}" stroke-width="{stroke_width}" opacity="{opacity:.2f}" />\n'
            
            # Occasional vertical glitch
            if random.random() < 0.3:
                x = random.randint(0, width)
                y1 = random.randint(0, height)
                y2 = random.randint(0, height)
                svg += f'  <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" '
                svg += f'stroke="{color}" stroke-width="{stroke_width}" opacity="{opacity:.2f}" />\n'
        
        return svg
    
    @staticmethod
    def _generate_shapes_from_text(text, width, height):
        """Generate shapes based on the text content"""
        svg = ""
        # Use character codes to influence shapes
        for i, char in enumerate(text):
            if i > 30:  # Limit the number of shapes
                break
                
            x = (ord(char) % 10) * width / 10 + random.randint(-20, 20)
            y = (i % 10) * height / 10 + random.randint(-20, 20)
            
            shape_type = i % 4  # Use a modulo to determine shape type
            
            if shape_type == 0:  # Circle
                r = 10 + (ord(char) % 40)
                color = f"#{ord(char) % 200 + 55:02x}{ord(char) % 150 + 50:02x}{ord(char) % 250:02x}"
                opacity = 0.1 + (i / len(text)) * 0.5
                svg += f'  <circle cx="{x}" cy="{y}" r="{r}" fill="{color}" opacity="{opacity:.2f}" />\n'
                
            elif shape_type == 1:  # Rectangle
                w = 20 + (ord(char) % 50)
                h = 10 + (ord(char) % 30)
                color = f"#{ord(char) % 200 + 55:02x}{ord(char) % 150 + 50:02x}{ord(char) % 250:02x}"
                opacity = 0.1 + (i / len(text)) * 0.5
                rotation = ord(char) % 90
                svg += f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" '
                svg += f'fill="{color}" opacity="{opacity:.2f}" '
                svg += f'transform="rotate({rotation} {x} {y})" />\n'
                
            elif shape_type == 2:  # Line
                x2 = x + 30 + (ord(char) % 40)
                y2 = y + 20 + (ord(char) % 30)
                color = f"#{ord(char) % 200 + 55:02x}{ord(char) % 150 + 50:02x}{ord(char) % 250:02x}"
                stroke_width = 1 + (i % 5)
                svg += f'  <line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" '
                svg += f'stroke="{color}" stroke-width="{stroke_width}" />\n'
                
            else:  # Path (more complex shape)
                d = f"M{x},{y} "
                points = 3 + (i % 4)
                radius = 15 + (ord(char) % 25)
                for j in range(points):
                    angle = 2 * math.pi * j / points
                    px = x + radius * math.cos(angle)
                    py = y + radius * math.sin(angle)
                    d += f"L{px},{py} "
                d += "Z"
                color = f"#{ord(char) % 200 + 55:02x}{ord(char) % 150 + 50:02x}{ord(char) % 250:02x}"
                opacity = 0.1 + (i / len(text)) * 0.4
                svg += f'  <path d="{d}" fill="{color}" opacity="{opacity:.2f}" />\n'
        
        return svg
    
    @staticmethod
    def _generate_code_elements(text, width, height):
        """Generate elements that look like code/digital artifacts"""
        svg = ""
        
        # Add some "code" text elements
        font_size = random.randint(4, 8)
        for i in range(min(len(text), 10)):
            if random.random() < 0.7:  # 70% chance for each character
                x = random.randint(0, width)
                y = random.randint(0, height)
                
                # Use ASCII or binary representation sometimes
                if random.random() < 0.5:
                    char_txt = f"{ord(text[i]):08b}"  # Binary representation
                else:
                    char_txt = text[i] if text[i].isprintable() else hex(ord(text[i]))
                
                opacity = random.uniform(0.3, 0.8)
                color = f"#{random.randint(100, 255):02x}{random.randint(100, 255):02x}{random.randint(100, 255):02x}"
                svg += f'  <text x="{x}" y="{y}" font-family="monospace" font-size="{font_size}" '
                svg += f'fill="{color}" opacity="{opacity:.2f}">{char_txt}</text>\n'
        
        return svg
