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
    # 16/11 v2 MSY: TUM sikistirma yontemleri (ZIP/LZW/JBIG/LZMA/Deflate)
    # + Photoshop layered + 16-bit CMYK desteklenir. Pillow once denenir,
    # olmazsa tifffile (TIFF uzmani) acar.
    try:
        im = Image.open(yol)
    except Exception as e:
        _tip = _tiff_sihirli(yol)
        if _tip != 'tiff':
            raise ValueError(
                f"Dosya formati taninamadi (magic: {_tip}). "
                f"Dosya gercekten .tif/.tiff mi? Photoshop'tan 'TIFF' olarak kaydedin.")
        im = _tifffile_ac(yol, e)
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
    # 16/11 v2: Pillow olmazsa tifffile (tum sikistirmalar)
    try:
        im = Image.open(yol)
    except Exception as e:
        _tip = _tiff_sihirli(yol)
        if _tip != 'tiff':
            raise ValueError(f"Dosya TIF degil (magic: {_tip}).")
        im = _tifffile_ac(yol, e)
        _dx = _tifffile_dpi(yol)
        arr = np.array(im.convert('RGBA'), dtype=np.uint8)
        return arr, (_dx, _dx)
    with im as im:
        dpi = im.info.get('dpi') or (300.0, 300.0)
        try:
            dx, dy = float(dpi[0]), float(dpi[1])
        except (TypeError, IndexError, ValueError):
            dx = dy = 300.0
        rgba = im.convert('RGBA')
        arr = np.array(rgba, dtype=np.uint8)
    return arr, (dx or 300.0, dy or 300.0)


def _tifffile_ac(yol: str, orijinal_hata: Exception):
    """16/11 v2: Pillow'un acamadigi TIFF'leri tifffile ile ac.

    Destek (Pillow'un desteklemedikleri dahil):
      - ZIP / Deflate / LZW / JBIG / LZMA sikistirma
      - Photoshop layered TIFF (8BIM / tag 34375)
      - 16-bit CMYK / Lab / BigTIFF
    Donus: PIL.Image
    """
    try:
        import tifffile
        import numpy as _np
    except ImportError:
        raise ValueError(
            f"Pillow bu TIFF'i acamadi: {orijinal_hata}\n"
            f"tifffile kutuphanesi eksik. Programi guncelle.")
    try:
        arr = tifffile.imread(yol)
        if arr.ndim == 3 and arr.shape[-1] >= 3:
            rgb = arr[..., :3]
        elif arr.ndim == 2:
            rgb = arr
        else:
            rgb = arr
        if rgb.dtype != _np.uint8:
            _mx = float(rgb.max()) or 1.0
            rgb = (rgb.astype(_np.float32) / _mx * 255.0).astype(_np.uint8)
        if rgb.ndim == 2:
            return Image.fromarray(rgb, mode='L')
        return Image.fromarray(rgb, mode='RGB')
    except Exception as e2:
        raise ValueError(
            f"TIFF acilamadi (Pillow: {str(orijinal_hata)[:60]} | "
            f"tifffile: {str(e2)[:60]}). Dosya bozuk olabilir.")


def _tifffile_dpi(yol: str):
    """tifffile ile DPI oku (XResolution tag)."""
    try:
        import tifffile as _tf
        with _tf.TiffFile(yol) as tf:
            pg = tf.pages[0]
            tag = pg.tags.get('XResolution')
            if tag is not None:
                v = tag.value
                if isinstance(v, (list, tuple)) and len(v) >= 2:
                    return float(v[0]) / float(v[1]) if v[1] else float(v[0])
                return float(v)
    except Exception:
        pass
    return 300.0


def ham_oku(yol):
    """Ham TIFF kanallarini tifffile ile oku.

    Donus: (arr (h, w, n) uint8, dpi) — CMYK/spot TIF'lerde:
      5 kanal: [C, M, Y, K, alpha]
      6 kanal: [C, M, Y, K, alpha, spot/beyaz]
    Pillow 4 kanaldan fazlasini RGBA'ya ezer (C,M,Y'yi RGB sanip K ve
    alpha'yi kaybediyordu). Bu fonksiyon ham kanallari korur.
    CMYK/spot olmayan dosyalarda None doner (cagiran klasik yola duser).
    """
    try:
        import tifffile
    except ImportError:
        return None
    try:
        arr = tifffile.imread(yol)
    except Exception:
        return None
    if arr.ndim != 3 or arr.shape[2] < 5 or arr.dtype != np.uint8:
        return None
    dx = _tifffile_dpi(yol) if hasattr(_tifffile_dpi, '__call__') else 300.0
    try:
        dx = float(dx)
    except Exception:
        dx = 300.0
    return arr, (dx, dx)
