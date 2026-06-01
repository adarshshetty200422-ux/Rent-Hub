from PIL import Image

def clean_logo():
    img_path = r"c:\Users\adars\OneDrive\Documents\Rent hub\rent_hub\static\images\logo.png"
    img = Image.open(img_path)
    print(f"Current cropped size: {img.size}")
    
    # The current size is around 352x407. We will crop the right side to remove the letter fragment.
    # We keep from x=0 to x=315 (which is 315 width).
    cropped = img.crop((0, 0, 315, img.height))
    
    # Auto-crop top and bottom padding to make it tight and square-ish
    # Convert to RGBA
    if cropped.mode != 'RGBA':
        cropped = cropped.convert('RGBA')
        
    width, height = cropped.size
    
    left = width
    top = height
    right = 0
    bottom = 0
    
    for y in range(height):
        for x in range(width):
            r, g, b, a = cropped.getpixel((x, y))
            if a > 10:  # non-transparent
                if x < left: left = x
                if x > right: right = x
                if y < top: top = y
                if y > bottom: bottom = y
                
    print(f"Refined bounding box: left={left}, top={top}, right={right}, bottom={bottom}")
    
    padding = 10
    final = cropped.crop((max(0, left - padding), max(0, top - padding), min(width, right + padding), min(height, bottom + padding)))
    final.save(img_path, "PNG")
    print(f"Final saved size: {final.size}")

if __name__ == "__main__":
    clean_logo()
