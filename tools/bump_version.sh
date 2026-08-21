#!/usr/bin/env bash
# Compute the next stepss-cg-studio version from the bundled CODEGEN release.
#
#   bump_version.sh codegen <upstream-tag>
#   bump_version.sh manual
#
# The version is <codegen X.Y>.<counter>, so the leading two components always
# name the CODEGEN executables bundled in the wheel:
#
#   CODEGEN v5.3 published        -> 5.3.0    (first wheel on this generator)
#   python-only release after it  -> 5.3.1
#   another python-only release   -> 5.3.2
#   CODEGEN v5.4 published        -> 5.4.0    (sequence restarts)
#
# Like stepss-python-ui's tools/bump_version.sh, the counter is derived from the
# tags that already exist rather than from a stored number, so there is nothing
# to drift out of step: a CODEGEN bump restarts the sequence on its own, because
# no tag for the new base exists yet. Re-running a failed release recomputes the
# same value, and a tag created by hand is taken into account for free.
#
# `codegen <tag>` rewrites src/cg_studio/_bundled.py so it records that tag --
# tools/update_codegen.sh has normally already done so, and this is what makes
# the two agree when it has not. `manual` changes it neither way, so a
# python-only release ships whatever generator main already bundles.
#
# Prints the new version (no 'v' prefix) on stdout; the release workflow reads
# that.
#
# CG_STUDIO_ROOT overrides the repository root, and CG_STUDIO_TAGS overrides the
# tag list (newline-separated), both for tests.
set -u

usage() {
    echo "usage: $0 codegen <upstream-tag>" >&2
    echo "       $0 manual" >&2
    exit 2
}

[ $# -ge 1 ] || usage
SOURCE="$1"
case "$SOURCE" in
    codegen) [ $# -eq 2 ] || usage; TAG="$2" ;;
    manual)  [ $# -eq 1 ] || usage; TAG="" ;;
    *)       usage ;;
esac

ROOT="${CG_STUDIO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
INIT="$ROOT/src/cg_studio/__init__.py"
BUNDLED="$ROOT/src/cg_studio/_bundled.py"

[ -f "$INIT" ] || { echo "FAIL: not found: $INIT" >&2; exit 1; }

read_assign() {  # read_assign <file> <name>
    [ -f "$1" ] || return 0
    sed -n "s/^$2[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'].*/\1/p" "$1" | head -n1
}

CUR="$(read_assign "$INIT" __version__)"
[ -n "$CUR" ] || { echo "FAIL: __version__ not found in $INIT" >&2; exit 1; }

CODEGEN_VER="$(read_assign "$BUNDLED" CODEGEN_VERSION)"
if [ "$SOURCE" = "codegen" ]; then
    CODEGEN_VER="$TAG"
fi
[ -n "$CODEGEN_VER" ] || { echo "FAIL: no CODEGEN_VERSION to carry forward" >&2; exit 1; }

if [ -n "${CG_STUDIO_TAGS+x}" ]; then
    TAGS="$CG_STUDIO_TAGS"
else
    TAGS="$(git -C "$ROOT" tag --list 2>/dev/null)" || TAGS=""
fi

NEW="$(CODEGEN_VER="$CODEGEN_VER" TAGS="$TAGS" python3 - <<'PYEOF'
import os, re, sys

raw = os.environ["CODEGEN_VER"].lstrip("vV").strip()
if not re.fullmatch(r"[0-9]+(\.[0-9]+)*", raw):
    sys.exit("FAIL: CODEGEN_VERSION %r is not a numeric version" % raw)

# The base is the first two components. CODEGEN is X.Y from v5.3 onwards and
# its release workflow enforces that, so this is normally the whole string;
# taking a prefix rather than requiring one keeps the older X.Y.Z releases
# (v5.1.0, v5.2.0) usable as a base instead of producing a four-component
# wheel version nobody asked for.
parts = raw.split(".")
if len(parts) < 2:
    sys.exit("FAIL: CODEGEN_VERSION %r has no minor component" % raw)
base = "%s.%s" % (parts[0], parts[1])

tags = set(os.environ["TAGS"].split())
counters = [
    int(m.group(1))
    for m in (re.fullmatch(r"v%s\.([0-9]+)" % re.escape(base), t) for t in tags)
    if m
]

# .0 is the first wheel on a given generator, whatever triggered it. Unlike
# stepss-python-ui, which uses a bare base for the first release, the counter is
# always written out: PEP 440 normalises 5.3 and 5.3.0 to the same version, so a
# bare base would look like a distinct release and resolve to an existing one.
print("%s.%d" % (base, max(counters) + 1 if counters else 0))
PYEOF
)" || exit 1
[ -n "$NEW" ] || { echo "FAIL: could not compute the next version" >&2; exit 1; }

# Rewrite __version__ in place. Anchored to the start of the line so a
# docstring mentioning __version__ cannot be hit.
python3 - "$INIT" "$CUR" "$NEW" <<'PYEOF'
import re, sys
path, cur, new = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(path, encoding='utf-8').read()
out, n = re.subn(r"(?m)^__version__\s*=\s*['\"]%s['\"]" % re.escape(cur),
                 '__version__ = "%s"' % new, src)
if n != 1:
    sys.exit("FAIL: expected exactly one __version__ assignment, found %d" % n)
open(path, 'w', encoding='utf-8').write(out)
PYEOF
REWRITE_RC=$?
# Must abort here, before _bundled.py is touched: a failed rewrite must leave no
# partial mutation, or CI would tag and publish a version that was never
# actually written to the package.
[ "$REWRITE_RC" -eq 0 ] || exit 1

if [ "$SOURCE" = "codegen" ]; then
    cat > "$BUNDLED" <<EOF
"""The CODEGEN release bundled in this wheel.

Written by tools/update_codegen.sh, which the release automation invokes when
stepss-Codegen publishes. Do not edit by hand: a manual edit is silently
overwritten by the next sync, and it would then disagree with the executables
actually sitting in cg_studio/bin/.

CODEGEN_VERSION is also what the package version is built from, so the leading
two components of __version__ always name the generator bundled here. See
tools/bump_version.sh.
"""

CODEGEN_VERSION = "$CODEGEN_VER"
EOF
fi

echo "$NEW"
