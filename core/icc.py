"""ICC profil dönüşümü (RGB → CMYK).

Pillow'un ImageCms modülü (littlecms gömülü) kullanılır; ek bağımlılık yok.
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageCms

INTENTLER = {
    'Perceptual': ImageCms.Intent.PERCEPTUAL,
    'Relative': ImageCms.Intent.RELATIVE_COLORIMETRIC,
    'Saturation': ImageCms.Intent.SATURATION,
    'Absolute': ImageCms.Intent.ABSOLUTE_COLORIMETRIC,
}


def profil_bilgi(yol: str) -> dict:
    """ICC dosyasının temel bilgisi (renk uzayı, sınıf)."""
    if not yol or not os.path.exists(yol):
        return {'ok': False, 'hata': 'dosya yok'}
    try:
        p = ImageCms.getOpenProfile(yol)
        prof = p.profile
        return {
            'ok': True,
            'ad': os.path.basename(yol),
            'renk_uzayi': (getattr(prof, 'xcolor_space', '') or '').strip(),
            'pcs': (getattr(prof, 'connection_space', '') or '').strip(),
            'sinif': (getattr(prof, 'device_class', '') or '').strip(),
            'versiyon': str(getattr(prof, 'icc_version', '')),
        }
    except Exception as e:
        return {'ok': False, 'hata': str(e)[:100]}


def rgb_to_cmyk(rgb: np.ndarray, icc_yol: str = None,
                intent: str = 'Perceptual', bpc: bool = True):
    """RGB (h,w,3 uint8) → CMYK (h,w,4 uint8).

    icc_yol verilmezse basit formül kullanılır (profil yoksa).
    """
    from core.settings import ayarlar_profil_yolu
    icc_yol = ayarlar_profil_yolu(icc_yol)
    if icc_yol and os.path.exists(icc_yol):
        try:
            img = Image.fromarray(rgb, mode='RGB')
            src = ImageCms.createProfile('sRGB')
            dst = ImageCms.getOpenProfile(icc_yol)
            out = ImageCms.profileToProfile(
                img, src, dst,
                renderingIntent=INTENTLER.get(intent, ImageCms.Intent.PERCEPTUAL),
                outputMode='CMYK',
                blackPointCompensation=bpc,
            )
            return np.array(out, dtype=np.uint8)
        except Exception:
            pass  # düş → basit formül
    return _basit_cmyk(rgb)


def _basit_cmyk(rgb: np.ndarray) -> np.ndarray:
    """Profil yoksa hızlı RGB→CMYK (GCR yok, saf dönüşüm)."""
    r = rgb[:, :, 0].astype(np.float32) / 255.0
    g = rgb[:, :, 1].astype(np.float32) / 255.0
    b = rgb[:, :, 2].astype(np.float32) / 255.0
    k = 1.0 - np.maximum(np.maximum(r, g), b)
    k_safe = np.where(k >= 1.0, 1.0, k)
    c = (1.0 - r - k_safe) / np.where(k_safe >= 1.0, 1.0, 1.0 - k_safe)
    m = (1.0 - g - k_safe) / np.where(k_safe >= 1.0, 1.0, 1.0 - k_safe)
    y = (1.0 - b - k_safe) / np.where(k_safe >= 1.0, 1.0, 1.0 - k_safe)
    out = np.stack([c, m, y, k], axis=2)
    out = np.clip(out, 0.0, 1.0) * 255.0
    return out.astype(np.uint8)
