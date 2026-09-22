#!/bin/sh
# Installs Tidy into ./tidy (override with TIDY_DIR) and runs its tests. Touches nothing outside that folder and
# never asks for or reads credentials. Usage: curl -fsSL https://raw.githubusercontent.com/abhibansal60/tidy/main/install.sh | sh
set -eu

REPO="${TIDY_REPO:-https://github.com/abhibansal60/tidy}"
DIR="${TIDY_DIR:-tidy}"

for tool in git python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing required tool: $tool" >&2; exit 1; }
done
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" ||
  { echo "Tidy needs Python 3.11 or newer; found $(python3 -V 2>&1)." >&2; exit 1; }

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"
python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -c requirements.txt -e .
.venv/bin/python -m unittest discover -s tests -q

cat <<MSG

Tidy is installed in $(pwd).
Next: .venv/bin/tidy init --email you@gmail.com --client-secrets PATH --key-stdin, then .venv/bin/tidy doctor.
The simpler install is: pipx install tidy-ai. Setup guide: docs/agent-setup.md
MSG
