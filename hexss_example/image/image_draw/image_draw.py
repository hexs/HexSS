from hexss.image import Image, ImageFont

img = Image.new('RGB', (500, 400), (0, 0, 0))
draw = img.draw('center')

draw.circle((0, 0), radius=35, outline=(0, 255, 0), width=2)
draw.line((-50, -50, 50, 50), fill=(255, 0, 0), width=2)
draw.line((-50, 50, 50, -50), fill=(0, 0, 255), width=2)
draw.rectangle((-100, -100, 100, 100), outline=(0, 255, 0), width=2)

draw.set_abs_origin((.8, .5)) \
    .rectangle((-10, -10, 10, 10), outline=(255, 0, 0), width=2)
draw.set_abs_origin((.2, .5)) \
    .rectangle((-10, -10, 10, 10), outline=(255, 0, 0), width=2)

draw.set_origin('center')
font = ImageFont.truetype("arial.ttf", 24)
draw.text(
    (0, 0), "Hello", fill=(255, 255, 255),
    font=font, anchor='mm',
    stroke_width=2, stroke_fill='green',
)

img.show()
