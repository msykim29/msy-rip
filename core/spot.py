"""Spot katmanı üretimi + choke (daraltma).

MSY Rip: her TIF için 0 / 1 / 2 piksel daraltma seçilir.
- 0 → alpha olduğu gibi (tam kapsama)
- 1 → spot 1 piksel İÇE daraltılır (choke) → beyaz kenardan taşmaz
- 2 → 2 piksel içe daraltılır

Yöntem: binary alpha maskesi üzerinde erozyon (minimum filtresi).
Sadece numpy kullanılır (scipy bağımlılığı yok).
"""
from __future__ import annotations

import numpy as np


def alpha_maske(rgba: np.ndarray, esik: int = 128) -> np.ndarray:
    """RGBA dizisinden binary maske (True = mürekkep var)."""
    if rgba.ndim != 3 or rgba.shape[2] < 4:
        raise ValueError("RGBA (h, w, 4) bekleniyor")
    return rgba[:, :, 3] >= esik


def erode(maske: np.ndarray, piksel: int = 1) -> np.ndarray:
    """Binary maskeyi N piksel içe daralt (4-komşu erozyon).

    piksel=0 → maske aynen döner.
    """
    if piksel <= 0:
        return maske
    m = maske.astype(bool)
    for _ in range(int(piksel)):
        # 4-komşu: üst, alt, sol, sağ hepsi dolu olmalı
        k = m.copy()
        k[1:, :] &= m[:-1, :]     # üstten
        k[:-1, :] &= m[1:, :]     # alttan
        k[:, 1:] &= m[:, :-1]     # soldan
        k[:, :-1] &= m[:, 1:]     # sağdan
        # kenarlar: dışarısı boş sayılır → kenar pikseli düşer
        k[0, :] = False
        k[-1, :] = False
        k[:, 0] = False
        k[:, -1] = False
        m = k
    return m


def spot_kanali(rgba: np.ndarray, daraltma: int = 1, esik: int = 128) -> np.ndarray:
    """Spot (beyaz) katmanını uint16 olarak üret.

    Döner: np.ndarray uint16 (h, w), 0 = spot yok, 65535 = tam spot.
    """
    m = alpha_maske(rgba, esik=esik)
    if daraltma > 0:
        m = erode(m, daraltma)
    return (m.astype(np.uint16) * 65535)


def kapsama_orani(maske: np.ndarray) -> float:
    """Maskenin dolu oranı (0..1) — teşhis/log için."""
    if maske.size == 0:
        return 0.0
    return float(np.count_nonzero(maske)) / float(maske.size)
