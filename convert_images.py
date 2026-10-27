from pathlib import Path
from PIL import Image, ImageOps
import sys

ROOT = Path(__file__).resolve().parent
EXPECTED = [ROOT / 'morning' / 'pict', ROOT / 'evening' / 'pict']

# Converter is placed in the repository root, alongside morning/ and evening/.
# Scan WebP and PNG recursively; JPEG files are already suitable.
def main():
    print('DailyPulse image converter: WebP/PNG -> JPEG')
    print(f'Repository: {ROOT}')
    if not any(p.is_dir() for p in EXPECTED):
        print('ERROR: Place these two files in the blackout-to-tg repository root.')
        print('Expected morning/pict and evening/pict directories.')
        return 1

    converted = 0
    skipped = 0
    failed = 0
    for folder in EXPECTED:
        if not folder.exists():
            print(f'WARNING: directory not found: {folder.relative_to(ROOT)}')
            continue
        sources = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ('.webp', '.png'))
        for source in sources:
            target = source.with_suffix('.jpg')
            if target.exists():
                print(f'SKIP: {target.relative_to(ROOT)} already exists; no overwrite')
                skipped += 1
                continue
            try:
                with Image.open(source) as im:
                    im = ImageOps.exif_transpose(im)
                    if im.mode in ('RGBA', 'LA') or 'transparency' in im.info:
                        rgba = im.convert('RGBA')
                        background = Image.new('RGB', rgba.size, (255, 255, 255))
                        background.paste(rgba, mask=rgba.getchannel('A'))
                        rgb = background
                    else:
                        rgb = im.convert('RGB')
                    rgb.save(target, 'JPEG', quality=88, optimize=True, progressive=True)
                    with Image.open(target) as test:
                        test.verify()
                print(f'OK: {source.relative_to(ROOT)} -> {target.name}')
                converted += 1
            except Exception as e:
                failed += 1
                target.unlink(missing_ok=True)
                print(f'ERROR: {source.relative_to(ROOT)}: {e}')
    print(f'\nDone: converted={converted}, skipped={skipped}, errors={failed}')
    print('Original .webp/.png images were NOT deleted.')
    print('After checking your JPG images, remove original WebP files manually before committing.')
    return 1 if failed else 0

if __name__ == '__main__':
    sys.exit(main())
