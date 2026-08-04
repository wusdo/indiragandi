#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
İNDİRAGANDİ — DaVinci Resolve eklentisi
Workspace > Scripts > Indiragandi

Linki indirir, biter bitmez Media Pool'a atar.
Motor: http://127.0.0.1:8767  (~/bin/indiragandi/server.py)
"""

import json
import os
import subprocess
import threading
import time
import urllib.request
import urllib.error

API = "http://127.0.0.1:8767"
HOME = os.path.expanduser("~")
SUNUCU = os.path.join(HOME, "bin", "indiragandi", "server.py")

KALITELER = [
    ("1080", "1080p  ·  FULL HD"),
    ("720",  "720p   ·  HAFIF"),
    ("1440", "1440p  ·  2K"),
    ("2160", "4K     ·  2160p"),
    ("best", "MAX    ·  EN IYISI"),
    ("mp3",  "MP3    ·  SADECE SES"),
]
CEREZLER = [("yok", "YOK"), ("safari", "SAFARI"), ("chrome", "CHROME"), ("firefox", "FIREFOX")]

# ---------------------------------------------------------------- Resolve
try:
    resolve
except NameError:
    try:
        import DaVinciResolveScript as dvr_script
        resolve = dvr_script.scriptapp("Resolve")
    except Exception:
        resolve = None

try:
    bmd
except NameError:
    import BlackmagicFusion as bmd

fusion = bmd.scriptapp("Fusion")
ui = fusion.UIManager
disp = bmd.UIDispatcher(ui)


# ---------------------------------------------------------------- HTTP
def istek(yol, veri=None, zaman=60):
    adres = API + yol
    if veri is None:
        r = urllib.request.urlopen(adres, timeout=zaman)
    else:
        govde = json.dumps(veri).encode("utf-8")
        req = urllib.request.Request(adres, data=govde,
                                     headers={"Content-Type": "application/json"})
        r = urllib.request.urlopen(req, timeout=zaman)
    return json.loads(r.read().decode("utf-8"))


def motor_ayakta():
    try:
        istek("/api/gecmis", zaman=2)
        return True
    except Exception:
        return False


def motoru_baslat():
    """Sunucu kapalıysa arka planda başlat."""
    if motor_ayakta():
        return True
    if not os.path.exists(SUNUCU):
        return False
    try:
        subprocess.Popen(["/usr/bin/python3", SUNUCU],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False
    for _ in range(20):
        time.sleep(0.4)
        if motor_ayakta():
            return True
    return False


# ---------------------------------------------------------------- arayüz
STIL = """
QWidget    { background-color: #0d0a18; color: #e9e6ff;
             font-family: Monaco, Courier New, monospace; font-size: 12px; }
QLabel#Baslik   { color: #ffe700; font-size: 20px; font-weight: bold; }
QLabel#AltBaslik{ color: #4deeea; font-size: 10px; }
QLabel#Etiket   { color: #8b82c4; font-size: 10px; }
QLabel#Durum    { color: #4deeea; font-size: 12px; }
QLabel#Bar      { color: #74ee15; font-size: 15px; }
QLabel#Bilgi    { color: #e9e6ff; font-size: 11px; }
QLabel#Hata     { color: #ff4757; font-size: 10px; }
QLineEdit  { background-color: #151027; color: #74ee15; border: 3px solid #3a2f6b;
             padding: 7px; font-size: 12px; }
QComboBox  { background-color: #151027; color: #e9e6ff; border: 3px solid #3a2f6b;
             padding: 6px; font-size: 11px; }
QComboBox QAbstractItemView { background-color: #151027; color: #e9e6ff;
             selection-background-color: #ff3d81; }
QCheckBox  { color: #8b82c4; font-size: 11px; }
QCheckBox:checked { color: #4deeea; }
QPushButton{ background-color: #282050; color: #e9e6ff; border: 3px solid #5a4a9e;
             padding: 9px; font-size: 11px; }
QPushButton:hover   { background-color: #3a2f6b; color: #ffe700; }
QPushButton:pressed { background-color: #5a4a9e; }
QPushButton#Indir   { background-color: #74ee15; color: #0d0a18;
                      border: 3px solid #ffe700; font-size: 15px; font-weight: bold;
                      padding: 13px; }
QPushButton#Indir:hover { background-color: #ffe700; }
"""

pencere = disp.AddWindow({
    "ID": "IgWin",
    "WindowTitle": "İNDİRAGANDİ",
    "Geometry": [300, 200, 480, 500],
    "Spacing": 9,
    "Margin": 16,
    "StyleSheet": STIL,
}, [
    ui.VGroup([
        ui.Label({"ID": "Baslik", "Text": "▼ İNDİRAGANDİ ▼",
                  "Alignment": {"AlignHCenter": True}, "Weight": 0}),
        ui.Label({"ID": "AltBaslik", "Text": "VIDEO INDIRME MAKINESI  ·  RESOLVE",
                  "Alignment": {"AlignHCenter": True}, "Weight": 0}),

        ui.VGap(8),

        ui.Label({"ID": "Etiket", "Text": "[1]  LINK", "Weight": 0}),
        ui.HGroup({"Weight": 0, "Spacing": 6}, [
            ui.LineEdit({"ID": "Url", "PlaceholderText": "https://youtube.com/...", "Weight": 1}),
            ui.Button({"ID": "PanoBtn", "Text": "PANO", "Weight": 0}),
        ]),
        ui.Label({"ID": "Bilgi", "Text": "", "WordWrap": True, "Weight": 0}),

        ui.VGap(6),

        ui.Label({"ID": "Etiket2", "Text": "[2]  KALITE", "Weight": 0}),
        ui.ComboBox({"ID": "Kalite", "Weight": 0}),

        ui.VGap(4),
        ui.CheckBox({"ID": "Kes", "Text": "Aralık kes — sadece istediğin bölümü indir",
                     "Checked": False, "Weight": 0}),
        ui.HGroup({"Weight": 0, "Spacing": 6}, [
            ui.LineEdit({"ID": "Bas", "PlaceholderText": "0:00", "Enabled": False}),
            ui.Label({"ID": "Ok", "Text": "→", "Weight": 0}),
            ui.LineEdit({"ID": "Bit", "PlaceholderText": "son", "Enabled": False}),
            ui.CheckBox({"ID": "TamKare", "Text": "tam kare", "Checked": False,
                         "Enabled": False, "Weight": 0}),
        ]),

        ui.VGap(4),
        ui.CheckBox({"ID": "MediaPool", "Text": "Media Pool'a otomatik ekle",
                     "Checked": True, "Weight": 0}),
        ui.CheckBox({"ID": "Timeline", "Text": "Aktif timeline'a da ekle",
                     "Checked": False, "Weight": 0}),
        ui.HGroup({"Weight": 0, "Spacing": 6}, [
            ui.Label({"ID": "Etiket3", "Text": "CEREZ", "Weight": 0}),
            ui.ComboBox({"ID": "Cerez", "Weight": 1}),
        ]),

        ui.VGap(8),
        ui.Button({"ID": "Indir", "Text": "▼  INDIR  ▼", "Weight": 0}),
        ui.VGap(8),

        ui.Label({"ID": "Etiket4", "Text": "[3]  DURUM", "Weight": 0}),
        ui.Label({"ID": "Bar", "Text": "░" * 24 + "   0%", "Weight": 0}),
        ui.Label({"ID": "Durum", "Text": "Hazır", "Weight": 0}),
        ui.Label({"ID": "Hata", "Text": "", "WordWrap": True, "Weight": 0}),

        ui.VGap(0, 1),
        ui.HGroup({"Weight": 0, "Spacing": 6}, [
            ui.Button({"ID": "KlasorBtn", "Text": "KLASOR"}),
            ui.Button({"ID": "GuncelleBtn", "Text": "MOTORU GUNCELLE"}),
            ui.Button({"ID": "KapatBtn", "Text": "KAPAT"}),
        ]),
    ]),
])

it = pencere.GetItems()

for _kod, _ad in KALITELER:
    it["Kalite"].AddItem(_ad)
for _kod, _ad in CEREZLER:
    it["Cerez"].AddItem(_ad)


# ---------------------------------------------------------------- yardımcı
def bar_ciz(yuzde):
    dolu = int(round(yuzde / 100.0 * 24))
    it["Bar"].Text = "█" * dolu + "░" * (24 - dolu) + "   %d%%" % int(yuzde)


def durum(metin):
    it["Durum"].Text = metin


def hata_yaz(metin):
    it["Hata"].Text = metin or ""


def medya_havuzuna_ekle(yol, timeline_de):
    """İndirilen dosyayı Media Pool'a, istenirse timeline'a ekler."""
    if resolve is None:
        return "Resolve API yok"
    try:
        pm = resolve.GetProjectManager()
        proje = pm.GetCurrentProject()
        if not proje:
            return "Acik proje yok"
        depo = resolve.GetMediaStorage()
        klipler = depo.AddItemListToMediaPool([yol])
        if not klipler:
            return "Media Pool'a eklenemedi"
        if timeline_de:
            havuz = proje.GetMediaPool()
            tl = proje.GetCurrentTimeline()
            if not tl:
                return "Media Pool'a eklendi (acik timeline yok)"
            havuz.AppendToTimeline(klipler)
            return "Timeline'a eklendi"
        return "Media Pool'a eklendi"
    except Exception as e:
        return "Aktarim hatasi: %s" % e


# ---------------------------------------------------------------- olaylar
calisiyor = [False]


def pano_tikla(ev):
    try:
        metin = subprocess.run(["pbpaste"], capture_output=True,
                               text=True, timeout=5).stdout.strip()
    except Exception:
        metin = ""
    if metin.startswith("http"):
        it["Url"].Text = metin
        threading.Thread(target=bilgi_al, args=(metin,), daemon=True).start()


def bilgi_al(link):
    it["Bilgi"].Text = "Bilgi alınıyor..."
    try:
        d = istek("/api/bilgi", {"url": link,
                                 "cerez": CEREZLER[it["Cerez"].CurrentIndex][0]}, zaman=50)
        if d.get("hata"):
            it["Bilgi"].Text = "Bilgi alınamadı (yine de deneyebilirsin)"
            return
        sure = d.get("sure") or 0
        dk = "%d:%02d" % (sure // 60, sure % 60) if sure else ""
        parcalar = [p for p in [d.get("site"), d.get("kanal"), dk] if p]
        it["Bilgi"].Text = "%s\n%s" % (d.get("baslik", ""), "  ·  ".join(parcalar))
    except Exception:
        it["Bilgi"].Text = "Motor kapalı"


def indir_isi(link, format_kodu, cerez, mp_ekle, tl_ekle,
              bas=None, bit=None, tam_kare=False):
    try:
        if not motoru_baslat():
            durum("✗ Motor başlatılamadı")
            hata_yaz("~/bin/indiragandi/server.py çalışmıyor. "
                     "Dock'taki İndiragandi uygulamasını bir kez aç.")
            return

        govde = {"url": link, "format": format_kodu, "cerez": cerez}
        if bas is not None or bit is not None:
            govde["bas"] = "" if bas is None else str(bas)
            govde["bit"] = "" if bit is None else str(bit)
            govde["tam_kare"] = bool(tam_kare)
        d = istek("/api/indir", govde)
        iid = d.get("id")
        if not iid:
            durum("✗ Başlatılamadı")
            return

        while True:
            time.sleep(0.5)
            s = istek("/api/durum?id=" + iid, zaman=10)
            bar_ciz(s.get("yuzde") or 0)
            asama = s.get("asama") or ""
            hiz = s.get("hiz") or ""
            durum("%s   %s" % (asama, hiz))

            if s.get("durum") == "bitti":
                bar_ciz(100)
                yol = s.get("yol") or ""
                if mp_ekle and yol:
                    durum("Media Pool'a aktarılıyor...")
                    sonuc = medya_havuzuna_ekle(yol, tl_ekle)
                    durum("✓ %s" % sonuc)
                else:
                    durum("✓ İndi: %s" % (s.get("dosya") or ""))
                break

            if s.get("durum") == "hata":
                durum("✗ HATA")
                m = s.get("hata") or "Bilinmeyen hata"
                ek = ("  →  CEREZ: SAFARI seçip tekrar dene."
                      if any(k in m.lower() for k in ("login", "cookie", "private", "sign in"))
                      else "  →  MOTORU GUNCELLE dene.")
                hata_yaz(m + ek)
                break
    except Exception as e:
        durum("✗ HATA")
        hata_yaz(str(e))
    finally:
        calisiyor[0] = False
        it["Indir"].Enabled = True


def kes_degisti(ev):
    """Aralık kutusu açılınca zaman alanlarını etkinleştir."""
    acik = it["Kes"].Checked
    for k in ("Bas", "Bit", "TamKare"):
        it[k].Enabled = acik


def zaman_sn(metin):
    """'1:30' → 90.0   Boş/geçersiz → None"""
    metin = (metin or "").strip().replace(",", ".")
    if not metin:
        return None
    try:
        parcalar = [float(p) for p in metin.split(":")]
    except ValueError:
        return False          # okunamadı
    if any(p < 0 for p in parcalar):
        return False
    toplam = 0.0
    for p in parcalar:
        toplam = toplam * 60 + p
    return toplam


def indir_tikla(ev):
    if calisiyor[0]:
        return
    link = (it["Url"].Text or "").strip()
    if not link.startswith("http"):
        durum("✗ Geçerli link yok")
        return

    bas = bit = None
    if it["Kes"].Checked:
        bas, bit = zaman_sn(it["Bas"].Text), zaman_sn(it["Bit"].Text)
        if bas is False or bit is False:
            durum("✗ Zaman okunamadı — örnek: 1:30")
            return
        if bas is not None and bit is not None and bit <= bas:
            durum("✗ Bitiş, başlangıçtan büyük olmalı")
            return

    calisiyor[0] = True
    it["Indir"].Enabled = False
    hata_yaz("")
    bar_ciz(0)
    durum("Başlatılıyor...")
    threading.Thread(
        target=indir_isi,
        args=(link,
              KALITELER[it["Kalite"].CurrentIndex][0],
              CEREZLER[it["Cerez"].CurrentIndex][0],
              it["MediaPool"].Checked,
              it["Timeline"].Checked,
              bas, bit, it["TamKare"].Checked),
        daemon=True,
    ).start()


def klasor_tikla(ev):
    try:
        istek("/api/klasor", zaman=5)
    except Exception:
        subprocess.Popen(["open", os.path.join(HOME, "Downloads", "İndirilenler")])


def guncelle_tikla(ev):
    def isle():
        durum("Motor güncelleniyor...")
        try:
            d = istek("/api/guncelle", {}, zaman=180)
            durum("Motor güncellendi")
            hata_yaz((d.get("cikti") or "")[-300:])
        except Exception as e:
            durum("✗ Güncellenemedi")
            hata_yaz(str(e))
    threading.Thread(target=isle, daemon=True).start()


def kapat(ev):
    disp.ExitLoop()


pencere.On.Kes.Clicked = kes_degisti
pencere.On.PanoBtn.Clicked = pano_tikla
pencere.On.Indir.Clicked = indir_tikla
pencere.On.KlasorBtn.Clicked = klasor_tikla
pencere.On.GuncelleBtn.Clicked = guncelle_tikla
pencere.On.KapatBtn.Clicked = kapat
pencere.On.IgWin.Close = kapat

pencere.Show()
threading.Thread(target=motoru_baslat, daemon=True).start()
disp.RunLoop()
pencere.Hide()
