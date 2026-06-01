import os
from PIL import Image

def crop_and_clean_logo():
    src_path = r"C:\Users\adars\.gemini\antigravity\brain\810d7329-1d51-457b-8503-cd66d8427658\media__1780298267341.png"
    dest_path = r"c:\Users\adars\OneDrive\Documents\Rent hub\rent_hub\static\images\logo.png"

    if not os.path.exists(src_path):
        print(f"Source file not found: {src_path}")
        return

    try:
        # Open source image
        img = Image.open(src_path)
        img = img.convert("RGBA")
        width, height = img.size

        # Crop the left part where the icon is (up to column 30 of the icon region)
        # Note: the original region height was 70.
        icon_only = img.crop((0, 0, 45, height)) # 45 is well within the gap before "R" starts
        icon_only = icon_only.convert("RGBA")
        datas = icon_only.getdata()

        # Detect background color from top-left pixel
        bg_r, bg_g, bg_b, bg_a = datas[0]
        print(f"Background color: R={bg_r}, G={bg_g}, B={bg_b}")

        # Replace background color with transparent alpha
        new_data = []
        threshold = 35
        for item in datas:
            r, g, b, a = item
            dist = ((r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2) ** 0.5
            if dist < threshold:
                new_data.append((0, 0, 0, 0))
            else:
                new_data.append(item)

        icon_only.putdata(new_data)

        # Auto-crop the bounding box of non-transparent pixels to make it a tight square icon
        w_cropped, h_cropped = icon_only.size
        left = w_cropped
        top = h_cropped
        right = 0
        bottom = 0

        for y in range(h_cropped):
            for x in range(w_cropped):
                r, g, b, a = icon_only.getpixel((x, y))
                if a > 10:  # Non-transparent
                    if x < left: left = x
                    if x > right: right = x
                    if y < top: top = y
                    if y > bottom: bottom = y

        print(f"Refined bounding box: left={left}, top={top}, right={right}, bottom={bottom}")

        # Add a tiny padding (e.g. 2px) to prevent edge clipping
        padding = 2
        final_box = (
            max(0, left - padding),
            max(0, top - padding),
            min(w_cropped, right + padding),
            min(h_cropped, bottom + padding)
        )
        
        final_img = icon_only.crop(final_box)
        
        # Save as PNG
        final_img.save(dest_path, "PNG")
        print(f"Successfully saved clean icon-only logo of size {final_img.size} to {dest_path}!")

    except Exception as e:
        print(f"Error cropping logo: {e}")

if __name__ == "__main__":
    crop_and_clean_logo()
