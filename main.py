"""MSY Rip — giriş noktası."""
from __future__ import annotations

import sys
import os

# paket yolu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import AnaEkran  # noqa: E402


def _hata_gunlugu(exc_tipi, deger, tb):
    """24/11 MSY: 'riplemiyor, kapaniyor' — sessiz cokmeyi teshis etmek icin
    tum yakalanmamis hatalar crash.log'a yazilir ve kullaniciya gosterilir."""
    import traceback as _tb
    import datetime as _dt
    try:
        kok = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, 'frozen', False):
            kok = os.path.dirname(sys.executable)
        yol = os.path.join(kok, 'crash.log')
        with open(yol, 'a', encoding='utf-8') as f:
            f.write('\n===== ' + _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' =====\n')
            _tb.print_exception(exc_tipi, deger, tb, file=f)
    except Exception:
        pass
    try:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, 'MSY Rip — beklenmeyen hata',
            str(deger) + '\n\nAyrinti crash.log dosyasina yazildi.')
    except Exception:
        pass


def main():
    sys.excepthook = _hata_gunlugu
    app = QApplication(sys.argv)
    app.setApplicationName("MSY Rip")
    import json as _json
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'version.json')) as _f:
            app.setApplicationVersion(_json.load(_f).get('version', '0.0.0'))
    except Exception:
        app.setApplicationVersion("0.0.0")
    w = AnaEkran()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
