DailyPulse image converter for Windows
====================================

1. Install Python 3 (if not installed) from https://www.python.org/downloads/windows/
   Ensure Python is available from PATH / py launcher.
2. Copy both files (convert_images.py and convert_images.bat) into the
   blackout-to-tg repository root (next to morning and evening folders).
3. Double click convert_images.bat.
4. It converts all WebP and PNG pictures found under morning/pict and evening/pict,
   including all seasonal subdirectories, into JPG with the same file names.
   Existing JPEG and existing target files are NEVER overwritten.
   Original files are NEVER deleted.
5. Check resulting JPG files in Windows Explorer.
6. Remove old .webp/.png originals manually (and do not commit both sets).
7. Commit only the intended images with TortoiseGit.

Important:
- Conversion from WebP to JPG can slightly increase file size or lose some quality.
- Transparent areas become white because JPG has no transparency.
- Numbering like 01.webp becomes 01.jpg.
- Any .jpg/.jpeg files remain unchanged.
