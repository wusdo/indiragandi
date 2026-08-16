#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
İNDİRAGANDİ — yerel video indirme paneli
http://localhost:8767
"""

import json
import os
import re
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = 8767
BASE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
YTDLP = os.path.join(HOME, "bin", "yt-dlp")
FFMPEG_DIR = os.path.join(HOME, "bin")
HEDEF = os.path.join(HOME, "Downloads", "İndirilenler")

os.makedirs(HEDEF, exist_ok=True)

ENV = dict(os.environ)
ENV["PATH"] = FFMPEG_DIR + ":" + ENV.get("PATH", "")

# ---------------------------------------------------------------- formatlar
def _video_format(h):
    """
    Kurgu programları için format zinciri.
    Önce H.264 (avc1) aranır — Premiere/AE/Resolve'de en akıcı codec.
    Bulunamazsa (1440p+ genelde sadece VP9/AV1 olur) kaliteye düşülür.
    """
    zincir = (
        "bv*[vcodec^=avc1][height<={h}]+ba[ext=m4a]/"
        "bv*[vcodec^=avc1][height<={h}]+ba/"
        "bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
        "bv*[height<={h}]+ba/"
        "b[height<={h}]"
    ).format(h=h)
    return ["-f", zincir, "--merge-output-format", "mp4"]


FORMATLAR = {
    # Sese kapak gömmek mantıklı, videoya değil (aşağıdaki nota bak)
    "mp3":   ["-x", "--audio-format", "mp3", "--audio-quality", "0", "--embed-thumbnail"],
    "720":   _video_format(720),
    "1080":  _video_format(1080),
    "1440":  _video_format(1440),
    "2160":  _video_format(2160),
    "best":  ["-f", "bv*+ba/b", "--merge-output-format", "mp4"],
}

ISLER = {}          # id -> durum sözlüğü
ISLER_KILIT = threading.Lock()

PCT = re.compile(r"\[download\]\s+([\d.]+)%")
HIZ = re.compile(r"at\s+([\d.]+\w+/s)")
ETA = re.compile(r"ETA\s+([\d:]+)")


def zaman_sn(metin):
    """
    '90'  '1:30'  '01:30'  '1:02:03'  '1.5'  →  saniye (float)
    Boş / anlamsız → None
    """
    if metin is None:
        return None
    metin = str(metin).strip().replace(",", ".")
    if not metin:
        return None
    try:
        parcalar = [float(p) for p in metin.split(":")]
    except ValueError:
        return None
    if not parcalar or any(p < 0 for p in parcalar):
        return None
    toplam = 0.0
    for p in parcalar:                      # ss / dd:ss / ss:dd:ss
        toplam = toplam * 60 + p
    return toplam


def sn_etiket(sn):
    """125.0 → '2m05s'  (dosya adına güvenle giren biçim)"""
    sn = int(round(sn))
    s, d, sa = sn % 60, (sn // 60) % 60, sn // 3600
    return ("%dh%02dm%02ds" % (sa, d, s)) if sa else ("%dm%02ds" % (d, s))


def is_guncelle(iid, **kw):
    with ISLER_KILIT:
        if iid in ISLER:
            ISLER[iid].update(kw)


def cerez_argumani(tarayici):
    if tarayici and tarayici != "yok":
        return ["--cookies-from-browser", tarayici]
    return []


def bilgi_getir(url, tarayici=None):
    """Link hakkında başlık / süre / kapak bilgisi çeker."""
    cmd = [YTDLP, "--dump-single-json", "--no-warnings", "--no-playlist"]
    cmd += cerez_argumani(tarayici)
    cmd += [url]
    try:
        cikti = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=45, env=ENV)
        if cikti.returncode != 0:
            return {"hata": (cikti.stderr or "").strip().splitlines()[-1:] or ["Bilgi alınamadı"]}
        d = json.loads(cikti.stdout)
        return {
            "baslik": d.get("title") or "İsimsiz",
            "kanal": d.get("uploader") or d.get("channel") or "",
            "sure": d.get("duration") or 0,
            "kapak": d.get("thumbnail") or "",
            "site": d.get("extractor_key") or "",
        }
    except subprocess.TimeoutExpired:
        return {"hata": ["Zaman aşımı"]}
    except Exception as e:
        return {"hata": [str(e)]}


def _gecici_ag_hatasi(satirlar):
    """
    --download-sections, parçayı ffmpeg'e indirtiyor. ffmpeg yt-dlp'nin
    oturumunu taşımadığı için YouTube ara sıra o bağlantıya 403 dönüyor —
    aynı komut saniyeler sonra sorunsuz çalışabiliyor. Bu hatayı tanıyıp
    önce tekrar deniyor, sonra tamamını indirip yerelde kesiyoruz.
    """
    metin = " ".join(satirlar[-25:]).lower()
    return ("ffmpeg exited with code" in metin
            or "403" in metin
            or "forbidden" in metin)


def _yerel_kes(iid, yol, b, e, tam_kare):
    """İnmiş tam dosyayı yerelde istenen aralığa kırpar (ağ gerektirmez)."""
    if not yol or not os.path.exists(yol):
        return False
    kok, uzanti = os.path.splitext(yol)
    gecici = kok + ".kesiliyor" + (uzanti or ".mp4")
    cmd = [os.path.join(FFMPEG_DIR, "ffmpeg"), "-y", "-ss", "%.3f" % b]
    if e is not None:
        cmd += ["-t", "%.3f" % (e - b)]
    cmd += ["-i", yol]
    if tam_kare:
        # Tam istenen karede başlaması için kesim yeniden kodlanır (yavaş).
        cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac"]
    else:
        cmd += ["-c", "copy"]
    cmd += ["-movflags", "+faststart", gecici]

    is_guncelle(iid, asama="Yerelde kesiliyor...", yuzde=99)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    except Exception:
        r = None
    if r is not None and r.returncode == 0 and os.path.exists(gecici) \
       and os.path.getsize(gecici) > 0:
        os.replace(gecici, yol)
        return True
    if os.path.exists(gecici):
        try:
            os.remove(gecici)
        except OSError:
            pass
    return False


def indir_calistir(iid, url, format_kodu, tarayici,
                   bas=None, bit=None, tam_kare=False):
    # --- istenen aralık ---
    bas_sn, bit_sn = zaman_sn(bas), zaman_sn(bit)
    kesme_eki = ""
    b = e = None
    kesiliyor = bas_sn is not None or bit_sn is not None
    if kesiliyor:
        b = bas_sn if bas_sn is not None else 0.0
        e = bit_sn
        if e is not None and e <= b:
            is_guncelle(iid, durum="hata",
                        hata="Bitiş zamanı başlangıçtan büyük olmalı")
            return
        kesme_eki = " [%s-%s]" % (sn_etiket(b),
                                  sn_etiket(e) if e is not None else "son")

    ortak = [YTDLP]
    ortak += FORMATLAR.get(format_kodu, FORMATLAR["best"])
    ortak += cerez_argumani(tarayici)
    ortak += [
        "-o", os.path.join(HEDEF,
                           "%(uploader,channel|indirilen)s - %(title).80B"
                           + kesme_eki + ".%(ext)s"),
        "--restrict-filenames",
        "--no-playlist",
        "--embed-metadata",
        # --embed-thumbnail videoya UYGULANMAZ: kapak, mp4 içine ikinci bir
        # PNG "video" akışı olarak giriyor ve NLE'ler bunu yanlış yorumluyor.
        # Sadece mp3'te var (bkz. FORMATLAR).
        "--no-mtime",
        "--newline",
        "--progress",
        # Biten dosyanın yolunu tahmin etmek yerine yt-dlp'nin kendisinden al.
        # (Aynı anda birden fazla indirme varsa "klasördeki en yeni dosya"
        #  başka bir işin geçici ses parçasına denk gelebiliyordu.)
        "--no-simulate",
        "--print", "after_move:IGYOL|%(filepath)s",
    ]

    kesme_args = []
    if kesiliyor:
        kesme_args = ["--download-sections",
                      "*%s-%s" % (b, e if e is not None else "inf")]
        if tam_kare:
            kesme_args += ["--force-keyframes-at-cuts"]

    sadece_ses = format_kodu == "mp3"
    bas_zaman = time.time()

    # 1) Hızlı yol: yalnızca istenen aralığı indir.
    kod, yol, satirlar = _ytdlp_calistir(iid, ortak + kesme_args + [url], sadece_ses)

    # 2) Aralık indirmesi geçici bir ağ hatasına takıldıysa bir kez tekrar dene.
    if kod != 0 and kesiliyor and _gecici_ag_hatasi(satirlar):
        is_guncelle(iid, asama="Bağlantı reddedildi, tekrar deneniyor...",
                    yuzde=0, hata="")
        time.sleep(2)
        kod, yol, satirlar = _ytdlp_calistir(iid, ortak + kesme_args + [url],
                                             sadece_ses)

        # 3) Hâlâ olmuyorsa tamamını indirip yerelde kes — yavaş ama kesin.
        if kod != 0 and _gecici_ag_hatasi(satirlar):
            is_guncelle(iid, asama="Parça indirilemedi, tamamı indiriliyor...",
                        yuzde=0, hata="")
            bas_zaman = time.time()
            kod, yol, satirlar = _ytdlp_calistir(iid, ortak + [url], sadece_ses)
            if kod == 0:
                yol = _tam_yol_bul(yol, bas_zaman)
                if not _yerel_kes(iid, yol, b, e, tam_kare):
                    is_guncelle(iid, durum="hata",
                                hata="İndirildi ama istenen aralık kesilemedi")
                    return

    if kod == 0:
        tam_yol = _tam_yol_bul(yol, bas_zaman)
        dosya = os.path.basename(tam_yol) if tam_yol else ""
        is_guncelle(iid, durum="bitti", yuzde=100, asama="Tamam",
                    dosya=dosya, yol=tam_yol)
    else:
        with ISLER_KILIT:
            mevcut = ISLER.get(iid, {}).get("hata")
        mesaj = mevcut or (satirlar[-1] if satirlar else "Bilinmeyen hata")
        is_guncelle(iid, durum="hata", hata=mesaj)


def _tam_yol_bul(gercek_yol, bas_zaman):
    if gercek_yol and os.path.exists(gercek_yol):
        return gercek_yol
    # Yedek plan: yalnızca BU iş başladıktan sonra oluşmuş,
    # tamamlanmış (ara parça olmayan) dosyalara bak.
    try:
        adaylar = []
        for f in os.listdir(HEDEF):
            if f.startswith(".") or ".f" in f.rsplit(".", 2)[0][-6:]:
                continue
            p2 = os.path.join(HEDEF, f)
            if os.path.getmtime(p2) >= bas_zaman - 1:
                adaylar.append(p2)
        if adaylar:
            return max(adaylar, key=os.path.getmtime)
    except Exception:
        pass
    return ""


def _ytdlp_calistir(iid, cmd, sadece_ses):
    """
    yt-dlp'yi çalıştırıp ilerlemeyi işe yansıtır.
    (çıkış kodu, yt-dlp'nin bildirdiği dosya yolu, son çıktı satırları) döner.
    """
    is_guncelle(iid, durum="calisiyor", asama="Bağlanıyor...")

    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, env=ENV)
    except Exception as e:
        return 1, "", [str(e)]

    son_satirlar = []
    parca = 0
    gercek_yol = ""

    for satir in p.stdout:
        satir = satir.rstrip()
        if not satir:
            continue

        # yt-dlp'nin bildirdiği kesin çıktı yolu
        if satir.startswith("IGYOL|"):
            gercek_yol = satir[6:].strip()
            continue

        son_satirlar.append(satir)
        son_satirlar[:] = son_satirlar[-25:]

        m = PCT.search(satir)
        if m:
            yeni = {"yuzde": float(m.group(1))}
            h = HIZ.search(satir)
            e = ETA.search(satir)
            if h:
                yeni["hiz"] = h.group(1)
            if e:
                yeni["eta"] = e.group(1)
            is_guncelle(iid, **yeni)
        elif satir.startswith("[Merger]") or "Merging formats" in satir:
            is_guncelle(iid, asama="Birleştiriliyor...", yuzde=99)
        elif satir.startswith("[ExtractAudio]"):
            is_guncelle(iid, asama="MP3'e çevriliyor...", yuzde=99)
        elif satir.startswith("[EmbedThumbnail]") or satir.startswith("[Metadata]"):
            is_guncelle(iid, asama="Kapak ve etiketler...", yuzde=99)
        elif satir.startswith("[download] Destination:"):
            parca += 1
            if sadece_ses:
                etiket = "Ses indiriliyor..."
            elif parca == 1:
                etiket = "Görüntü indiriliyor... (1/2)"
            else:
                etiket = "Ses indiriliyor... (2/2)"
            is_guncelle(iid, asama=etiket, yuzde=0)
        elif satir.startswith("ERROR:"):
            is_guncelle(iid, hata=satir[6:].strip())

    p.wait()
    return p.returncode, gercek_yol, son_satirlar


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _gonder(self, kod, govde, tip="application/json; charset=utf-8"):
        if isinstance(govde, (dict, list)):
            govde = json.dumps(govde, ensure_ascii=False)
        if isinstance(govde, str):
            govde = govde.encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", tip)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        # Adobe CEP panelleri ve Resolve betikleri farklı köken üzerinden bağlanır
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        # GitHub Pages'teki https tanıtım sayfası buraya (yerel ağ) istek atarken
        # Chrome "Private Network Access" ön kontrolü yapar; bu başlık olmadan
        # istek engellenir ve panel demo moduna düşer.
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(govde)

    def do_OPTIONS(self):
        self._gonder(204, b"", "text/plain")

    def do_GET(self):
        yol = urlparse(self.path)

        if yol.path in ("/", "/index.html"):
            try:
                with open(os.path.join(BASE, "ui.html"), "rb") as f:
                    self._gonder(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._gonder(404, b"ui.html yok", "text/plain; charset=utf-8")
            return

        if yol.path == "/api/durum":
            iid = parse_qs(yol.query).get("id", [""])[0]
            with ISLER_KILIT:
                self._gonder(200, ISLER.get(iid, {"durum": "yok"}))
            return

        if yol.path in ("/tanitim", "/tanitim/", "/tanitim.html"):
            try:
                with open(os.path.join(BASE, "tanitim.html"), "rb") as f:
                    self._gonder(200, f.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._gonder(404, b"tanitim.html kurulu degil",
                             "text/plain; charset=utf-8")
            return

        # tanıtım sayfasının ihtiyaç duyduğu dosyalar
        STATIK = {
            "/tutorial.html":   ("rehber.html", "text/html; charset=utf-8"),
            "/rehber":          ("rehber.html", "text/html; charset=utf-8"),
            "/indiragandi.mp4": ("indiragandi.mp4", "video/mp4"),
        }
        if yol.path in STATIK:
            dosya, tip = STATIK[yol.path]
            try:
                with open(os.path.join(BASE, dosya), "rb") as f:
                    self._gonder(200, f.read(), tip)
            except FileNotFoundError:
                self._gonder(404, b"yok", "text/plain; charset=utf-8")
            return

        if yol.path == "/api/pano":
            try:
                metin = subprocess.run(["pbpaste"], capture_output=True,
                                       text=True, timeout=5).stdout.strip()
            except Exception:
                metin = ""
            self._gonder(200, {"metin": metin})
            return

        if yol.path == "/api/klasor":
            subprocess.Popen(["open", HEDEF])
            self._gonder(200, {"ok": True})
            return

        if yol.path == "/api/gecmis":
            try:
                dosyalar = [f for f in os.listdir(HEDEF) if not f.startswith(".")]
                dosyalar.sort(key=lambda f: os.path.getmtime(os.path.join(HEDEF, f)),
                              reverse=True)
                liste = []
                for f in dosyalar[:12]:
                    p = os.path.join(HEDEF, f)
                    liste.append({"ad": f, "mb": round(os.path.getsize(p) / 1048576, 1)})
                self._gonder(200, liste)
            except Exception as e:
                self._gonder(200, [])
            return

        self._gonder(404, {"hata": "yok"})

    def do_POST(self):
        yol = urlparse(self.path).path
        uzunluk = int(self.headers.get("Content-Length") or 0)
        try:
            veri = json.loads(self.rfile.read(uzunluk) or b"{}")
        except Exception:
            veri = {}

        if yol == "/api/bilgi":
            url = (veri.get("url") or "").strip()
            if not url.startswith("http"):
                self._gonder(400, {"hata": ["Geçersiz link"]})
                return
            self._gonder(200, bilgi_getir(url, veri.get("cerez")))
            return

        if yol == "/api/indir":
            url = (veri.get("url") or "").strip()
            if not url.startswith("http"):
                self._gonder(400, {"hata": "Geçersiz link"})
                return
            iid = uuid.uuid4().hex[:10]
            with ISLER_KILIT:
                ISLER[iid] = {"durum": "basliyor", "yuzde": 0, "asama": "Sıraya alındı",
                              "hiz": "", "eta": "", "dosya": "", "yol": "", "hata": "",
                              "baslangic": time.time()}
            t = threading.Thread(target=indir_calistir,
                                 args=(iid, url, veri.get("format", "1080"),
                                       veri.get("cerez"),
                                       veri.get("bas"), veri.get("bit"),
                                       bool(veri.get("tam_kare"))),
                                 daemon=True)
            t.start()
            self._gonder(200, {"id": iid})
            return

        if yol == "/api/guncelle":
            try:
                r = subprocess.run([YTDLP, "-U"], capture_output=True, text=True,
                                   timeout=180, env=ENV)
                self._gonder(200, {"cikti": (r.stdout + r.stderr).strip()[-400:]})
            except Exception as e:
                self._gonder(200, {"cikti": str(e)})
            return

        self._gonder(404, {"hata": "yok"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("İNDİRAGANDİ → http://localhost:%d" % PORT)
    print("Hedef klasör:", HEDEF)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
