#!/usr/bin/env bash
#
# install-fastcontext-laptop.sh
# ------------------------------------------------------------------------------
# Installeert de FastContext-scout-CLI op je laptop (Linux of macOS) en wijst
# 'm naar het Q4-model dat op beestjeai2 draait (llama.cpp, poort 8057).
#
# Wat het doet:
#   1. checkt/installeert dependencies: git, ripgrep (rg), uv
#   2. cloont de fork Cirius1792/fastcontext (gepind op de geteste commit)
#   3. past onze patches toe: (a) leading-slash paden -> workdir-relatief,
#      (b) fix voor de crash/lege-answer in de --citation-parser
#   4. draait `uv sync`
#   5. schrijft env-config + een `fastcontext`-commando (+ `fc`-alias) in ~/.local/bin
#   6. installeert de FastContext-skill voor je agent-runtime (pi/claude/codex)
#   7. test de verbinding met beestjeai2
#
# Herhaald draaien is veilig: de installatie wordt schoon teruggezet naar de
# geteste commit en opnieuw gepatcht (idempotent) — zo krijg je updates binnen.
#
# Gebruik:
#   chmod +x install-fastcontext-laptop.sh
#   AGENT=pi ./install-fastcontext-laptop.sh
#
# Overrides (env):
#   FC_DIR       installmap            (default: ~/fastcontext)
#   FC_ENDPOINT  host:poort op beestjeai2
#                (default: 100.98.124.25:8057 = Tailscale-IP; LAN: beestjeai2.local:8057)
#   FC_MODEL     served-model-name     (default: fastcontext-q4)
#   AGENT        pi | claude | codex | auto | none   (skills-locatie; default auto)
# ------------------------------------------------------------------------------
set -euo pipefail

FC_DIR="${FC_DIR:-$HOME/fastcontext}"
FC_ENDPOINT="${FC_ENDPOINT:-100.98.124.25:8057}"
FC_MODEL="${FC_MODEL:-fastcontext-q4}"
FC_REPO="https://github.com/Cirius1792/fastcontext.git"
FC_COMMIT="1522d6d6b5e040e817b468e12826662aa069a8b0"   # geteste commit
BINDIR="$HOME/.local/bin"

say(){ printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[let op]\033[0m %s\n' "$*"; }
die(){ printf '\033[1;31m[fout]\033[0m %s\n' "$*" >&2; exit 1; }

# --- 0. platform + package manager -------------------------------------------
OS="$(uname -s)"
install_pkg(){ # $1 = commando dat moet bestaan, $2 = brew-pakket, $3 = apt-pakket
  command -v "$1" >/dev/null 2>&1 && return 0
  say "installeer '$1'..."
  if [ "$OS" = "Darwin" ]; then
    command -v brew >/dev/null 2>&1 || die "Homebrew ontbreekt. Installeer via https://brew.sh en draai dit script opnieuw."
    brew install "$2"
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y "$3"
  else
    die "Kan '$1' niet automatisch installeren op dit platform. Installeer het handmatig en draai opnieuw."
  fi
}

# --- 1. dependencies ---------------------------------------------------------
say "Dependencies controleren..."
install_pkg git git git
install_pkg rg ripgrep ripgrep
if ! command -v uv >/dev/null 2>&1; then
  say "installeer uv (astral)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || die "uv niet gevonden na installatie. Zorg dat ~/.local/bin in je PATH staat."

# --- 2. clone / update (idempotent, gepind) ----------------------------------
if [ -d "$FC_DIR/.git" ]; then
  say "FastContext bestaat al in $FC_DIR — schoon terugzetten naar geteste commit..."
  git -C "$FC_DIR" fetch --depth 1 origin "$FC_COMMIT" 2>/dev/null || git -C "$FC_DIR" fetch origin
  git -C "$FC_DIR" reset --hard "$FC_COMMIT"     # verwijdert een eerder toegepaste patch
  git -C "$FC_DIR" clean -fd -- src >/dev/null 2>&1 || true
else
  say "FastContext klonen naar $FC_DIR ..."
  git clone "$FC_REPO" "$FC_DIR"
  git -C "$FC_DIR" checkout -q "$FC_COMMIT"
fi

# --- 3. patches (base64-ingebakken = byte-exact) -----------------------------
say "Patches toepassen (pad-fix + citation-fix)..."
PATCH_FILE="$(mktemp)"
base64 --decode > "$PATCH_FILE" <<'PATCH_B64'
ZGlmZiAtLWdpdCBhL3NraWxscy9mYXN0Y29udGV4dC9TS0lMTC5tZCBiL3NraWxscy9mYXN0Y29udGV4dC9TS0lMTC5tZAppbmRleCA5NjEyNmZiLi42MTQyNjZiIDEwMDY0NAotLS0gYS9za2lsbHMvZmFzdGNvbnRleHQvU0tJTEwubWQKKysrIGIvc2tpbGxzL2Zhc3Rjb250ZXh0L1NLSUxMLm1kCkBAIC0yNywxMiArMjcsNDQgQEAgRmFzdCwgYXV0b25vbW91cyBzdWJhZ2VudCB0aGF0IGV4cGxvcmVzIGNvZGViYXNlcyB0aHJvdWdoIG11bHRpLXN0ZXAgcmVhc29uaW5nLgogIyMgVXNhZ2UKIAogYGBgYmFzaAotIyBQcmVjaXNlIGFuc3dlciB3aXRoIGZpbGU6bGluZSBjaXRhdGlvbnMKLWZhc3Rjb250ZXh0IC1xICI8ZGV0YWlsZWQgcXVlc3Rpb24+IiAtLW1heC10dXJucyA4IC0tY2l0YXRpb24KKyMgRGVmYXVsdDogY29tcGFjdCBmaWxlOmxpbmUgZXZpZGVuY2UgKHRoaXMgaXMgdGhlIHBvaW50IOKAlCBpdCBzYXZlcyB5b3VyIGNvbnRleHQpCitmYXN0Y29udGV4dCAtcSAiPHNwZWNpZmljIHF1ZXN0aW9uPiIgLS1tYXgtdHVybnMgMTIgLS1jaXRhdGlvbgogCi0jIERlZXAgdHJhY2VzIG9yIGFyY2hpdGVjdHVyZSBxdWVzdGlvbnMKLWZhc3Rjb250ZXh0IC1xICI8Y29tcGxleCBxdWVzdGlvbj4iIC0tbWF4LXR1cm5zIDEyIC0tY2l0YXRpb24KKyMgRGVlcCBhcmNoaXRlY3R1cmUgdHJhY2VzIGFjcm9zcyBtYW55IGZpbGVzCitmYXN0Y29udGV4dCAtcSAiPGNvbXBsZXggcXVlc3Rpb24+IiAtLW1heC10dXJucyAxNiAtLWNpdGF0aW9uCiAKLSMgQnJvYWRlciBzdW1tYXJ5IHdpdGggZXhwbGFuYXRpb25zIChtYXkgaW5jbHVkZSBzb21lIG5vaXNlKQotZmFzdGNvbnRleHQgLXEgIjxxdWVzdGlvbj4iIC0tbWF4LXR1cm5zIDgKKyMgT25seSB3aGVuIHlvdSBzcGVjaWZpY2FsbHkgd2FudCB0aGUgbW9kZWwncyBmdWxsIHJlYXNvbmluZywgbm90IGp1c3QgY2l0YXRpb25zCitmYXN0Y29udGV4dCAtcSAiPHF1ZXN0aW9uPiIgLS1tYXgtdHVybnMgMTIKIGBgYAorCisqKktlZXAgYC0tY2l0YXRpb25gIG9uIGJ5IGRlZmF1bHQqKiDigJQgdGhlIGNvbXBhY3QgY2l0YXRpb25zIGFyZSB0aGUgd2hvbGUgdmFsdWUgb2YKK2Egc2NvdXQ6IHRoZXkgbGV0IHlvdSBhY3Qgd2l0aG91dCBwdWxsaW5nIGVudGlyZSBmaWxlcyBpbnRvIHlvdXIgb3duIGNvbnRleHQuIFRoZQorcGF0Y2hlZCBDTEkgbmV2ZXIgcmV0dXJucyBhbiBlbXB0eSBhbnN3ZXI6IGlmIHRoZSBtb2RlbCBwcm9kdWNlcyBmaWxlOmxpbmUKK2NpdGF0aW9ucyB5b3UgZ2V0IHRob3NlLCBvdGhlcndpc2UgaXQgZmFsbHMgYmFjayB0byB0aGUgZnVsbCBhbnN3ZXIuIFNvIHRoZXJlIGlzIG5vCitkb3duc2lkZSB0byBgLS1jaXRhdGlvbmAuIE9ubHkgZHJvcCBpdCB3aGVuIHlvdSBkZWxpYmVyYXRlbHkgd2FudCB0aGUgcmVhc29uaW5nLgorCitEZWZhdWx0IHRvIGAtLW1heC10dXJucyAxMmAgKDE2IGZvciB3aWRlL2FyY2hpdGVjdHVyYWwgdHJhY2VzKS4KKworIyMgR2V0dGluZyBnb29kIHJlc3VsdHMKKworZmFzdGNvbnRleHQgaXMgYmFja2VkIGJ5IGEgc21hbGwsIGZhc3QgbW9kZWwuIEl0IGV4Y2VscyBhdCAqKmxvY2F0aW5nKiogY29kZSBhbmQKKyoqdHJhY2luZyoqIGxvZ2ljLCBidXQgaXMgbGVzcyByZWxpYWJsZSBhdCBleGhhdXN0aXZlLCB3aWRlIHN3ZWVwcyBpbiBvbmUgc2hvdC4KKworLSAqKkJlIHNwZWNpZmljLioqICJXaGVyZSBpcyBKV1QgdmVyaWZpZWQgYW5kIHdoZXJlIGFyZSB0b2tlbnMgaXNzdWVkPyIgYmVhdHMKKyAgImV4cGxhaW4gdGhlIGF1dGggc3lzdGVtIi4KKy0gKipPbmUgY29uY2VybiBwZXIgcXVlcnkuKiogQXNrIGFib3V0IGEgc2luZ2xlIGJlaGF2aW9yL2Zsb3cgYXQgYSB0aW1lLgorLSAqKlNwbGl0IGxhcmdlIGF1ZGl0cy4qKiBJbnN0ZWFkIG9mICJjaGVjayBldmVyeSByb3V0ZSBmaWxlIGZvciBtaXNzaW5nIGF1dGggaW4KKyAgb25lIGNhbGwiLCBsb29wIHBlciBmaWxlL2FyZWE6CisgIGBgYGJhc2gKKyAgZm9yIGYgaW4gZGFzaGJvYXJkIGluaXRpYXRpdmVzIGh5cG90aGVzZXMgYWRtaW47IGRvCisgICAgZmFzdGNvbnRleHQgLXEgIkluIGFwcC9yb3V0ZXMvJGYucHksIGxpc3QgZWFjaCBlbmRwb2ludCBhbmQgd2hpY2ggYXV0aAorICAgICAgZGVwZW5kZW5jeSAoZ2V0X2N1cnJlbnRfdXNlciAvIHJlcXVpcmVfcm9sZSAvIHJlcXVpcmVfZWRpdG9yIC8KKyAgICAgIHJlcXVpcmVfYWRtaW4pIGl0IHVzZXMuIEZsYWcgYW55IGVuZHBvaW50IHdpdGggbm8gYXV0aC4iIC0tbWF4LXR1cm5zIDEwCisgIGRvbmUKKyAgYGBgCisgIFRoZW4gY29tYmluZSB0aGUgcmVzdWx0cyB5b3Vyc2VsZi4gU21hbGxlciwgZm9jdXNlZCBjYWxscyBhcmUgZmFzdGVyIGFuZCBmYXIKKyAgbW9yZSBhY2N1cmF0ZSB0aGFuIG9uZSBnaWFudCByZXF1ZXN0LgorLSAqKk5hbWUgdGhlIGxhbmd1YWdlL3BhdGhzKiogd2hlbiB5b3Uga25vdyB0aGVtICgiVHlwZVNjcmlwdCByZXBvIiwgImxvb2sgaW4KKyAgc3JjL2xpYi8iKSDigJQgaXQgc3RvcHMgdGhlIG1vZGVsIGd1ZXNzaW5nIHRoZSB3cm9uZyBzdGFjay4KKy0gKipUcnVzdCB0aGUgZmlsZTpsaW5lIHRhcmdldHMsIHZlcmlmeSB0aGUgcHJvc2UuKiogTG9jYWxpemF0aW9uIGlzIHRoZSBzdHJvbmcKKyAgc3VpdDsgb3BlbiB0aGUgY2l0ZWQgZmlsZXMgdG8gY29uZmlybSBkZXRhaWxzIGJlZm9yZSBhY3RpbmcuCmRpZmYgLS1naXQgYS9zcmMvZmFzdGNvbnRleHQvYWdlbnQvdG9vbC9nbG9iLnB5IGIvc3JjL2Zhc3Rjb250ZXh0L2FnZW50L3Rvb2wvZ2xvYi5weQppbmRleCA0NTA2MzQ2Li4zNDgyZTlmIDEwMDY0NAotLS0gYS9zcmMvZmFzdGNvbnRleHQvYWdlbnQvdG9vbC9nbG9iLnB5CisrKyBiL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL2dsb2IucHkKQEAgLTMsNyArMyw3IEBAIGltcG9ydCBzdWJwcm9jZXNzCiBmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgKIAogZnJvbSAudG9vbCBpbXBvcnQgVG9vbAotZnJvbSAudXRpbHMgaW1wb3J0IFJHX1BBVEgKK2Zyb20gLnV0aWxzIGltcG9ydCBSR19QQVRILCByZXNvbHZlX3dpdGhpbl9jd2QKIAogCiBkZWYgcnVuKGRpcmVjdG9yeTogc3RyLCBwYXR0ZXJuOiBzdHIsIGN3ZDogc3RyKSAtPiBzdHI6CkBAIC00NiwxMSArNDYsMTIgQEAgY2xhc3MgR2xvYlRvb2woVG9vbCk6CiAgICAgICAgIGRpcmVjdG9yeSA9IHBhcmFtcy5nZXQoImRpcmVjdG9yeSIsIGN3ZCkKICAgICAgICAgcGF0dGVybiA9IHBhcmFtcy5nZXQoInBhdHRlcm4iKQogCi0gICAgICAgIHAgPSBQYXRoKGRpcmVjdG9yeSkKLSAgICAgICAgaWYgbm90IHAuaXNfZGlyKCk6Ci0gICAgICAgICAgICByZXR1cm4gZiI8c3lzdGVtLXJlbWluZGVyPkVycm9yOiBkaXJlY3RvcnkgYHtkaXJlY3Rvcnl9YCBkb2VzIG5vdCBleGlzdCBvciBpcyBub3QgYSBkaXJlY3RvcnkuPC9zeXN0ZW0tcmVtaW5kZXI+IgotICAgICAgICBpZiBub3QgcC5yZXNvbHZlKCkuaXNfcmVsYXRpdmVfdG8oUGF0aChjd2QpLnJlc29sdmUoKSk6CisgICAgICAgIHJlc29sdmVkID0gcmVzb2x2ZV93aXRoaW5fY3dkKGRpcmVjdG9yeSwgY3dkKQorICAgICAgICBpZiByZXNvbHZlZCBpcyBOb25lOgogICAgICAgICAgICAgcmV0dXJuIGYiPHN5c3RlbS1yZW1pbmRlcj5QZXJtaXNzaW9uIGVycm9yOiBge2RpcmVjdG9yeX1gIGlzIG5vdCB3aXRoaW4gdGhlIHdvcmtpbmcgZGlyZWN0b3J5IGB7Y3dkfWA8L3N5c3RlbS1yZW1pbmRlcj4iCisgICAgICAgIGRpcmVjdG9yeSA9IHJlc29sdmVkCisgICAgICAgIGlmIG5vdCBQYXRoKGRpcmVjdG9yeSkuaXNfZGlyKCk6CisgICAgICAgICAgICByZXR1cm4gZiI8c3lzdGVtLXJlbWluZGVyPkVycm9yOiBkaXJlY3RvcnkgYHtkaXJlY3Rvcnl9YCBkb2VzIG5vdCBleGlzdCBvciBpcyBub3QgYSBkaXJlY3RvcnkuPC9zeXN0ZW0tcmVtaW5kZXI+IgogCiAgICAgICAgIG91dHB1dCA9IHJ1bihkaXJlY3RvcnksIHBhdHRlcm4sIGN3ZD1jd2QpCiAKZGlmZiAtLWdpdCBhL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL2dyZXAucHkgYi9zcmMvZmFzdGNvbnRleHQvYWdlbnQvdG9vbC9ncmVwLnB5CmluZGV4IDRlZTE2MWYuLjRmYWNiMzAgMTAwNjQ0Ci0tLSBhL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL2dyZXAucHkKKysrIGIvc3JjL2Zhc3Rjb250ZXh0L2FnZW50L3Rvb2wvZ3JlcC5weQpAQCAtMiw3ICsyLDcgQEAgaW1wb3J0IGpzb24KIGZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAogCiBmcm9tIC50b29sIGltcG9ydCBUb29sCi1mcm9tIC51dGlscyBpbXBvcnQgUkdfUEFUSAorZnJvbSAudXRpbHMgaW1wb3J0IFJHX1BBVEgsIHJlc29sdmVfd2l0aGluX2N3ZAogCiAKIGNsYXNzIEdyZXBUb29sKFRvb2wpOgpAQCAtODIsOCArODIsMTAgQEAgY2xhc3MgR3JlcFRvb2woVG9vbCk6CiAgICAgICAgIGhlYWRfbGltaXQgPSBwYXJhbXMuZ2V0KCJoZWFkX2xpbWl0IikKICAgICAgICAgbXVsdGlsaW5lID0gcGFyYW1zLmdldCgibXVsdGlsaW5lIikKIAotICAgICAgICBpZiBub3QgUGF0aChwYXRoKS5yZXNvbHZlKCkuaXNfcmVsYXRpdmVfdG8oUGF0aChjd2QpLnJlc29sdmUoKSk6CisgICAgICAgIHJlc29sdmVkID0gcmVzb2x2ZV93aXRoaW5fY3dkKHBhdGgsIGN3ZCkKKyAgICAgICAgaWYgcmVzb2x2ZWQgaXMgTm9uZToKICAgICAgICAgICAgIHJldHVybiBmIjxzeXN0ZW0tcmVtaW5kZXI+UGVybWlzc2lvbiBlcnJvcjogYHtwYXRofWAgaXMgbm90IHdpdGhpbiB0aGUgd29ya2luZyBkaXJlY3RvcnkgYHtjd2R9YDwvc3lzdGVtLXJlbWluZGVyPiIKKyAgICAgICAgcGF0aCA9IHJlc29sdmVkCiAKICAgICAgICAgb3V0cHV0ID0gcnVuX3JnKAogICAgICAgICAgICAgUkdfUEFUSCwKZGlmZiAtLWdpdCBhL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL3JlYWQucHkgYi9zcmMvZmFzdGNvbnRleHQvYWdlbnQvdG9vbC9yZWFkLnB5CmluZGV4IGEwY2FhNzYuLjM3YThhMmUgMTAwNjQ0Ci0tLSBhL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL3JlYWQucHkKKysrIGIvc3JjL2Zhc3Rjb250ZXh0L2FnZW50L3Rvb2wvcmVhZC5weQpAQCAtNCw2ICs0LDcgQEAgZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCiBpbXBvcnQgYWlvZmlsZXMKIAogZnJvbSAudG9vbCBpbXBvcnQgVG9vbAorZnJvbSAudXRpbHMgaW1wb3J0IHJlc29sdmVfd2l0aGluX2N3ZAogCiBNQVhfTElORSA9IDIwMDAKIE1BWF9MSU5FX0xFTkdUSCA9IDIwMDAKQEAgLTQxLDggKzQyLDEwIEBAIGNsYXNzIFJlYWRUb29sKFRvb2wpOgogICAgICAgICAgICAgcmV0dXJuICI8c3lzdGVtLXJlbWluZGVyPkVycm9yOiBmaWxlIHBhdGggaXMgcmVxdWlyZWQ8L3N5c3RlbS1yZW1pbmRlcj4iCiAKICAgICAgICAgY3dkID0ga3dhcmdzLmdldCgiY3dkIiwgUGF0aC5jd2QoKS5hc19wb3NpeCgpKQotICAgICAgICBpZiBub3QgUGF0aChmaWxlX3BhdGgpLnJlc29sdmUoKS5pc19yZWxhdGl2ZV90byhQYXRoKGN3ZCkucmVzb2x2ZSgpKToKKyAgICAgICAgcmVzb2x2ZWQgPSByZXNvbHZlX3dpdGhpbl9jd2QoZmlsZV9wYXRoLCBjd2QpCisgICAgICAgIGlmIHJlc29sdmVkIGlzIE5vbmU6CiAgICAgICAgICAgICByZXR1cm4gZiI8c3lzdGVtLXJlbWluZGVyPlBlcm1pc3Npb24gZXJyb3I6IGB7ZmlsZV9wYXRofWAgaXMgbm90IHdpdGhpbiB0aGUgd29ya2luZyBkaXJlY3RvcnkgYHtjd2R9YDwvc3lzdGVtLXJlbWluZGVyPiIKKyAgICAgICAgZmlsZV9wYXRoID0gcmVzb2x2ZWQKIAogICAgICAgICBpZiBub3QgUGF0aChmaWxlX3BhdGgpLmV4aXN0cygpOgogICAgICAgICAgICAgcmV0dXJuIGYiPHN5c3RlbS1yZW1pbmRlcj5FcnJvcjoge2ZpbGVfcGF0aH0gZG9lcyBub3QgZXhpc3Q8L3N5c3RlbS1yZW1pbmRlcj4iCmRpZmYgLS1naXQgYS9zcmMvZmFzdGNvbnRleHQvYWdlbnQvdG9vbC91dGlscy5weSBiL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL3V0aWxzLnB5CmluZGV4IDhkZWFkZGIuLmU0MzVkZGUgMTAwNjQ0Ci0tLSBhL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL3V0aWxzLnB5CisrKyBiL3NyYy9mYXN0Y29udGV4dC9hZ2VudC90b29sL3V0aWxzLnB5CkBAIC0xLDYgKzEsNyBAQAogaW1wb3J0IG9zCiBpbXBvcnQgcGxhdGZvcm0KIGltcG9ydCBzaHV0aWwKK2Zyb20gcGF0aGxpYiBpbXBvcnQgUGF0aAogCiAKIGRlZiBfZmluZF9leGlzdGluZ19yZygpIC0+IHN0ciB8IE5vbmU6CkBAIC0xMiwzICsxMyw0MyBAQCBkZWYgX2ZpbmRfZXhpc3RpbmdfcmcoKSAtPiBzdHIgfCBOb25lOgogCiAKIFJHX1BBVEggPSBfZmluZF9leGlzdGluZ19yZygpCisKKworZGVmIHJlc29sdmVfd2l0aGluX2N3ZChwYXRoOiBzdHIsIGN3ZDogc3RyKSAtPiBzdHIgfCBOb25lOgorICAgICIiIlJlc29sdmUgYSBtb2RlbC1zdXBwbGllZCBwYXRoIHRvIGFuIGFic29sdXRlIHBhdGggaW5zaWRlIGBgY3dkYGAuCisKKyAgICBTbWFsbCBxdWFudGl6ZWQgZXhwbG9yZXJzIGZyZXF1ZW50bHkgZW1pdCByZXBvLXJvb3QtcmVsYXRpdmUgcGF0aHMgd3JpdHRlbgorICAgIHdpdGggYSBsZWFkaW5nIHNsYXNoIChlLmcuIGBgL2F1dG93aWtpYGAgb3IgYGAvPHdvcmtkaXItbmFtZT4vYXV0b3dpa2lgYCkKKyAgICByYXRoZXIgdGhhbiBwYXRocyByZWxhdGl2ZSB0byB0aGUgYWN0dWFsIHdvcmtpbmcgZGlyZWN0b3J5LiBJbnRlcnByZXQgdGhvc2UKKyAgICBhcyB3b3JrZGlyLXJlbGF0aXZlIGluc3RlYWQgb2YgcmVqZWN0aW5nIHRoZW0gYXMgIm91dHNpZGUgdGhlIHdvcmtzcGFjZSIuCisKKyAgICBSZXR1cm5zIHRoZSByZXNvbHZlZCBhYnNvbHV0ZSBwYXRoIChhcyBhIHN0cmluZykgd2hlbiBpdCBsYW5kcyBpbnNpZGUKKyAgICBgYGN3ZGBgLCBvciBgYE5vbmVgYCB3aGVuIHRoZSBwYXRoIGdlbnVpbmVseSBlc2NhcGVzIHRoZSB3b3Jrc3BhY2UuCisgICAgIiIiCisgICAgY3dkX3AgPSBQYXRoKGN3ZCkucmVzb2x2ZSgpCisgICAgc3RyaXBwZWQgPSBwYXRoLmxzdHJpcCgiLyIpCisgICAgcGFydHMgPSBbcCBmb3IgcCBpbiBzdHJpcHBlZC5zcGxpdCgiLyIpIGlmIHBdCisKKyAgICAjIENhbmRpZGF0ZSBpbnRlcnByZXRhdGlvbnMsIGluIHByaW9yaXR5IG9yZGVyLgorICAgIGNhbmRpZGF0ZXM6IGxpc3RbUGF0aF0gPSBbXQorICAgIGxpdGVyYWwgPSBQYXRoKHBhdGgpCisgICAgY2FuZGlkYXRlcy5hcHBlbmQobGl0ZXJhbCBpZiBsaXRlcmFsLmlzX2Fic29sdXRlKCkgZWxzZSBjd2RfcCAvIGxpdGVyYWwpCisgICAgIyBNb2RlbCBwcmVmaXhlZCB0aGUgd29ya2RpcidzIG93biBuYW1lOiAiL2F1dG93aWtpLXdjL2F1dG93aWtpIiAtPiAiPGN3ZD4vYXV0b3dpa2kiLgorICAgIGlmIHBhcnRzIGFuZCBwYXJ0c1swXSA9PSBjd2RfcC5uYW1lOgorICAgICAgICBjYW5kaWRhdGVzLmFwcGVuZChjd2RfcCAvICIvIi5qb2luKHBhcnRzWzE6XSkgaWYgcGFydHNbMTpdIGVsc2UgY3dkX3ApCisgICAgIyBMZWFkaW5nLXNsYXNoLWFzLXdvcmtkaXItcmVsYXRpdmU6ICIvYXV0b3dpa2kiIC0+ICI8Y3dkPi9hdXRvd2lraSIuCisgICAgY2FuZGlkYXRlcy5hcHBlbmQoY3dkX3AgLyBzdHJpcHBlZCkKKworICAgIGZpcnN0X2luc2lkZTogc3RyIHwgTm9uZSA9IE5vbmUKKyAgICBmb3IgY2FuZCBpbiBjYW5kaWRhdGVzOgorICAgICAgICByZXNvbHZlZCA9IGNhbmQucmVzb2x2ZSgpCisgICAgICAgIGlmIG5vdCByZXNvbHZlZC5pc19yZWxhdGl2ZV90byhjd2RfcCk6CisgICAgICAgICAgICBjb250aW51ZQorICAgICAgICBpZiBmaXJzdF9pbnNpZGUgaXMgTm9uZToKKyAgICAgICAgICAgIGZpcnN0X2luc2lkZSA9IHN0cihyZXNvbHZlZCkKKyAgICAgICAgIyBQcmVmZXIgYW4gaW50ZXJwcmV0YXRpb24gdGhhdCBhY3R1YWxseSBwb2ludHMgYXQgc29tZXRoaW5nLgorICAgICAgICBpZiByZXNvbHZlZC5leGlzdHMoKToKKyAgICAgICAgICAgIHJldHVybiBzdHIocmVzb2x2ZWQpCisKKyAgICAjIE5vdGhpbmcgZXhpc3RzLCBidXQgYSB3b3Jrc3BhY2UtcmVsYXRpdmUgcmVhZGluZyBpcyBhdmFpbGFibGUgLT4gYmVzdCBlZmZvcnQuCisgICAgcmV0dXJuIGZpcnN0X2luc2lkZQpkaWZmIC0tZ2l0IGEvc3JjL2Zhc3Rjb250ZXh0L2FnZW50L3V0aWxzLnB5IGIvc3JjL2Zhc3Rjb250ZXh0L2FnZW50L3V0aWxzLnB5CmluZGV4IGI0M2Y5MjEuLjQ0OTIyNzMgMTAwNjQ0Ci0tLSBhL3NyYy9mYXN0Y29udGV4dC9hZ2VudC91dGlscy5weQorKysgYi9zcmMvZmFzdGNvbnRleHQvYWdlbnQvdXRpbHMucHkKQEAgLTU0LDExICs1NCwxMyBAQCBkZWYgbG9hZF9zeXN0ZW1fcHJvbXB0KHdvcmtfZGlyOiBzdHIpIC0+IHN0cjoKIAogCiBkZWYgcGFyc2VfY2l0YXRpb25zKHRleHQ6IHN0cikgLT4gbGlzdDoKKyAgICAjIFByZWZlciB0aGUgY29udGVudCBpbnNpZGUgPGZpbmFsX2Fuc3dlcj4uLi48L2ZpbmFsX2Fuc3dlcj4sIGJ1dCBmYWxsIGJhY2sgdG8KKyAgICAjIHRoZSB3aG9sZSBtZXNzYWdlIHdoZW4gdGhlIG1vZGVsIGZvcmdvdCB0aGUgdGFncyAoY29tbW9uIHdpdGggc21hbGwgbW9kZWxzKS4KKyAgICAjIEFsd2F5cyByZXR1cm4gYSBsaXN0IHNvIGRvd25zdHJlYW0gZm9ybWF0dGluZyBuZXZlciBzZWVzIGFuIGluY29uc2lzdGVudCB0eXBlLgogICAgIGZpbmFsX2Fuc3dlciA9IHJlLnNlYXJjaChyIjxmaW5hbF9hbnN3ZXI+KC4qPyk8L2ZpbmFsX2Fuc3dlcj4iLCB0ZXh0LCByZS5ET1RBTEwpCi0gICAgaWYgZmluYWxfYW5zd2VyIGlzIE5vbmU6Ci0gICAgICAgIHJldHVybiB7ImZpbmFsX2Fuc3dlciI6IHRleHQuc3RyaXAoKSwgImNpdGF0aW9ucyI6IFtdfQorICAgIGJvZHkgPSBmaW5hbF9hbnN3ZXIuZ3JvdXAoMSkgaWYgZmluYWxfYW5zd2VyIGlzIG5vdCBOb25lIGVsc2UgdGV4dAogCi0gICAgZW50cmllcyA9IGZpbmFsX2Fuc3dlci5ncm91cCgxKS5zdHJpcCgpLnNwbGl0bGluZXMoKQorICAgIGVudHJpZXMgPSBib2R5LnN0cmlwKCkuc3BsaXRsaW5lcygpCiAKICAgICBlbnRyaWVzID0gW2UgZm9yIGUgaW4gZW50cmllcyBpZiBlLnN0cmlwKCldCiAKQEAgLTExMCw4ICsxMTIsMTEgQEAgZGVmIGZvcm1hdF9jaXRhdGlvbnMoY2l0YXRpb25zOiBsaXN0LCB2YWxpZGF0ZTogYm9vbCA9IFRydWUpIC0+IHN0cjoKIAogZGVmIGdldF9maW5hbF9hbnN3ZXIodGV4dDogc3RyKSAtPiBzdHI6CiAgICAgY2l0YXRpb25zID0gcGFyc2VfY2l0YXRpb25zKHRleHQpCi0gICAgZmluYWxfYW5zd2VyID0gZm9ybWF0X2NpdGF0aW9ucyhjaXRhdGlvbnMpCi0gICAgcmV0dXJuIGZpbmFsX2Fuc3dlcgorICAgIGlmIG5vdCBjaXRhdGlvbnM6CisgICAgICAgICMgTm8gcGFyc2VhYmxlIGZpbGU6bGluZSBjaXRhdGlvbnMg4oCUIHJldHVybiB0aGUgbW9kZWwncyByYXcgYW5zd2VyIGluc3RlYWQKKyAgICAgICAgIyBvZiBhbiBlbXB0eSAob3IgY3Jhc2hpbmcpIDxmaW5hbF9hbnN3ZXI+IGJsb2NrLgorICAgICAgICByZXR1cm4gdGV4dC5zdHJpcCgpCisgICAgcmV0dXJuIGZvcm1hdF9jaXRhdGlvbnMoY2l0YXRpb25zKQogCiAKIGlmIF9fbmFtZV9fID09ICJfX21haW5fXyI6Cg==
PATCH_B64

if git -C "$FC_DIR" apply --check "$PATCH_FILE" 2>/dev/null; then
  git -C "$FC_DIR" apply "$PATCH_FILE"
  say "Patches toegepast."
elif git -C "$FC_DIR" apply --reverse --check "$PATCH_FILE" 2>/dev/null; then
  say "Patches waren al toegepast — overslaan."
else
  warn "Patches lieten zich niet schoon toepassen (upstream gewijzigd?). FastContext werkt nog,"
  warn "maar zonder de pad-fix/citation-fix kunnen kleine modellen falen of crashen."
fi
rm -f "$PATCH_FILE"

# --- 4. deps installeren -----------------------------------------------------
say "Python-dependencies installeren (uv sync)..."
( cd "$FC_DIR" && uv sync )

# --- 5. env-config + commando ------------------------------------------------
ENV_FILE="$FC_DIR/beestjeai2.env"
cat > "$ENV_FILE" <<EOF
# FastContext -> Q4-model op beestjeai2 (llama.cpp)
export FC_BASE_URL="http://${FC_ENDPOINT}/v1/"
export FC_MODEL="${FC_MODEL}"
export FC_REASONING_EFFORT="none"
export FC_MAX_TOKENS=1536
export FC_TEMPERATURE=0.2
EOF
say "Env-config: $ENV_FILE"

mkdir -p "$BINDIR"
# 'fastcontext' = exact de naam die de skill aanroept: Bash(fastcontext *).
# Roept de venv-binary direct aan (geen PATH-recursie) met de endpoint-env erbij.
cat > "$BINDIR/fastcontext" <<EOF
#!/usr/bin/env bash
# FastContext-client: scout tegen het model op beestjeai2, vanuit de repo waarin je staat.
set -euo pipefail
source "$ENV_FILE"
exec "$FC_DIR/.venv/bin/fastcontext" "\$@"
EOF
chmod +x "$BINDIR/fastcontext"
ln -sf "$BINDIR/fastcontext" "$BINDIR/fc"   # korte alias
say "Commando geïnstalleerd: $BINDIR/fastcontext (+ alias 'fc')"
case ":$PATH:" in *":$BINDIR:"*) : ;; *) warn "Zet $BINDIR in je PATH:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc" ;; esac

# --- 5b. Skill installeren zodat de agent 'fastcontext' proactief inzet ------
# AGENT bepaalt de skills-map:
#   pi      -> ~/.pi/agent/skills/fastcontext/       (Mario Zechner's pi-coding-agent)
#   claude  -> ~/.claude/skills/fastcontext/         (Claude Code)
#   codex   -> ~/.codex/skills/fastcontext/          (Codex CLI)
#   auto    -> installeer voor elke runtime waarvan de config-map bestaat (default)
AGENT="${AGENT:-auto}"
SKILL_SRC="$FC_DIR/skills/fastcontext/SKILL.md"
_installed_skill=0
_install_skill_to(){ # $1 = skills-basismap
  mkdir -p "$1/fastcontext"
  cp "$SKILL_SRC" "$1/fastcontext/SKILL.md"
  say "Skill geïnstalleerd: $1/fastcontext/SKILL.md"
  _installed_skill=1
}
case "$AGENT" in
  pi)     _install_skill_to "$HOME/.pi/agent/skills" ;;
  claude) _install_skill_to "$HOME/.claude/skills" ;;
  codex)  _install_skill_to "$HOME/.codex/skills" ;;
  auto)
    [ -d "$HOME/.pi" ]     && _install_skill_to "$HOME/.pi/agent/skills"
    [ -d "$HOME/.claude" ] && _install_skill_to "$HOME/.claude/skills"
    [ -d "$HOME/.codex" ]  && _install_skill_to "$HOME/.codex/skills"
    ;;
  none) : ;;
  *) warn "Onbekende AGENT='$AGENT' (gebruik: pi|claude|codex|auto|none)" ;;
esac
if [ "$_installed_skill" = 0 ] && [ "$AGENT" != "none" ]; then
  warn "Skill niet geïnstalleerd (geen agent-config-map gevonden). Forceer bv. met:  AGENT=pi ./install-fastcontext-laptop.sh"
  warn "Of kopieer handmatig: $SKILL_SRC  ->  <skills-map>/fastcontext/SKILL.md"
fi

# --- 6. verbindingstest ------------------------------------------------------
say "Verbinding met beestjeai2 testen (http://${FC_ENDPOINT}) ..."
if curl -s -m 5 "http://${FC_ENDPOINT}/v1/models" | grep -q "$FC_MODEL"; then
  say "✅ Model '${FC_MODEL}' bereikbaar op beestjeai2."
else
  warn "Kan het model nog niet bereiken op ${FC_ENDPOINT}."
  warn "  - draait de llama-server op beestjeai2 op een NIET-lokaal adres (0.0.0.0)?"
  warn "  - zit je laptop op dezelfde Tailscale/LAN?  test:  curl http://${FC_ENDPOINT}/health"
  warn "  - ander endpoint?  FC_ENDPOINT=beestjeai2.local:8057 ./install-fastcontext-laptop.sh"
fi

cat <<EOF

------------------------------------------------------------------------------
Klaar. Gebruik:
    cd /pad/naar/een/repo
    fastcontext -q "Waar zit de authenticatie-logica?" --max-turns 12 --citation

Config aanpassen: $ENV_FILE
------------------------------------------------------------------------------
EOF
