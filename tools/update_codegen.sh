#!/usr/bin/env bash
# Download the CODEGEN executables from a stepss-Codegen GitHub release and
# copy them into src/cg_studio/bin/ for bundling in the wheel.
#
# Usage: tools/update_codegen.sh <tag>        e.g. tools/update_codegen.sh v5.3
#
# Requires the GitHub CLI (gh) authenticated with access to SPS-L/stepss-Codegen,
# which is a private repository. The release automation passes STEPSS_TOKEN.
#
# Records what it fetched in src/cg_studio/_bundled.py, which is also what
# tools/bump_version.sh derives the wheel version from. Review and commit the
# updated binaries afterwards:
#   git add src/cg_studio/bin src/cg_studio/_bundled.py
#   git commit -m "Bundle CODEGEN <tag>"
#
# Companion to tools/bump_version.sh; the release automation calls both.
#
# CG_STUDIO_BIN_DIR overrides the destination, for tests.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $0 <codegen-release-tag> (e.g. v5.3)" >&2
    exit 2
fi
TAG="$1"
REPO="SPS-L/stepss-Codegen"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN_DIR="${CG_STUDIO_BIN_DIR:-$ROOT/src/cg_studio/bin}"
BUNDLED="$ROOT/src/cg_studio/_bundled.py"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "Downloading CODEGEN $TAG executables from $REPO ..."
gh release download "$TAG" --repo "$REPO" \
    --pattern "codegen-*-$TAG.*" --dir "$WORK_DIR"

# The Linux and macOS archives both contain a member named CODEGEN, so each is
# unpacked into its own directory rather than a shared one. A flat extraction
# would silently leave one platform holding the other's executable, and the two
# are not distinguishable by name, size or the `file` output a reviewer skims.
#
# asset:dest:member, where dest matches the keys resolve_codegen() looks up.
for spec in \
    "codegen-linux-x86_64-$TAG.tar.gz:lin:CODEGEN" \
    "codegen-windows-x86_64-$TAG.zip:win:CODEGEN.exe" \
    "codegen-macos-arm64-$TAG.tar.gz:mac:CODEGEN"
do
    asset="${spec%%:*}"; rest="${spec#*:}"
    dest="${rest%%:*}"; member="${rest#*:}"
    archive="$WORK_DIR/$asset"

    # Never recovered from by picking some other file: in a pipeline that
    # publishes to PyPI without review, silently bundling a different binary is
    # the one failure that reaches users as a wrong executable.
    [ -f "$archive" ] || { echo "FAIL: CODEGEN $TAG has no $asset" >&2; exit 1; }

    mkdir -p "$WORK_DIR/x/$dest" "$BIN_DIR/$dest"
    case "$asset" in
        *.zip)    unzip -q "$archive" -d "$WORK_DIR/x/$dest" ;;
        *.tar.gz) tar -xzf "$archive" -C "$WORK_DIR/x/$dest" ;;
    esac

    [ -f "$WORK_DIR/x/$dest/$member" ] || {
        echo "FAIL: $asset does not contain $member" >&2; exit 1; }

    # 755, not 644: this is the one payload in the wheel that gets executed.
    # A wheel carries the mode bit in the zip entry and pip restores it, so
    # getting it right here is what makes the installed binary runnable.
    # config.resolve_codegen() re-applies it at runtime as a backstop.
    install -m 755 "$WORK_DIR/x/$dest/$member"       "$BIN_DIR/$dest/$member"
    install -m 644 "$WORK_DIR/x/$dest/BUILDINFO.txt" "$BIN_DIR/$dest/BUILDINFO.txt"
done

# One copy: all three archives carry the same Academic Public License, and it
# is the licence of the executables rather than of this package.
install -m 644 "$WORK_DIR/x/lin/LICENSE" "$BIN_DIR/LICENSE-CODEGEN"

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

CODEGEN_VERSION = "$TAG"
EOF

echo
echo "Updated $BIN_DIR:"
find "$BIN_DIR" -type f -printf '%M  %8s  %P\n' | sort -k3
echo
cat "$BUNDLED"
echo "Done. Review the changes and commit, e.g.:"
echo "  git add src/cg_studio/bin src/cg_studio/_bundled.py"
echo "  git commit -m \"Bundle CODEGEN $TAG\""
