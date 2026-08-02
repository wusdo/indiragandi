# ▼ İNDİRAGANDİ ▼

**Pixel art temalı video indirme makinesi — Mac için.**
YouTube, Instagram, TikTok, X ve 1000+ siteden video indirir. İndirdiğini **doğrudan Premiere Pro, After Effects veya DaVinci Resolve projene atar.**

```
   ...K........K...
   ..KKKKKKKKKKKK..
   ..KBSSSPPSSSBK..
   ..KBSPPPPPPSBK..
   ..KBSSPPPPSSBK..
   ..KBBBBBBBBBBK..
   ..KKKKKKKKKKKK..
   ...K.K....K.K...
```

---

## Ne yapar

| | |
|---|---|
| **Tarayıcı paneli** | Pixel art arayüz, blok ilerleme çubuğu, 8-bit ses efektleri |
| **Premiere Pro** | İndirir → aktif bin'e atar → istersen timeline'a yerleştirir |
| **After Effects** | İndirir → Project paneline atar → istersen açık comp'a katman ekler |
| **DaVinci Resolve** | İndirir → Media Pool'a atar → istersen timeline'a append eder |
| **Terminal** | `indir <link>` tek satırda indirir |

**Kaliteler:** MP3 · 720p · 1080p · 1440p · 4K · MAX

Link yapıştırdığın anda kapak, başlık, kanal ve süre önizlemesi gelir.

---

## Kurulum

Homebrew, Python paketi, hiçbir şey gerekmiyor — kurulum her şeyi kendi indiriyor. **sudo istemez.**

```bash
git clone https://github.com/wusdo/indiragandi.git
cd indiragandi
bash kur.sh
```

Kurulum sonrası Adobe / Resolve uygulamalarını yeniden başlat.

---

## Kullanım

### Panel
`~/Applications/İndiragandi.app` → Dock'a sürükle, tıkla. Tarayıcıda `localhost:8767` açılır.

Linki kopyala → **PANO** → kalite seç → **İNDİR**.

### NLE eklentileri

| Uygulama | Menü |
|---|---|
| Premiere Pro | Window → Extensions → Indiragandi |
| After Effects | Window → Extensions → Indiragandi |
| DaVinci Resolve | Workspace → Scripts → Indiragandi |

### Terminal

```bash
gandi              # paneli aç
indir <link>       # en yüksek kalite mp4
indir              # panodaki linki indir
indir -s <link>    # sadece ses → mp3
indir -g           # motoru güncelle
```

İnen dosyalar: `~/Downloads/İndirilenler`

---

## Giriş gerektiren içerik

Instagram'ın gizli/takipçi-kısıtlı gönderileri için tarayıcı çerezi gerekir. Her panelde **ÇEREZ** seçici var:

```
ÇEREZ: SAFARI   ← seç, tekrar dene
```

Terminalden:
```bash
INDIR_COOKIE_BROWSER=safari indir "<link>"
```

Safari çerezleri için Terminal'e **Full Disk Access** vermen gerekebilir.

---

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| YouTube hata veriyor | Panelde **MOTORU GÜNCELLE** (veya `indir -g`) |
| Panel açılmıyor | Terminal'de `gandi` |
| Adobe paneli boş / görünmüyor | Uygulamayı tamamen kapat aç; `kur.sh` CEP debug modunu açar |
| "MOTOR KAPALI" uyarısı | Dock'taki İndiragandi.app'i bir kez aç |

Motor logu: `/tmp/indiragandi.log`

---

## Nasıl çalışıyor

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Tarayıcı   │   │ Adobe CEP   │   │   Resolve   │
│   paneli    │   │   paneli    │   │   betiği    │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       └─────────────────┼─────────────────┘
                         ▼
              localhost:8767  (server.py)
                         ▼
                  yt-dlp + ffmpeg
                         ▼
              ~/Downloads/İndirilenler
```

Tek bir yerel motor, üç arayüz. Motor sadece `127.0.0.1`'e bağlanır — dışarı açık değildir.

### Dosyalar

```
server.py                 motor (Python stdlib, bağımlılık yok)
ui.html                   tarayıcı paneli
cli/indir, cli/gandi      terminal komutları
eklentiler/adobe/         CEP paneli (Premiere + AE)
eklentiler/resolve/       Fusion UIManager betiği
kur.sh                    kurulum
```

---

## Gereksinimler

- macOS (Apple Silicon veya Intel)
- Python 3 (macOS'ta hazır gelir)
- Premiere Pro / After Effects 2020+ · DaVinci Resolve 17+ (eklentiler için, zorunlu değil)

---

## Not

İndirme motoru [yt-dlp](https://github.com/yt-dlp/yt-dlp)'dir. Yalnızca indirme hakkına sahip olduğun içerikler için kullan — telif ve platform şartları senin sorumluluğunda.

## Lisans

MIT
