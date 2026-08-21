"""The CODEGEN release bundled in this wheel.

Written by tools/update_codegen.sh, which the release automation invokes when
stepss-Codegen publishes. Do not edit by hand: a manual edit is silently
overwritten by the next sync, and it would then disagree with the executables
actually sitting in cg_studio/bin/.

CODEGEN_VERSION is also what the package version is built from, so the leading
two components of __version__ always name the generator bundled here. See
tools/bump_version.sh.
"""

CODEGEN_VERSION = "v5.3"
