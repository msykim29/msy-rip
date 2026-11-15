# resources/

`msyrip.ico` — program ikonu (256x256, çoklu boyut).
Yoksa PyInstaller varsayılan ikon kullanır.

İkon üretmek için:
```bash
python -c "
from PIL import Image, ImageDraw
im = Image.new('RGBA',(256,256),(0,0,0,0))
d = ImageDraw.Draw(im)
d.ellipse([16,16,240,240], fill=(37,99,235,255))
d.ellipse([80,80,176,176], fill=(255,255,255,255))
im.save('resources/msyrip.ico', sizes=[(16,16),(32,32),(48,48),(128,128),(256,256)])
"
```
