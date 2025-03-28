"""
SVG to PNG Converter Utility
"""

import cairosvg
from io import BytesIO
import logging

logger = logging.getLogger("svg_converter")

def convert_svg_to_png(svg_content, width=1200, height=675):
    """
    Convert SVG content to PNG format for Twitter compatibility
    
    Args:
        svg_content: String containing SVG XML
        width: Desired width of PNG
        height: Desired height of PNG
        
    Returns:
        BytesIO: PNG image as BytesIO object or None if conversion failed
    """
    try:
        logger.info(f"Converting SVG (length: {len(svg_content)}) to PNG...")
        png_bytes = BytesIO()
        
        # Use CairoSVG to convert from SVG to PNG
        cairosvg.svg2png(
            bytestring=svg_content.encode('utf-8'),
            write_to=png_bytes,
            output_width=width,
            output_height=height
        )
        
        # Reset buffer position
        png_bytes.seek(0)
        
        # Log successful conversion
        size_kb = png_bytes.getbuffer().nbytes / 1024
        logger.info(f"SVG converted to PNG successfully. Size: {size_kb:.2f} KB")
        
        return png_bytes
        
    except Exception as e:
        logger.exception(f"Error converting SVG to PNG: {e}")
        return None
