"""Regenerate committed app icons; optional development dependency: Pillow.

Run with Python and Pillow, optionally passing an Open Sans Bold TTF path.
The normal app build uses committed PNGs and does not require Pillow or fonts.
"""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
font_path=sys.argv[1] if len(sys.argv)>1 else '/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf'
scale=3
image=Image.new('RGB',(512*scale,512*scale),'#163c35')
draw=ImageDraw.Draw(image)
font=ImageFont.truetype(font_path,170*scale)
draw.text((256*scale,220*scale),'360',font=font,anchor='mm',fill='#fffefa')
points=[(115,335),(178,280),(220,320),(285,272),(340,312),(397,277)]
draw.line([(x*scale,y*scale) for x,y in points],fill='#f4bd66',width=12*scale,joint='curve')
r=9*scale
for x,y in [points[0],points[-1]]:draw.ellipse((x*scale-r,y*scale-r,x*scale+r,y*scale+r),fill='#f4bd66')
for size in [192,512]:image.resize((size,size),Image.Resampling.LANCZOS).save(ROOT/'icons'/f'icon-{size}.png',optimize=True)
