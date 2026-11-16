"""MSY Rip — Ayarlar penceresi (⚙).

MSY isteği:
  - CMYK + White için her renk yüzdesi
  - Kanal sıralamasını değiştir
  - Import ile renk profili yükle
  - Spot ismi yaz
  - Ripli dosyaların kaydedileceği klasörü seç
  - Kaydet → tekrar değişene kadar kalıcı
"""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

from core.icc import profil_bilgi
from core.machines import MAKINELER, uygula
from core.settings import Ayarlar

KANAL_SECENEK = ['C', 'M', 'Y', 'K', 'White', 'Spot_1', 'Spot_2', 'Spot_3', 'Spot_4']


class AyarlarPenceresi(QDialog):
    def __init__(self, ayar: Ayarlar, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MSY Rip — Ayarlar")
        self.resize(620, 700)
        self.ayar = Ayarlar(**{})  # kopya
        # kopyala
        for k, v in vars(ayar).items():
            setattr(self.ayar, k, v if not isinstance(v, (list, dict)) else type(v)(v))
        self._kur()

    # ------------------------------------------------------------------
    def _kur(self):
        v = QVBoxLayout(self)

        # 0) Makine seçimi (PM19 'Printer Setup' benzeri)
        g0 = QGroupBox("Makine profili")
        h0 = QHBoxLayout(g0)
        self.makine_combo = QComboBox()
        self.makine_combo.addItems(list(MAKINELER.keys()))
        _cur = self.ayar.makine or "JLHS600EPS3200 (DTF 6PASS)"
        if _cur in MAKINELER:
            self.makine_combo.setCurrentText(_cur)
        h0.addWidget(self.makine_combo, 1)
        self.makine_lbl = QLabel("")
        self.makine_lbl.setStyleSheet("color:#666; font-size:11px;")
        h0.addWidget(self.makine_lbl)
        b_makine = QPushButton("Uygula")
        b_makine.setStyleSheet("background:#2563eb;color:white;padding:6px 16px;border-radius:5px;")
        b_makine.clicked.connect(self._makine_uygula)
        h0.addWidget(b_makine)
        self.makine_combo.currentTextChanged.connect(self._makine_bilgi)
        # makine secimi degisir degimez tum ayarlar otomatik guncellenir
        self.makine_combo.currentIndexChanged.connect(self._makine_uygula)
        v.addWidget(g0)
        self._makine_bilgi(self.makine_combo.currentText())

        # 1) Kanal sıralaması
        g1 = QGroupBox("1) Kanal sıralaması")
        h1 = QHBoxLayout(g1)
        self.kanal_liste = QListWidget()
        self.kanal_liste.addItems(self.ayar.kanal_sirasi)
        h1.addWidget(self.kanal_liste, 1)

        kv = QVBoxLayout()
        self.kanal_combo = QComboBox()
        self.kanal_combo.addItems(KANAL_SECENEK)
        kv.addWidget(self.kanal_combo)

        b_degistir = QPushButton("Seçileni değiştir")
        b_degistir.clicked.connect(self._kanal_degistir)
        kv.addWidget(b_degistir)

        b_yukari = QPushButton("▲ Yukarı")
        b_yukari.clicked.connect(lambda: self._kanal_tasi(-1))
        kv.addWidget(b_yukari)

        b_asagi = QPushButton("▼ Aşağı")
        b_asagi.clicked.connect(lambda: self._kanal_tasi(1))
        kv.addWidget(b_asagi)
        kv.addStretch(1)
        h1.addLayout(kv)
        v.addWidget(g1)

        # 2) Renk yüzdeleri
        g2 = QGroupBox("2) Renk yüzdeleri (%)")
        f2 = QFormLayout(g2)
        self.yuzde = {}
        for ad in ('C', 'M', 'Y', 'K', 'White'):
            sb = QDoubleSpinBox()
            sb.setRange(0, 100)
            sb.setDecimals(0)
            sb.setSuffix(" %")
            sb.setValue(float(self.ayar.renk_yuzde.get(ad, 100)))
            self.yuzde[ad] = sb
            f2.addRow(ad, sb)
        v.addWidget(g2)

        # 3) ICC profili
        g3 = QGroupBox("3) Renk profili (ICC)")
        h3 = QHBoxLayout(g3)
        self.icc_edit = QLineEdit(self.ayar.icc_yol)
        self.icc_edit.setReadOnly(True)
        h3.addWidget(self.icc_edit, 1)
        b_icc = QPushButton("Import…")
        b_icc.clicked.connect(self._icc_sec)
        h3.addWidget(b_icc)
        v.addWidget(g3)

        # 4) Spot ismi + pass
        g4 = QGroupBox("4) Spot ve pass")
        f4 = QFormLayout(g4)
        self.spot_edit = QLineEdit(self.ayar.spot_adi)
        f4.addRow("Spot adı (beyaz katman)", self.spot_edit)
        self.pass_spin = QSpinBox()
        self.pass_spin.setRange(1, 16)
        self.pass_spin.setValue(int(self.ayar.pass_sayisi))
        f4.addRow("Pass sayısı", self.pass_spin)
        self.hucre_spin = QSpinBox()
        self.hucre_spin.setRange(2, 32)
        self.hucre_spin.setValue(int(self.ayar.halftone_hucre))
        f4.addRow("Halftone hücresi (px)", self.hucre_spin)
        from PyQt6.QtWidgets import QComboBox as _QCB
        self.htur_combo = _QCB()
        self.htur_combo.addItems(['sofm', 'am'])
        self.htur_combo.setCurrentText(getattr(self.ayar, 'halftone_tur', 'sofm') or 'sofm')
        f4.addRow("Halftone türü", self.htur_combo)
        v.addWidget(g4)

        # 5) Çıkış klasörü
        g5 = QGroupBox("5) Çıkış klasörü")
        h5 = QHBoxLayout(g5)
        self.cikis_edit = QLineEdit(self.ayar.cikis_klasoru)
        self.cikis_edit.setReadOnly(True)
        h5.addWidget(self.cikis_edit, 1)
        b_cikis = QPushButton("Gözat…")
        b_cikis.clicked.connect(self._cikis_sec)
        h5.addWidget(b_cikis)
        v.addWidget(g5)

        # 6) Kaydet / İptal
        bb = QDialogButtonBox()
        b_kaydet = bb.addButton("Kaydet", QDialogButtonBox.ButtonRole.AcceptRole)
        b_kaydet.setStyleSheet("background:#2563eb;color:white;padding:6px 18px;border-radius:5px;")
        b_iptal = bb.addButton("İptal", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self._kaydet)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    # ------------------------------------------------------------------
    def _makine_bilgi(self, ad):
        m = MAKINELER.get(ad)
        if m:
            self.makine_lbl.setText(
                f"{m['aciklama']} — {m['pass_sayisi']} pass, bant {m['prt_bant_px']}px")

    def _makine_uygula(self):
        ad = self.makine_combo.currentText()
        if uygula(self.ayar, ad):
            # UI alanlarini da guncelle
            self.kanal_liste.clear()
            self.kanal_liste.addItems(self.ayar.kanal_sirasi)
            for k, sb in self.yuzde.items():
                sb.setValue(float(self.ayar.renk_yuzde.get(k, 100)))
            self.spot_edit.setText(self.ayar.spot_adi)
            self.pass_spin.setValue(int(self.ayar.pass_sayisi))
            self.hucre_spin.setValue(int(self.ayar.halftone_hucre))

    def _kanal_degistir(self):
        i = self.kanal_liste.currentRow()
        if i < 0:
            return
        self.kanal_liste.item(i).setText(self.kanal_combo.currentText())

    def _kanal_tasi(self, yon):
        i = self.kanal_liste.currentRow()
        j = i + yon
        if i < 0 or j < 0 or j >= self.kanal_liste.count():
            return
        item = self.kanal_liste.takeItem(i)
        self.kanal_liste.insertItem(j, item)
        self.kanal_liste.setCurrentRow(j)

    def _icc_sec(self):
        yol, _ = QFileDialog.getOpenFileName(
            self, "ICC profili seç", "", "ICC (*.icc *.icm)")
        if not yol:
            return
        b = profil_bilgi(yol)
        if not b.get('ok'):
            QMessageBox.warning(self, "Geçersiz profil", b.get('hata', 'okunamadı'))
            return
        if b.get('renk_uzayi') != 'CMYK':
            QMessageBox.warning(
                self, "Uyumsuz profil",
                f"Bu profil {b.get('renk_uzayi')} — CMYK yazıcı profili gerekli.")
            return
        # Profili kurulum klasorundeki profiles/ altina kopyala:
        # masaustundeki orijinal silinse bile program kullanmaya devam eder.
        import shutil
        from core.settings import profil_klasoru
        hedef = os.path.join(profil_klasoru(), os.path.basename(yol))
        try:
            if os.path.abspath(yol) != os.path.abspath(hedef):
                shutil.copy2(yol, hedef)
            self.icc_edit.setText(os.path.basename(yol))
            QMessageBox.information(
                self, "Profil kaydedildi",
                f"Profil program klasörüne kopyalandı:\n{hedef}\n\n"
                "Orijinal dosyayı silebilirsin — rip yine çalışır.")
        except Exception as e:
            self.icc_edit.setText(yol)

    def _cikis_sec(self):
        d = QFileDialog.getExistingDirectory(self, "Çıkış klasörü seç")
        if d:
            self.cikis_edit.setText(d)

    def _kaydet(self):
        self.ayar.makine = self.makine_combo.currentText()
        kanallar = [self.kanal_liste.item(i).text()
                    for i in range(self.kanal_liste.count())]
        if not kanallar:
            QMessageBox.warning(self, "Hata", "Kanal listesi boş olamaz.")
            return
        self.ayar.kanal_sirasi = kanallar
        self.ayar.renk_yuzde = {k: sb.value() for k, sb in self.yuzde.items()}
        self.ayar.icc_yol = self.icc_edit.text().strip()
        self.ayar.spot_adi = self.spot_edit.text().strip() or 'Spot_1'
        self.ayar.pass_sayisi = int(self.pass_spin.value())
        self.ayar.halftone_hucre = int(self.hucre_spin.value())
        self.ayar.halftone_tur = self.htur_combo.currentText()
        self.ayar.cikis_klasoru = self.cikis_edit.text().strip()

        hatalar = self.ayar.dogrula()
        if hatalar:
            QMessageBox.warning(self, "Ayarlar hatalı",
                                "\n".join(f"• {h}" for h in hatalar))
            return
        self.accept()
