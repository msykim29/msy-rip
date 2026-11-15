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


def bilgi_oku(yol: str) -> TifBilgi:
    """TIF dosyasının meta bilgisini oku (görüntüyü belleğe almadan)."""
    with Image.open(yol) as im:
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
    with Image.open(yol) as im:
        dpi = im.info.get('dpi') or (300.0, 300.0)
        try:
            dx, dy = float(dpi[0]), float(dpi[1])
        except (TypeError, IndexError, ValueError):
            dx = dy = 300.0
        rgba = im.convert('RGBA')
        arr = np.array(rgba, dtype=np.uint8)
    return arr, (dx or 300.0, dy or 300.0)
