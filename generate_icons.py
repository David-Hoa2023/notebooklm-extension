#!/usr/bin/env python3
"""
Generate icons for NotebookLM Chrome Extension
Creates a notebook with link chain icon to represent note-taking and web linking
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size):
    """Create an icon with notebook and link chain design"""
    
    # Create a new image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Define colors
    bg_gradient_start = (74, 144, 226)  # Blue
    bg_gradient_end = (123, 104, 238)   # Purple
    notebook_color = (255, 255, 255)    # White
    link_color = (46, 125, 50)          # Green
    pen_color = (255, 107, 107)         # Coral
    line_color = (224, 224, 224)        # Light gray
    
    # Draw background gradient (simplified as solid color blend)
    for y in range(size):
        ratio = y / size
        r = int(bg_gradient_start[0] * (1 - ratio) + bg_gradient_end[0] * ratio)
        g = int(bg_gradient_start[1] * (1 - ratio) + bg_gradient_end[1] * ratio)
        b = int(bg_gradient_start[2] * (1 - ratio) + bg_gradient_end[2] * ratio)
        draw.rectangle([(0, y), (size, y + 1)], fill=(r, g, b, 255))
    
    # Draw notebook pages (with shadow effect)
    # Back page (shadow)
    back_page = [
        int(size * 0.25), int(size * 0.15),
        int(size * 0.80), int(size * 0.80)
    ]
    draw.rectangle(back_page, fill=(255, 255, 255, 77))
    
    # Middle page
    middle_page = [
        int(size * 0.22), int(size * 0.18),
        int(size * 0.77), int(size * 0.83)
    ]
    draw.rectangle(middle_page, fill=(255, 255, 255, 128))
    
    # Front page (main notebook)
    front_page = [
        int(size * 0.20), int(size * 0.20),
        int(size * 0.75), int(size * 0.85)
    ]
    draw.rectangle(front_page, fill=notebook_color)
    
    # Draw lines on notebook
    line_spacing = int(size * 0.08)
    for i in range(1, 5):
        y = int(size * 0.20 + (i * line_spacing))
        if y < size * 0.80:
            draw.line(
                [(int(size * 0.25), y), (int(size * 0.70), y)],
                fill=line_color,
                width=max(1, int(size * 0.01))
            )
    
    # Draw chain links (two interlocking circles)
    link_width = max(2, int(size * 0.04))
    
    # First link (ellipse)
    link1_bbox = [
        int(size * 0.40), int(size * 0.50),
        int(size * 0.55), int(size * 0.65)
    ]
    draw.ellipse(link1_bbox, outline=link_color, width=link_width)
    
    # Second link (overlapping ellipse)
    link2_bbox = [
        int(size * 0.50), int(size * 0.50),
        int(size * 0.65), int(size * 0.65)
    ]
    draw.ellipse(link2_bbox, outline=link_color, width=link_width)
    
    # Draw a pencil/pen
    pen_start = (int(size * 0.60), int(size * 0.35))
    pen_end = (int(size * 0.70), int(size * 0.45))
    draw.line([pen_start, pen_end], fill=pen_color, width=max(2, int(size * 0.04)))
    
    # Pencil tip
    tip_start = pen_end
    tip_end = (int(size * 0.72), int(size * 0.47))
    draw.line([tip_start, tip_end], fill=(51, 51, 51), width=max(1, int(size * 0.02)))
    
    # Add a subtle shadow at the bottom
    shadow_rect = [
        int(size * 0.20), int(size * 0.83),
        int(size * 0.75), int(size * 0.87)
    ]
    draw.rectangle(shadow_rect, fill=(0, 0, 0, 25))
    
    return img

def main():
    """Generate icons in multiple sizes"""
    
    # Icon sizes required for Chrome extension
    sizes = {
        'icon16.png': 16,
        'icon48.png': 48,
        'icon128.png': 128
    }
    
    icons_dir = 'icons'
    
    # Create icons directory if it doesn't exist
    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)
    
    # Generate each icon
    for filename, size in sizes.items():
        icon = create_icon(size)
        filepath = os.path.join(icons_dir, filename)
        icon.save(filepath, 'PNG')
        print(f"Created {filepath} ({size}x{size})")
    
    print("\nIcons generated successfully!")
    print("The icons represent a notebook with chain links, symbolizing note-taking and web linking.")

if __name__ == '__main__':
    try:
        main()
    except ImportError:
        print("This script requires the Pillow library.")
        print("Install it with: pip install Pillow")
        print("\nAlternatively, open generate-icons.html in Chrome to manually save the icons.")