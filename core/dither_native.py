"""MSY Rip — PM22 (SAi Flexi) dither.dll köprüsü.

Dither.dll + 24 bağımlılık `resources/dither_native/` altında taşınır.
StochasticHalftone sınıfı (ordinal 24) oluşturulur, Action16 (ordinal 86)
ile 16-bit kanal dither edilir.

Kullanım:
    from core.dither_native import Pm22Dither
    with Pm22Dither(kanal_sayisi=8, seviye=16) as d:
        cikti = d.uygula(gri_0_1)   # (H, W) float 0..1 -> (H, W) uint16
"""
from __future__ import annotations

import ctypes
import os
import sys

BASE = os.path.join(
    getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'resources', 'dither_native')

_CACHE = {}


def _yukle():
    if 'dll' in _CACHE:
        return _CACHE['dll']
    if not hasattr(ctypes, 'WinDLL'):
        raise OSError('PM22 dither sadece Windows\'ta çalışır')
    try:
        ctypes.windll.kernel32.SetDllDirectoryW(BASE)
    except Exception:
        pass
    yol = os.path.join(BASE, 'Dither.dll')
    if not os.path.exists(yol):
        raise OSError('Dither.dll bulunamadı: %s' % yol)
    try:
        h = ctypes.WinDLL(yol)
    except OSError as e:
        raise OSError('Dither.dll yüklenemedi: %s' % e)
    _CACHE['dll'] = h
    return h


class Pm22Dither:
    """StochasticHalftone — PM22'nin gerçek blue-noise halftone motoru."""

    OBJ_BOYUT = 0x40000

    def __init__(self, kanal_sayisi: int = 8, seviye: int = 16,
                 agirlik: tuple | None = None):
        self.dll = _yukle()
        self.kanal = int(kanal_sayisi)
        self.seviye = int(seviye)
        self._obj = ctypes.create_string_buffer(self.OBJ_BOYUT)
        self._agirlik = (ctypes.c_float * 16)(
            *(agirlik or (0.28, 0.56, 1.0, 0.0,
                          0.28, 0.56, 1.0, 0.0,
                          0.28, 0.56, 1.0, 0.0,
                          0.28, 0.56, 1.0, 0.0)))
        self._ctor = self.dll[24]
        self._action16 = self.dll[86]
        self._hazirla_ctor()

    def _hazirla_ctor(self):
        # KKKKK QAY0EA@M HHH PAN1111H N
        proto = ctypes.CFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_void_p,          # this
            ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_uint, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int)
        addr = ctypes.cast(self._ctor, ctypes.c_void_p).value
        fn = proto(addr)
        fn(self._obj, self.kanal, 255, 255, self.seviye, 16,
           self._agirlik, 0, 0, 0, None, None, None, None, 0, 0)

    def uygula(self, gri):
        """gri: (H, W) float 0..1 → (H, W) uint8 dither maskesi."""
        import numpy as np
        g = np.clip(np.asarray(gri, dtype=np.float32), 0.0, 1.0)
        h, w = g.shape
        g16 = (g * 65535.0).astype(np.uint16)
        cikti = np.zeros((h, w), dtype=np.uint8)
        S = ctypes.POINTER(ctypes.c_uint16)
        B = ctypes.POINTER(ctypes.c_uint8)
        inp = (S * h)()
        outp = (B * h)()
        yaz = g16.ctypes.data
        cyaz = cikti.ctypes.data
        for y in range(h):
            inp[y] = ctypes.cast(yaz + y * w * 2, S)
            outp[y] = ctypes.cast(cyaz + y * w, B)
        proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.c_uint,
                                 ctypes.POINTER(S), ctypes.POINTER(B))
        fn = proto(ctypes.cast(self._action16, ctypes.c_void_p).value)
        fn(self._obj, w, inp, outp)
        return cikti

    def kapat(self):
        self._obj = None


def kullanilabilir() -> bool:
    try:
        _yukle()
        return True
    except Exception:
        return False
