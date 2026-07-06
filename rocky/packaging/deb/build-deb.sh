#!/bin/sh
# Build a rocky .deb from this source tree. Run on a Debian/Ubuntu host with dpkg-deb.
#
#   cd rocky/packaging/deb && ./build-deb.sh
#
# Output: rocky_<version>_all.deb in this directory. Install with:
#   sudo apt install ./rocky_1.0.0_all.deb
set -eu

VERSION="1.0.0"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROCKY_SRC="$(cd "$HERE/../.." && pwd)"   # the rocky/ directory
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Package layout: files under /usr/lib/rocky, rockyctl linked to /usr/bin by postinst.
install -d "$STAGE/usr/lib/rocky"
for f in agent_profile.md action_schema.json policy_rules.md capabilities.yaml \
         tool_registry.yaml memory_schema.sql policy.py executor.py memory.py \
         audit.py rockyctl rocky.conf.example.json README.md; do
    install -m 0644 "$ROCKY_SRC/$f" "$STAGE/usr/lib/rocky/$f"
done
chmod 0755 "$STAGE/usr/lib/rocky/rockyctl"

# Store the database under the user's home, not the read-only package path.
sed -i 's#os.path.join(HERE, "rocky.db")#os.path.expanduser("~/.local/share/rocky/rocky.db")#' \
    "$STAGE/usr/lib/rocky/memory.py" 2>/dev/null || true

install -d "$STAGE/DEBIAN"
install -m 0644 "$HERE/control" "$STAGE/DEBIAN/control"
sed -i "s/^Version: .*/Version: $VERSION/" "$STAGE/DEBIAN/control"
install -m 0755 "$HERE/postinst" "$STAGE/DEBIAN/postinst"

OUT="$HERE/rocky_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT"
echo "built $OUT"
