#!/bin/bash
# ============================================================
#  İNDİRAGANDİ — kurulum
#  Kullanım:  bash kur.sh
# ============================================================
set -e

KAYNAK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HOME/bin"
UYG="$BIN/indiragandi"
CEP="$HOME/Library/Application Support/Adobe/CEP/extensions/com.indiragandi.panel"
RES="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
APP="$HOME/Applications/İndiragandi.app"

echo
echo "  ▼ İNDİRAGANDİ KURULUMU"
echo "  ──────────────────────"
echo

mkdir -p "$BIN" "$UYG" "$HOME/Applications" "$HOME/Downloads/İndirilenler"

# ---------------------------------------------- 1. yt-dlp
echo "[1/6] yt-dlp indiriliyor..."
curl -sL -o "$BIN/yt-dlp" \
  https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos
chmod +x "$BIN/yt-dlp"
echo "      ✓ $("$BIN/yt-dlp" --version)"

# ---------------------------------------------- 2. ffmpeg
echo "[2/6] ffmpeg aranıyor..."
if [ -x "$BIN/ffmpeg" ]; then
  echo "      ✓ zaten kurulu"
elif command -v ffmpeg >/dev/null 2>&1; then
  ln -sf "$(command -v ffmpeg)" "$BIN/ffmpeg"
  echo "      ✓ sistemdeki ffmpeg bağlandı"
elif command -v brew >/dev/null 2>&1; then
  brew install ffmpeg
  ln -sf "$(command -v ffmpeg)" "$BIN/ffmpeg"
  echo "      ✓ brew ile kuruldu"
else
  echo "      · Homebrew yok, pip ile taşınabilir sürüm kuruluyor..."
  python3 -m pip install --user --quiet --upgrade imageio-ffmpeg
  FF=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
  ln -sf "$FF" "$BIN/ffmpeg"
  echo "      ✓ $("$BIN/ffmpeg" -version 2>&1 | head -1 | cut -c1-40)"
fi

# ---------------------------------------------- 3. motor + arayüz
echo "[3/6] Motor ve panel kopyalanıyor..."
cp "$KAYNAK/server.py" "$KAYNAK/ui.html" "$UYG/"
[ -f "$KAYNAK/docs/index.html" ] && cp "$KAYNAK/docs/index.html" "$UYG/tanitim.html"
cp "$KAYNAK/cli/indir" "$KAYNAK/cli/gandi" "$BIN/"
chmod +x "$BIN/indir" "$BIN/gandi"
echo "      ✓ $UYG"

# ---------------------------------------------- 4. PATH
echo "[4/6] PATH ayarlanıyor..."
if ! grep -q 'HOME/bin' "$HOME/.zshrc" 2>/dev/null; then
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.zshrc"
  echo "      ✓ ~/.zshrc güncellendi"
else
  echo "      ✓ zaten ekli"
fi

# ---------------------------------------------- 5. Mac uygulaması
echo "[5/6] İndiragandi.app oluşturuluyor..."
TMPAS=$(mktemp /tmp/indiragandi.XXXXXX.applescript)
printf 'do shell script "$HOME/bin/gandi"\n' > "$TMPAS"
rm -rf "$APP"
osacompile -o "$APP" "$TMPAS" 2>/dev/null
rm -f "$TMPAS"
echo "      ✓ $APP"

# ---------------------------------------------- 6. NLE eklentileri
echo "[6/6] Premiere / After Effects / Resolve eklentileri..."

if [ -d "$HOME/Library/Application Support/Adobe" ]; then
  for v in 9 10 11 12 13; do
    defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1 2>/dev/null || true
  done
  rm -rf "$CEP"
  mkdir -p "$CEP"
  cp -R "$KAYNAK/eklentiler/adobe/." "$CEP/"
  echo "      ✓ Premiere + After Effects paneli"
else
  echo "      · Adobe bulunamadı, atlandı"
fi

if [ -d "$(dirname "$RES")" ]; then
  mkdir -p "$RES"
  cp "$KAYNAK/eklentiler/resolve/Indiragandi.py" "$RES/Indiragandi.py"
  echo "      ✓ DaVinci Resolve betiği"
else
  echo "      · Resolve bulunamadı, atlandı"
fi

# ---------------------------------------------- bitti
cat <<'SON'

  ════════════════════════════════════════════════
   KURULDU

   Panel      →  ~/Applications/İndiragandi.app
                 (Dock'a sürükle)
   Terminal   →  gandi          paneli aç
                 indir <link>   hızlı indirme

   Premiere / AE     →  Window > Extensions > Indiragandi
   DaVinci Resolve   →  Workspace > Scripts > Indiragandi

   İnenler    →  ~/Downloads/İndirilenler
  ════════════════════════════════════════════════

SON
