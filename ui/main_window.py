"""MSY Rip — ana ekran (MSY çizimine birebir).

Tasarım (15/11/2026):
  ┌────────────────────────────────────────────┐
  │        0    1    2            ⚙ ayarlar    │
  ├──────────┬──────────────┬──────────────────┤
  │ a. tif   │  □   □   □   │  50x20 cm        │
  │ b. tif   │  □   □   □   │  55x32 cm        │
  │          │              │   [ spot + rip ] │
  └──────────┴──────────────┴──────────────────┘
"""
from __future__ import annotations

import os
import threading

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView, QButtonGroup, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton, QRadioButton,
    QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout, QWidget,
)

from core.pipeline import rip_isle
from core.settings import Ayarlar
from core.tif import bilgi_oku
from ui.settings_dialog import AyarlarPenceresi
import updater


class RipThread(QThread):
    """RIP işlemini arka planda çalıştır (arayüz donmasın)."""
    ilerleme = pyqtSignal(int, int, str)   # (tamam, toplam, mesaj)
    log = pyqtSignal(str)
    bitti = pyqtSignal(list)               # [(tif, prt|None, hata), ...]

    def __init__(self, isler, ayar):
        super().__init__()
        self.isler = isler        # [(tif_yolu, daraltma), ...]
        self.ayar = ayar

    def run(self):
        sonuc = []
        toplam = len(self.isler)
        for i, (tif, daraltma) in enumerate(self.isler, 1):
            ad = os.path.basename(tif)
            self.ilerleme.emit(i - 1, toplam, f"{ad} işleniyor…")
            try:
                prt = rip_isle(tif, daraltma, self.ayar, log=self.log.emit)
                sonuc.append((tif, prt, None))
                self.log.emit(f"✔ {ad} → {os.path.basename(prt)}")
            except Exception as e:
                sonuc.append((tif, None, str(e)))
                self.log.emit(f"✖ {ad}: {e}")
            self.ilerleme.emit(i, toplam, f"{ad} bitti")
        self.bitti.emit(sonuc)


class IndirmeThread(QThread):
    """24/11 MSY: guncelleme indirmesini ARKA PLANDA yapar.

    Eski kod `updater.indir_ve_kur()` fonksiyonunu dogrudan cagiriyordu ->
    ana (arayuz) is parcaciginda 111 MB indirme boyunca pencere DONUYORDU ve
    ilerleme gorunmuyordu. Artik thread + yuzde sinyali.
    """
    ilerleme = pyqtSignal(int, float, float)   # (yuzde, inen_mb, toplam_mb)
    bitti = pyqtSignal(bool, str)

    def __init__(self, url, ebeveyn=None):
        super().__init__(ebeveyn)
        self.url = url
        self._iptal = False

    def iptal(self):
        self._iptal = True

    def run(self):
        def _cb(inen, toplam):
            if self._iptal:
                return
            mb_in = inen / (1024 * 1024)
            mb_top = (toplam or 0) / (1024 * 1024)
            yuzde = int(100 * inen / toplam) if toplam else 0
            self.ilerleme.emit(yuzde, mb_in, mb_top)

        try:
            ok = updater.indir_ve_kur(self.url, ilerleme=_cb)
            self.bitti.emit(bool(ok), '')
        except Exception as e:
            self.bitti.emit(False, str(e)[:200])


class AnaEkran(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSY Rip")
        self.resize(980, 620)
        self.ayar = Ayarlar.yukle()
        self.setAcceptDrops(True)
        self._satirlar = []   # [(dosya_yolu, TifBilgi|None)]

        self._kur_toolbar()
        self._kur_govde()
        self._durum(f"Ayarlar yüklendi — çıkış: {self.ayar.cikis_klasoru or '(seçilmedi)'}")
        # 15/11: açılışta GitHub güncelleme kontrolü (arka planda, arayüzü bekletmez)
        QTimer.singleShot(1200, self._guncelleme_kontrol)

    # ---------------- arayüz kurulumu ----------------
    def _kur_toolbar(self):
        tb = QToolBar("Ana")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_ekle = QAction("＋ Dosya Ekle", self)
        act_ekle.triggered.connect(self.dosya_sec)
        tb.addAction(act_ekle)

        act_temizle = QAction("✕ Listeyi Temizle", self)
        act_temizle.triggered.connect(self.listeyi_temizle)
        tb.addAction(act_temizle)

        bosluk = QWidget()
        bosluk.setSizePolicy(bosluk.sizePolicy().horizontalPolicy().Expanding,
                             bosluk.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(bosluk)

        act_ayar = QAction("⚙ Ayarlar", self)
        act_ayar.triggered.connect(self.ayarlari_ac)
        tb.addAction(act_ayar)

    def _kur_govde(self):
        merkez = QWidget()
        self.setCentralWidget(merkez)
        v = QVBoxLayout(merkez)

        # --- TEK TABLO (MSY çizimi): [ ] [Dosya] [0] [1] [2] [Boyut] ---
        self.tablo = QTableWidget(0, 6)
        self.tablo.setHorizontalHeaderLabels(["", "Dosya", "0", "1", "2", "Boyut"])
        self.tablo.setColumnWidth(0, 32)
        self.tablo.setColumnWidth(1, 300)
        self.tablo.setColumnWidth(2, 70)
        self.tablo.setColumnWidth(3, 70)
        self.tablo.setColumnWidth(4, 70)
        self.tablo.setColumnWidth(5, 200)
        hdr = self.tablo.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.verticalHeader().setDefaultSectionSize(56)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setStyleSheet(
            "QTableWidget{font-size:15px;gridline-color:#d1d5db;}"
            "QHeaderView::section{font-size:15px;font-weight:bold;padding:6px;"
            "background:#f3f4f6;border:1px solid #d1d5db;}")
        v.addWidget(self.tablo, 1)

        # --- alt kısım: ilerleme + spot+rip ---
        alt = QHBoxLayout()

        self.ilerleme = QProgressBar()
        self.ilerleme.setValue(0)
        alt.addWidget(self.ilerleme, 1)

        self.durum_lbl = QLabel("Hazır")
        self.durum_lbl.setStyleSheet("color:#666;")
        alt.addWidget(self.durum_lbl)

        self.btn_rip = QPushButton("spot + rip")
        self.btn_rip.setMinimumHeight(46)
        self.btn_rip.setMinimumWidth(150)
        self.btn_rip.setStyleSheet(
            "QPushButton{font-size:15px;font-weight:bold;background:#2563eb;"
            "color:white;border-radius:6px;padding:8px 18px;}"
            "QPushButton:hover{background:#1d4ed8;}"
            "QPushButton:disabled{background:#9ca3af;}")
        self.btn_rip.clicked.connect(self.rip_baslat)
        alt.addWidget(self.btn_rip)

        v.addLayout(alt)

        # --- ipucu ---
        ipucu = QLabel("TIF dosyalarını bu pencereye sürükleyip bırakabilirsin.")
        ipucu.setStyleSheet("color:#888; font-size:11px;")
        v.addWidget(ipucu)

        # --- alt bilgi: sürüm + web sitesi (21/11 MSY) ---
        altbilgi = QHBoxLayout()
        altbilgi.setContentsMargins(0, 2, 0, 2)
        _sv = ""
        # 21/11 MSY: surum HER ZAMAN "1.0.x" formatinda gorunmeli.
        # Paketlenmis exe'te version.json sys._MEIPASS altinda,
        # exe'nin yaninda veya kaynak kokunde olabilir.
        try:
            import json as _j, os as _o, sys as _s
            _adaylar = []
            if getattr(_s, 'frozen', False):
                _adb = _o.path.dirname(_s.executable)
                _adaylar.append(_o.path.join(_adb, 'version.json'))
                _meip = getattr(_s, '_MEIPASS', None)
                if _meip:
                    _adaylar.append(_o.path.join(_meip, 'version.json'))
            _kok = _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))
            _adaylar.append(_o.path.join(_kok, 'version.json'))
            for _vp in _adaylar:
                if _o.path.exists(_vp):
                    with open(_vp, encoding='utf-8') as _f:
                        _sv = str(_j.load(_f).get('version') or '').strip()
                    if _sv:
                        break
        except Exception:
            _sv = ""
        if not _sv:
            # son care: exe dosya surumunden oku
            try:
                import sys as _s2
                if getattr(_s2, 'frozen', False):
                    _sv = str(QApplication.applicationVersion() or '').strip()
                    if _sv in ('', '1.0.0'):
                        _sv = ""
            except Exception:
                pass
        if not _sv:
            _sv = "1.0.0"
        # "v1.0.41" bicimi (basinda v varsa temizle)
        _sv = _sv.lstrip('vV')
        self.surum_lbl = QLabel(f"v{_sv}")
        self.surum_lbl.setStyleSheet("color:#9ca3af; font-size:11px;")
        altbilgi.addWidget(self.surum_lbl)
        altbilgi.addStretch(1)
        self.site_lbl = QLabel('<a href="https://www.msy.kim" style="color:#2563eb;'
                               'text-decoration:none;font-size:11px;">www.msy.kim</a>')
        self.site_lbl.setOpenExternalLinks(True)
        self.site_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        altbilgi.addWidget(self.site_lbl)
        v.addLayout(altbilgi)

    # ---------------- sürükle-bırak ----------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = []
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p and os.path.isfile(p) and p.lower().endswith(('.tif', '.tiff')):
                yollar.append(p)
        if yollar:
            self._dosya_ekle(yollar)

    def dosya_sec(self):
        yollar, _ = QFileDialog.getOpenFileNames(
            self, "TIF dosyaları seç", "", "TIFF (*.tif *.tiff)")
        if yollar:
            self._dosya_ekle(yollar)

    def _dosya_ekle(self, yollar):
        for yol in yollar:
            if any(yol == s[0] for s in self._satirlar):
                continue
            try:
                bilgi = bilgi_oku(yol)
            except Exception as e:
                QMessageBox.warning(self, "TIF okunamadi",
                    f"Dosya: {os.path.basename(yol)}\n\n{e}")
                continue
            self._satirlar.append((yol, bilgi))
            self._satir_ciz(len(self._satirlar) - 1, yol, bilgi)
        self._durum(f"{len(self._satirlar)} dosya")

    def _satir_ciz(self, idx, yol, bilgi):
        satir = self.tablo.rowCount()
        self.tablo.insertRow(satir)

        ad = QTableWidgetItem(os.path.basename(yol))
        ad.setToolTip(yol)
        self.tablo.setItem(satir, 1, ad)

        grup = QButtonGroup(self.tablo)
        varsayilan = 1   # MSY: varsayılan 1 px daraltma
        for i, n in enumerate((0, 1, 2)):
            rb = QRadioButton()
            rb.setStyleSheet("margin-left:22px;")
            rb.setChecked(n == varsayilan)
            grup.addButton(rb, n)
            self.tablo.setCellWidget(satir, 2 + i, rb)

        # Boyut — tablonun son sütunu (MSY çizimi)
        bt = QTableWidgetItem(bilgi.boyut_metin if bilgi else "—")
        bt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        bt.setToolTip(f"{bilgi.piksel_genislik}x{bilgi.piksel_yukseklik} px "
                      f"@ {bilgi.dpi[0]:.0f} dpi" if bilgi else "")
        self.tablo.setItem(satir, 5, bt)

    def listeyi_temizle(self):
        self.tablo.setRowCount(0)
        self._satirlar.clear()
        self.ilerleme.setValue(0)
        self._durum("Liste temizlendi")

    # ---------------- ayarlar ----------------
    def ayarlari_ac(self):
        d = AyarlarPenceresi(self.ayar, self)
        if d.exec():
            self.ayar = d.ayar
            yol = self.ayar.kaydet()
            self._durum(f"Ayarlar kaydedildi → {yol}")

    # ---------------- rip ----------------
    def _daraltma(self, satir) -> int:
        for i, n in enumerate((0, 1, 2)):
            w = self.tablo.cellWidget(satir, 2 + i)
            if isinstance(w, QRadioButton) and w.isChecked():
                return n
        return 1

    def rip_baslat(self):
        if not self._satirlar:
            QMessageBox.information(self, "MSY Rip", "Önce TIF dosyası ekle.")
            return
        if not self.ayar.cikis_klasoru:
            QMessageBox.information(
                self, "MSY Rip",
                "Çıkış klasörü seçilmemiş.\n\nAyarlar (⚙) → Çıkış klasörü seç.")
            self.ayarlari_ac()
            return
        hatalar = self.ayar.dogrula()
        if hatalar:
            QMessageBox.warning(self, "Ayarlar hatalı", "\n".join(f"• {h}" for h in hatalar))
            self.ayarlari_ac()
            return

        isler = [(yol, self._daraltma(i)) for i, (yol, _b) in enumerate(self._satirlar)]
        self.btn_rip.setEnabled(False)
        self.ilerleme.setMaximum(len(isler))
        self.ilerleme.setValue(0)

        self._thread = RipThread(isler, self.ayar)
        self._thread.ilerleme.connect(self._ilerleme_guncelle)
        self._thread.log.connect(self._durum)
        self._thread.bitti.connect(self._rip_bitti)
        self._thread.start()

    def _ilerleme_guncelle(self, tamam, toplam, mesaj):
        self.ilerleme.setMaximum(toplam)
        self.ilerleme.setValue(tamam)
        self._durum(mesaj)

    def _rip_bitti(self, sonuc):
        self.btn_rip.setEnabled(True)
        basarili = [s for s in sonuc if s[1]]
        hatali = [s for s in sonuc if s[2]]
        msg = f"{len(basarili)}/{len(sonuc)} dosya rip'lendi\n\nÇıkış: {self.ayar.cikis_klasoru}"
        if hatali:
            msg += "\n\nHatalar:\n" + "\n".join(
                f"• {os.path.basename(h[0])}: {h[2]}" for h in hatali[:5])
        QMessageBox.information(self, "MSY Rip — tamamlandı", msg)
        self._durum("Tamamlandı")

    # ---------------- güncelleme ----------------
    def _guncelleme_kontrol(self):
        """Arka planda GitHub'dan sürüm kontrolü."""
        try:
            bilgi = updater.guncelleme_kontrol()
        except Exception:
            return
        if not bilgi:
            return
        cevap = QMessageBox.question(
            self, "MSY Rip — Güncelleme",
            f"Yeni sürüm mevcut: v{bilgi.get('version')}\n\n"
            f"{bilgi.get('notes', '')}\n\n"
            "Şimdi indirilip kurulsun mu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if cevap != QMessageBox.StandardButton.Yes:
            return
        # 24/11 MSY: indirme ARKA PLANDA + ilerleme cubugu (pencere donmaz)
        from PyQt6.QtWidgets import QProgressDialog
        self._dl_pencere = QProgressDialog(
            "Güncelleme indiriliyor…", "İptal", 0, 100, self)
        self._dl_pencere.setWindowTitle("MSY Rip — Güncelleme")
        self._dl_pencere.setWindowModality(Qt.WindowModality.WindowModal)
        self._dl_pencere.setMinimumDuration(0)
        self._dl_pencere.setValue(0)
        self._dl_pencere.setAutoClose(False)
        self._dl_pencere.setAutoReset(False)

        self._dl_thread = IndirmeThread(bilgi.get('url', ''), self)

        def _ilerleme(yuzde, inen, toplam):
            self._dl_pencere.setValue(max(0, min(100, yuzde)))
            if toplam > 0:
                self._dl_pencere.setLabelText(
                    f"İndiriliyor… %{yuzde}  ({inen:.1f} / {toplam:.1f} MB)")
            else:
                self._dl_pencere.setLabelText(f"İndiriliyor… {inen:.1f} MB")
            self._durum(f"Güncelleme indiriliyor: %{yuzde}")

        def _bitti(ok, hata):
            try:
                self._dl_pencere.setValue(100)
                self._dl_pencere.close()
            except Exception:
                pass
            if ok:
                QMessageBox.information(
                    self, "MSY Rip",
                    "Güncelleme indirildi ve başlatıldı.\n"
                    "Kurulum bitince programı yeniden aç.")
                self.close()
            elif hata:
                QMessageBox.warning(self, "MSY Rip",
                                    "Güncelleme hatası:\n" + hata)
            else:
                QMessageBox.warning(self, "MSY Rip",
                                    "Güncelleme indirilemedi. "
                                    "Daha sonra tekrar deneyin.")

        self._dl_thread.ilerleme.connect(_ilerleme)
        self._dl_thread.bitti.connect(_bitti)
        self._dl_pencere.canceled.connect(self._dl_thread.iptal)
        self._dl_thread.start()

    def _durum(self, metin):
        self.durum_lbl.setText(str(metin)[:90])
