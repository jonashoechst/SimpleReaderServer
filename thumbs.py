from wand.image import Image
import sys

def save_thumbnail(pdf_path, jpg_path, DPI=200, WIDTH=340, HEIGHT=480):
    """
    Creates a thumbnail at jpg_path for a given pdf_path.

    DPI controls the pdf rendering resolution.
    WIDTH/HEIGHT represents the resolution of the saved jpg. 
    """

    with Image(filename=pdf_path+"[0]", resolution=(DPI, DPI)) as img:
         img.resize(WIDTH, HEIGHT)
         img.save(filename=jpg_path)

if __name__ == "__main__":
    pdf_path = sys.argv[1]
    jpg_path = pdf_path.split(".")[0]+"_export.jpg"

    save_thumbnail(pdf_path, jpg_path)
