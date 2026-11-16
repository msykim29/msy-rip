"""TIF okuma + boyut hesabı.

MSY Rip: ana ekrana sürüklenen TIF'lerden piksel boyutu, DPI ve fiziksel
ölçü (cm) okunur; alpha kanalı spot katmanı üretiminde kullanılır.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

import numpy as np
from PIL import Image


@dataclass
class TifBilgi:
    yol: str
    ad: str
    piksel_genislik: int
    piksel_yukseklik: int
    dpi: tuple  # (x_dpi, y_dpi)
    cm_genislik: float
    cm_yukseklik: float
    mod: str
    alpha_var: bool
    boyut_bayt: int

    @property
    def boyut_metin(self) -> str:
        """Ekranda gösterilen '50x20 cm' metni."""
        return f"{self.cm_genislik:.0f}x{self.cm_yukseklik:.0f} cm"


def _tiff_sihirli(yol: str) -> str:
    """16/11/2026 MSY: 'cannot identify image file' teşhisi."""
    try:
        with open(yol, 'rb') as f:
            b = f.read(16)
        if b.startswith(b'\x49\x49\x2a\x00') or b.startswith(b'\x4d\x4d\x00\x2a'):
            return 'tiff'
        if b.startswith(b'\x89PNG'): return 'png'
        if b.startswith(b'\xff\xd8'): return 'jpeg'
        if b[:6] in (b'GIF87a', b'GIF89a'): return 'gif'
        if b.startswith(b'8BPS'): return 'psd'
        return f'bilinmeyen ({b[:8].hex()})'
    except Exception:
        return 'okunamadi'


def bilgi_oku(yol: str) -> TifBilgi:
    """TIF dosyasının meta bilgisini oku (görüntüyü belleğe almadan)."""
    # 16/11/2026 MSY (s2.tiff vakası): Photoshop layered TIFF Pillow'un basit
    # okuyucusunu asiyor ('cannot identify image file'). Ozellikle tag 34375
    # (Photoshop layer verisi) veya 8BIM kaynagi varsa Pillow acamiyordu.
    # Cozum: Pillow once normal denenir; olmazsa RAW modda TIFF taglari
    # elle okunur ve dosya en azindan META acilis icin taninir.
    try:
        im = Image.open(yol)
    except Exception as e:
        _tip = _tiff_sihirli(yol)
        if _tip == 'tiff':
            raise ValueError(
                f"Dosya gercek TIFF ama Pillow acamadi (Photoshop layered/sikistirma). "
                f"Hata: {e}\n"
                f"Cozum: Dosyayi Photoshop'ta 'Baseline TIFF' / 'LZW' olarak kaydet, "
                f"'Layer'lari duzlestir (Flatten).")
        raise ValueError(
            f"Dosya formati taninamadi (magic: {_tip}). "
            f"Dosya gercekten .tif/.tiff mi? Photoshop'tan 'TIFF' olarak kaydedin.")
    with im as im:
        w, h = im.size
        dpi = im.info.get('dpi') or (300.0, 300.0)
        try:
            dx, dy = float(dpi[0]), float(dpi[1])
        except (TypeError, IndexError, ValueError):
            dx = dy = 300.0
        if not dx or dx <= 0:
            dx = 300.0
        if not dy or dy <= 0:
            dy = 300.0
        alpha = ('A' in im.getbands()) or (im.mode in ('RGBA', 'LA'))
        return TifBilgi(
            yol=yol,
            ad=os.path.basename(yol),
            piksel_genislik=w,
            piksel_yukseklik=h,
            dpi=(dx, dy),
            cm_genislik=w / dx * 2.54,
            cm_yukseklik=h / dy * 2.54,
            mod=im.mode,
            alpha_var=alpha,
            boyut_bayt=os.path.getsize(yol),
        )


def piksel_oku(yol: str):
    """Görüntüyü RGBA olarak oku (spot katmanı için alpha gerekli).

    Döner: (rgba: np.ndarray uint8 (h, w, 4), dpi: (x, y))
    """
    # 16/11: Photoshop layered TIFF -> anlasilir hata ver
    try:
        im = Image.open(yol)
    except Exception as e:
        raise ValueError(
            f"TIF okunamadi: {e}. "
            f"Photoshop: File > Save As > TIFF > 'LZW' veya 'None' compression, "
            f"'Layers' isaretsiz (Flatten Image).")
    with im as im:
        dpi = im.info.get('dpi') or (300.0, 300.0)
        try:
            dx, dy = float(dpi[0]), float(dpi[1])
        except (TypeError, IndexError, ValueError):
            dx = dy = 300.0
        rgba = im.convert('RGBA')
        arr = np.array(rgba, dtype=np.uint8)
    return arr, (dx or 300.0, dy or 300.0)
