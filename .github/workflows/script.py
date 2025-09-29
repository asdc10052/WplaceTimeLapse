import aiohttp, asyncio, io, json, os, re, warnings
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageChops

class WplaceTimeLapse:
    
    def __init__(self, target):
        self.setup(target)
        try:
            asyncio.run(self.fetchs())
            self.png()
            self.gif()
        except NotChanged:
            print(f"> 동일한 이미지")
        except Exception as e:
            print(f"> 오류 발생: {e}")
    
    def setup(self, target):
        self.timestamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d %H%M%S')
        self.dirname = target['name']
        self.pngname = f"{self.dirname}/{self.timestamp}.png"
        self.gifname = f"{self.dirname}/{self.dirname}.gif"
        os.makedirs(self.dirname, exist_ok=True)
        start = re.search(r"\(Tl X: (\d*), Tl Y: (\d*), Px X: (\d*), Px Y: (\d*)\)", target['start'])
        end = re.search(r"\(Tl X: (\d*), Tl Y: (\d*), Px X: (\d*), Px Y: (\d*)\)", target['end'])
        self.tx1, self.ty1, self.px1, self.py1 = map(int, start.groups())
        self.tx2, self.ty2, self.px2, self.py2 = map(int, end.groups())
        self.txl, self.tyl = self.tx2 - self.tx1 + 1, self.ty2 - self.ty1 + 1
        print(f"[{self.dirname}] ({self.txl}x{self.tyl})")
    
    async def fetchs(self):
        async with aiohttp.ClientSession() as session:
            async def fetch(x, y):
                try:
                    async with session.get(f"https://backend.wplace.live/files/s0/tiles/{x}/{y}.png") as response:
                        response.raise_for_status()
                        data = await response.read()
                        return (x, y, Image.open(io.BytesIO(data)).convert("RGBA"))
                except Exception:
                    print(f"> 다운로드 실패 ({x}, {y})")
                    return (x, y, None)
            tasks = [fetch(x, y) for x in range(self.tx1, self.tx2 + 1) for y in range(self.ty1, self.ty2 + 1)]
            self.imgs = await asyncio.gather(*tasks)
        
    def png(self):
        canvas = Image.new("RGBA", (self.txl*1000, self.tyl*1000), (0,0,0,0))
        for x, y, img in self.imgs:
            if img:
                canvas.paste(img, ((x-self.tx1)*1000, (y-self.ty1)*1000), img)
        canvas = canvas.crop((self.px1, self.py1, (self.txl-1)*1000+self.px2+1, (self.tyl-1)*1000+self.py2+1))
        canvas = canvas.convert("P", palette=Image.ADAPTIVE, colors=64)
        png_files = sorted([f for f in os.listdir(self.dirname) if f.endswith(".png")])
        if png_files:
            if ImageChops.difference(Image.open(os.path.join(self.dirname, png_files[-1])), canvas).getbbox() is None:
                raise NotChanged()
        canvas.save(self.pngname)
        print(f'> {self.pngname}')

    def gif(self):
        warnings.filterwarnings("ignore", message="Palette images with Transparency expressed in bytes should be converted to RGBA images")
        frames = sorted([Image.open(os.path.join(self.dirname, f)) for f in os.listdir(self.dirname) if f.endswith(".png")])
        frames[0].save(self.gifname, save_all=True, append_images=frames[1:], duration=100, loop=0, transparency=1, disposal=2)
        print(f'> {self.gifname}')

class NotChanged(Exception):
    pass

if __name__ == "__main__":
    targets = json.load(open('.github/workflows/config.json', 'r'))['targets']
    for target in targets:
        if target['enabled']:
            WplaceTimeLapse(target)
