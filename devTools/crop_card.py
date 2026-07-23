from PIL import Image
import sys

check = Image.open(sys.argv[1])
w, h = check.size
print(f"check.png size: {w}x{h}")

# Card 1 (top-left card) — from earlier detection: (100, 729, 1820, 1080) was whole console
# Individual cards need to be extracted
# Actually let me crop card 1 based on standard layout

# .cap for row 1 col 1 in earlier measurements was x=0 to 420, y=120 to 234 in a 1720-wide console
# But check.png is 1920x1080, console is centered
# Console starts at x=(1920-1720)/2=100, y=1080-356=724
# Card 1 in check: x=100+0=100, y=724+120=844, w=420, h=114

card1 = check.crop((100, 844, 100+420, 844+114))
card1.save("card1_zoom.png")
print("Saved card1_zoom.png")

# Also whole console area
console = check.crop((100, 724, 100+1720, 724+356))
console.save("console_zoom.png")
print("Saved console_zoom.png")
