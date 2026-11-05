#!/usr/bin/env bash
# Salin satu diagram Mermaid ke clipboard, siap tempel ke mermaid.live.
# Pakai: ./copy.sh            -> daftar diagram
#        ./copy.sh 3          -> salin diagram nomor 3
#        ./copy.sh 03-login-sesi-logout.mmd
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"

if [ $# -eq 0 ]; then
  ls -1 "$dir"/*.mmd | xargs -n1 basename
  echo
  echo "usage: $(basename "$0") <nomor|nama-file>"
  exit 0
fi

target="$1"
if [ ! -f "$dir/$target" ]; then
  target="$(ls -1 "$dir" | grep -E "^0*${1}-.*\.mmd$" | head -1)"
fi
if [ -z "${target:-}" ] || [ ! -f "$dir/$target" ]; then
  echo "tidak ditemukan: $1" >&2
  exit 1
fi

sudo=""
if command -v wl-copy >/dev/null 2>&1; then
  wl-copy < "$dir/$target"
elif command -v xclip >/dev/null 2>&1; then
  xclip -selection clipboard < "$dir/$target"
elif command -v xsel >/dev/null 2>&1; then
  xsel --clipboard --input < "$dir/$target"
else
  cat "$dir/$target"
  echo
  echo "(tidak ada alat clipboard; isi file dicetak di atas)" >&2
  exit 0
fi
echo "tersalin ke clipboard: $target"
