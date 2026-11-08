"""Shared Windows/cross-platform tool discovery and video helpers.

Automatically locates FFmpeg, MinGW-w64 GCC, Tesseract OCR, and Arial fonts
without requiring a hardcoded 'C:\\Users\\asus' username.
"""

import shutil
import subprocess
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]


def find_ffmpeg() -> Path:
    try:
        import imageio_ffmpeg

        exe = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if exe.exists():
            return exe
    except Exception:
        pass
    for candidate in (
        Path.home()
        / "AppData/Local/Programs/Python/Python313/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe",
        Path(
            r"C:\Users\asus\AppData\Local\Programs\Python\Python313\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
        ),
    ):
        if candidate.exists():
            return candidate
    which_ff = shutil.which("ffmpeg")
    if which_ff:
        return Path(which_ff)
    return Path(
        r"C:\Users\asus\AppData\Local\Programs\Python\Python313\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
    )


def find_gcc() -> Path:
    for candidate in (
        Path(r"C:\winlibs\mingw64\bin\gcc.exe"),
        Path(r"C:\msys64\mingw64\bin\gcc.exe"),
    ):
        if candidate.exists():
            return candidate
    which_gcc = shutil.which("x86_64-w64-mingw32-gcc")
    if which_gcc:
        return Path(which_gcc)
    return Path(r"C:\winlibs\mingw64\bin\gcc.exe")


def find_tesseract() -> Path:
    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path("/opt/homebrew/bin/tesseract"),
    ):
        if candidate.exists():
            return candidate
    which_tess = shutil.which("tesseract")
    if which_tess:
        return Path(which_tess)
    return Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


def load_font(size: int, bold: bool = False):
    name = "arialbd.ttf" if bold else "arial.ttf"
    mac_name = "Arial Bold.ttf" if bold else "Arial.ttf"
    for path in (
        Path(rf"C:\Windows\Fonts\{name}"),
        Path(f"/System/Library/Fonts/Supplemental/{mac_name}"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.truetype(rf"C:\Windows\Fonts\{name}", size)


FFMPEG = find_ffmpeg()
GCC = find_gcc()
TESS = find_tesseract()
DETECT = ROOT / "src" / ("detect" if (ROOT / "src" / "detect").exists() else "detect.exe")
TIMER = ROOT / "src" / ("time_kernel" if (ROOT / "src" / "time_kernel").exists() else "time_kernel.exe")
DATA = ROOT / "data"
RESULTS = ROOT / "results"
