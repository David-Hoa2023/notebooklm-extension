#!/usr/bin/env python3
"""
Create PWA icons for Bội Kiều app
This script generates app icons in multiple sizes needed for PWA
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """Create a single icon of the specified size"""
    # Create a new image with gradient background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Create gradient background (purple theme)
    for y in range(size):
        # Create gradient from dark purple to light purple
        r = int(26 + (102 - 26) * y / size)
        g = int(0 + (51 - 0) * y / size)
        b = int(51 + (153 - 51) * y / size)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))
    
    # Add circular border
    border_width = max(2, size // 64)
    draw.ellipse([border_width, border_width, size-border_width, size-border_width], 
                outline=(255, 0, 255, 255), width=border_width)
    
    # Add text content
    try:
        # Try to use a nice font if available
        font_size = size // 4
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Add main text "Kiều"
    text = "Kiều"
    
    # Get text dimensions
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - size // 20
    
    # Add text shadow
    shadow_offset = max(1, size // 128)
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0, 128))
    
    # Add main text with gradient effect
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    
    # Add small decorative elements
    if size >= 128:
        # Add small flower symbols
        flower = "🌸"
        small_font_size = size // 8
        try:
            small_font = ImageFont.truetype("arial.ttf", small_font_size)
        except:
            small_font = font
        
        # Top flower
        flower_bbox = draw.textbbox((0, 0), flower, font=small_font)
        flower_width = flower_bbox[2] - flower_bbox[0]
        draw.text(((size - flower_width) // 2, size // 8), flower, font=small_font, fill=(255, 255, 255, 200))
        
        # Bottom flower
        draw.text(((size - flower_width) // 2, size - size // 4), flower, font=small_font, fill=(255, 255, 255, 200))
    
    # Save the image
    img.save(output_path, 'PNG', optimize=True)
    print(f"Created icon: {output_path} ({size}x{size})")

def main():
    """Generate all required PWA icons"""
    # Define required icon sizes for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    # Create icons directory if it doesn't exist
    icons_dir = "icons"
    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)
    
    # Generate each icon size
    for size in sizes:
        output_path = os.path.join(icons_dir, f"icon-{size}.png")
        create_icon(size, output_path)
    
    print(f"\nSuccessfully created {len(sizes)} icons for PWA!")
    print("Icons created:")
    for size in sizes:
        print(f"  - icon-{size}.png ({size}x{size})")

if __name__ == "__main__":
    main()