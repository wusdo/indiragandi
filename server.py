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
FORMATLAR = {
    "mp3":   ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
    "720":   ["-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]",
              "--merge-output-format", "mp4"],
    "1080":  ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]",
              "--merge-output-format", "mp4"],
    "1440":  ["-f", "bv*[height<=1440][ext=mp4]+ba[ext=m4a]/bv*[height<=1440]+ba/b[height<=1440]",
              "--merge-output-format", "mp4"],
    "2160":  ["-f", "bv*[height<=2160][ext=mp4]+ba[ext=m4a]/bv*[height<=2160]+ba/b[height<=2160]",
              "--merge-output-format", "mp4"],
    "best":  ["-f", "bv*+ba/b", "--merge-output-format", "mp4"],
}

ISLER = {}          # id -> durum sözlüğü
ISLER_KILIT = threading.Lock()

PCT = re.compile(r"\[download\]\s+([\d.]+)%")
HIZ = re.compile(r"at\s+([\d.]+\w+/s)")
ETA = re.compile(r"ETA\s+([\d:]+)")


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


def indir_calistir(iid, url, format_kodu, tarayici):
    cmd = [YTDLP]
    cmd += FORMATLAR.get(format_kodu, FORMATLAR["best"])
    cmd += cerez_argumani(tarayici)
    cmd += [
        "-o", os.path.join(HEDEF, "%(uploader,channel|indirilen)s - %(title).80B.%(ext)s"),
        "--restrict-filenames",
        "--no-playlist",
        "--embed-metadata",
        "--embed-thumbnail",
        "--no-mtime",
        "--newline",
        "--progress",
        url,
    ]

    is_guncelle(iid, durum="calisiyor", asama="Bağlanıyor...")

    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, env=ENV)
    except Exception as e:
        is_guncelle(iid, durum="hata", hata=str(e))
        return

    son_satirlar = []
    parca = 0
    sadece_ses = format_kodu == "mp3"

    for satir in p.stdout:
        satir = satir.rstrip()
        if not satir:
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

    if p.returncode == 0:
        dosya, tam_yol = "", ""
        try:
            adaylar = [os.path.join(HEDEF, f) for f in os.listdir(HEDEF)
                       if not f.startswith(".")]
            if adaylar:
                tam_yol = max(adaylar, key=os.path.getmtime)
                dosya = os.path.basename(tam_yol)
        except Exception:
            pass
        is_guncelle(iid, durum="bitti", yuzde=100, asama="Tamam",
                    dosya=dosya, yol=tam_yol)
    else:
        with ISLER_KILIT:
            mevcut = ISLER.get(iid, {}).get("hata")
        mesaj = mevcut or (son_satirlar[-1] if son_satirlar else "Bilinmeyen hata")
        is_guncelle(iid, durum="hata", hata=mesaj)


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
                                       veri.get("cerez")),
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
