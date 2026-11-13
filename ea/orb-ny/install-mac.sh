#!/bin/bash
# ORB NY EA installer for MetaTrader 5 on macOS.
# Copies ORB_NY_EA.mq5 into every MT5 MQL5/Experts folder found and tries to compile it.
# Usage (Terminal):  bash ~/Downloads/install-mac.sh

EA_NAME="ORB_NY_EA.mq5"
EA_URL="https://raw.githubusercontent.com/alikamal94/alikamal94/claude/charming-lovelace-9v31cy/ea/orb-ny/ORB_NY_EA.mq5"
HERE="$(cd "$(dirname "$0")" && pwd)"

# 1) Find the EA file (next to this script, in Downloads, or download it)
SRC=""
for f in "$HERE/$EA_NAME" "$HOME/Downloads/$EA_NAME"; do
  [ -f "$f" ] && SRC="$f" && break
done
if [ -z "$SRC" ]; then
  echo "Downloading $EA_NAME ..."
  SRC="$(mktemp -d)/$EA_NAME"
  curl -fsSL "$EA_URL" -o "$SRC" || { echo "Download failed. Put $EA_NAME next to this script."; exit 1; }
fi
echo "Using $SRC"

# 2) Find MT5 Experts folders (official app + broker-branded apps)
EXPERTS=()
while IFS= read -r d; do EXPERTS+=("$d"); done < <(
  find "$HOME/Library/Application Support" -maxdepth 10 -type d -path "*/MQL5/Experts" 2>/dev/null
)
if [ ${#EXPERTS[@]} -eq 0 ]; then
  echo "No MetaTrader 5 folder found. Install MetaTrader 5 for Mac, open it once, then run this again."
  exit 1
fi

# Wine that ships inside the MetaTrader app (used to run MetaEditor for compiling)
WINE="$(find /Applications "$HOME/Applications" -maxdepth 7 -type f \( -name wine64 -o -name wine \) -path "*MetaTrader*" 2>/dev/null | head -n 1)"

for EXP in "${EXPERTS[@]}"; do
  cp -f "$SRC" "$EXP/$EA_NAME" && echo "Copied to: $EXP"
  INSTALL="$(cd "$EXP/../.." && pwd)"
  EDITOR="$INSTALL/metaeditor64.exe"
  PREFIX="${INSTALL%%/drive_c/*}"
  if [ -n "$WINE" ] && [ -f "$EDITOR" ] && [ -d "$PREFIX/drive_c" ]; then
    WINPATH="Z:$(echo "$EXP/$EA_NAME" | sed 's#/#\\#g')"
    echo "  Compiling..."
    (cd "$INSTALL" && WINEPREFIX="$PREFIX" WINEDEBUG=-all "$WINE" metaeditor64.exe "/compile:$WINPATH" /log >/dev/null 2>&1)
  fi
  if [ -f "$EXP/ORB_NY_EA.ex5" ]; then
    echo "  Compiled OK"
  else
    echo "  Not compiled yet. In MT5 press F4 (MetaEditor), open Experts > ORB_NY_EA.mq5 and press F7."
  fi
done

echo
echo "Done. In MT5: Navigator > Expert Advisors > right-click > Refresh, then drag ORB_NY_EA onto your chart."
