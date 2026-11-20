"""Deterministic reference-still calibration under the user's existing permission.

Uses imagegen's photographic subjects; changes reference layout/scale only, no video.
"""
from pathlib import Path
from collections import deque
import hashlib
import json
import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont

R = Path(__file__).resolve().parents[2]
P = R / 'projects/悬崖上的小气球'
O = P / '02-素材/参考图/龙与果树高度参考28'
SOURCE = Path('C:/Users/long/.codex/generated_images/01a1c83f-3fe5-7412-b65c-29237be12733/exec-4e2a4103-44fd-4c6f-b5ef-89986a2ef56b.png')
BASE = 850
TREE_H = 720
DRAGON_H = 72


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(image, box, kind):
    patch = image.crop(box).convert('RGB')
    mask = Image.new('L', patch.size, 0)
    for y in range(patch.height):
        for x in range(patch.width):
            rr, gg, bb = patch.getpixel((x, y))
            if kind == 'tree':
                vegetation = gg > rr + 2 and gg > bb + 8
                wood = rr > bb + 17 and gg > bb + 7 and rr - gg < 80
                berry = rr > gg + 25 and rr > bb + 20
                keep = min(rr, gg, bb) < 192 and (vegetation or wood or berry)
                # Below the canopy, only the trunk/root corridor belongs to the
                # tree; exclude the neighbouring original dragon from this ROI.
                if box[1] + y > 370 and not 390 <= box[0] + x <= 630:
                    keep = False
            else:
                keep = rr > gg + 17 and rr > bb + 7
                keep = keep or (rr > gg + 12 and bb > gg + 3)
            if keep:
                mask.putpixel((x, y), 255)
    # Close tiny material holes, then fill enclosed eyes/claws without retaining
    # the cream background or the old neutral gray ruler/dashed lines.
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    padded = Image.new('L', (mask.width + 4, mask.height + 4), 0)
    padded.paste(mask, (2, 2))
    ImageDraw.floodfill(padded, (0, 0), 128, thresh=0)
    pixels = padded.load()
    for y in range(padded.height):
        for x in range(padded.width):
            pixels[x, y] = 0 if pixels[x, y] == 128 else 255
    mask = padded.crop((2, 2, mask.width + 2, mask.height + 2))
    if kind == 'dragon':
        # Generated shrink edits can leave tiny detached old horn fragments.
        # Keep only the connected physical creature, excluding background specks.
        seen = set()
        largest = []
        for y in range(mask.height):
            for x in range(mask.width):
                if (x, y) in seen or mask.getpixel((x, y)) == 0:
                    continue
                group = []
                queue = deque([(x, y)])
                seen.add((x, y))
                while queue:
                    xx, yy = queue.popleft()
                    group.append((xx, yy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = xx + dx, yy + dy
                        if (0 <= nx < mask.width and 0 <= ny < mask.height
                                and (nx, ny) not in seen and mask.getpixel((nx, ny))):
                            seen.add((nx, ny))
                            queue.append((nx, ny))
                if len(group) > len(largest):
                    largest = group
        clean = Image.new('L', mask.size, 0)
        for xy in largest:
            clean.putpixel(xy, 255)
        mask = clean
    bounds = mask.getbbox()
    assert bounds, kind
    patch = patch.convert('RGBA')
    patch.putalpha(mask)
    patch = patch.crop(bounds)
    return patch, {'source_box': list(box), 'local_foreground_box': list(bounds)}


def normalize_height(subject, height):
    width = round(subject.width * height / subject.height)
    subject = subject.resize((width, height), Image.Resampling.LANCZOS)
    assert subject.getchannel('A').getbbox()[1::2] == (0, height)
    return subject


def main():
    O.mkdir(parents=True, exist_ok=True)
    destination = O / '龙与果树-高度参考-校准05.png'
    assert not destination.exists(), 'Preserve existing reference.'
    candidate = O / '龙与果树-高度参考-候选02.png'
    if not candidate.exists():
        shutil.copy2(SOURCE, candidate)
    im = Image.open(candidate).convert('RGB')
    tree, tree_record = extract(im, (310, 110, 1160, 841), 'tree')
    clean_source = O / '龙与果树-高度参考-候选01.png'
    dragon, dragon_record = extract(Image.open(clean_source).convert('RGB'), (1090, 680, 1350, 841), 'dragon')
    dragon_record['photographic_source'] = str(clean_source)
    dragon_record['photographic_source_sha256'] = sha(clean_source)
    tree = normalize_height(tree, TREE_H)
    dragon = normalize_height(dragon, DRAGON_H)
    tree_xy = (330, BASE - TREE_H)
    dragon_xy = (1130, BASE - DRAGON_H)
    canvas = Image.new('RGBA', (1536, 1024), (250, 244, 235, 255))
    draw = ImageDraw.Draw(canvas)
    ink = (30, 32, 31, 255)
    font = lambda size: ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', size)
    regular = lambda size: ImageFont.truetype('C:/Windows/Fonts/arial.ttf', size)
    draw.text((768, 42), 'HEIGHT REFERENCE', anchor='mm', font=font(64), fill=ink)

    ticks = []
    for cm in range(0, 201, 5):
        y = BASE - cm * TREE_H / 200
        major = cm % 20 == 0
        draw.line((128 if major else 138, y, 160 if major else 151, y), fill=ink, width=2)
        if major:
            draw.text((115, y), str(cm), anchor='rm', font=regular(34), fill=ink)
            ticks.append({'cm': cm, 'y': y})
    draw.line((143, BASE - TREE_H, 143, BASE), fill=ink, width=2)
    draw.line((125, BASE, 1440, BASE), fill=ink, width=3)
    for y, end in ((BASE - TREE_H, 550), (BASE - DRAGON_H, 1200)):
        for x in range(165, end, 14):
            draw.line((x, y, min(x + 7, end), y), fill=(75, 77, 74, 255), width=1)

    def arrow(x, top, bottom):
        draw.line((x, top + 5, x, bottom - 5), fill=ink, width=3)
        draw.polygon(((x, top), (x - 8, top + 15), (x + 8, top + 15)), fill=ink)
        draw.polygon(((x, bottom), (x - 8, bottom - 15), (x + 8, bottom - 15)), fill=ink)

    arrow(282, BASE - TREE_H, BASE)
    draw.rectangle((206, 470, 365, 516), fill=(250, 244, 235, 255))
    draw.text((282, 493), '200 cm', anchor='mm', font=font(38), fill=ink)
    arrow(1068, BASE - DRAGON_H, BASE)
    draw.text((1045, BASE - DRAGON_H / 2), '20 cm', anchor='rm', font=font(37), fill=ink)

    # Soft localized grounding shadows belong to the reference plate only.
    shadow = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((425, BASE - 2, 575, BASE + 4), fill=(60, 50, 35, 35))
    sd.ellipse((dragon_xy[0] + 8, BASE - 2, dragon_xy[0] + dragon.width - 5, BASE + 3), fill=(60, 50, 35, 30))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(2)))
    canvas.alpha_composite(tree, tree_xy)
    canvas.alpha_composite(dragon, dragon_xy)
    draw = ImageDraw.Draw(canvas)
    draw.text((500, 890), 'BERRY SAPLING', anchor='mm', font=font(40), fill=ink)
    draw.text((dragon_xy[0] + dragon.width / 2, 890), 'GULU', anchor='mm', font=font(40), fill=ink)
    draw.text((768, 970), 'TREE : GULU = 10 : 1', anchor='mm', font=font(45), fill=ink)
    canvas.convert('RGB').save(destination)
    record = {
        'source': str(candidate), 'source_sha256': sha(candidate),
        'output': str(destination), 'sha256': sha(destination),
        'permission': '06-记录/用户确认/参考静图确定性精修允许04.json',
        'method': 'Imagegen photographic subjects; deterministic uniform reference-subject rescale, shared baseline and vector-raster ruler typography. No video edit.',
        'tree': {**tree_record, 'canvas_xy': tree_xy, 'height_pixels': TREE_H, 'label_cm': 200},
        'dragon': {**dragon_record, 'canvas_xy': dragon_xy, 'height_pixels': DRAGON_H, 'label_cm': 20},
        'baseline_y': BASE, 'ratio': TREE_H / DRAGON_H,
        'ruler_major_ticks': ticks, 'minor_cm_step': 5,
        'height_measurement': 'Ground to tree apex / natural four-paw dragon highest horn; includes head/horns, excludes tail/wings',
        'new_video_submissions': 0, 'user_acceptance': 'pending',
        'status': 'WAIT_VISUAL_INSPECTION',
    }
    f = P / '05-检查与验收/龙与果树高度参考28-确定性校准05.json'
    f.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(destination), 'tree_px': TREE_H, 'dragon_px': DRAGON_H, 'ratio': TREE_H / DRAGON_H}, ensure_ascii=False))


if __name__ == '__main__':
    main()
