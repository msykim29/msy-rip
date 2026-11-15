"""MSY Rip — giriş noktası."""
from __future__ import annotations

import sys
import os

# paket yolu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import AnaEkran  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MSY Rip")
    app.setApplicationVersion("1.0.0")
    w = AnaEkran()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
