from wand.image import Image
import sys

def save_thumbnail(pdf_path, jpg_path, dpi, width, height):
    DPI = (dpi if dpi else 200)
    WIDTH = (width if width else 340)
    HEIGHT = (height if height else 480)
    
    with Image(filename=pdf_path+"[0]", resolution=(DPI, DPI)) as img:
         img.resize(WIDTH, HEIGHT)
         img.save(filename=jpg_path)

if __name__ == "__main__":
    pdf_path = sys.argv[1]
    jpg_path = pdf_path.split(".")[0]+"_export.jpg"
    
    save_thumbnail(pdf_path, jpg_path)