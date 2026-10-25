# Publishing the Warm Winter SDKs

This repository is the source for the Python and npm packages named `warmwinter`.
The existing [.github/workflows/publish.yml](.github/workflows/publish.yml) owns
registry publishing. A main merge does not publish either package.

## Prepare and verify the candidate

1. Set one reviewed version in `python/pyproject.toml`, Python `__version__`,
   `typescript/package.json`, the package-lock root/package entry, and TypeScript
   `VERSION`. Keep version assertions in the existing tests aligned.
2. From `python/`, run `python -m unittest discover -v`, then `python -m build`.
   Verify the built wheel and source archive contain the intended version and
   client methods. The contract tests use synthetic transport, not live keys.
3. From `typescript/`, run `npm ci`, `npm test`, then
   `npm pack --ignore-scripts`. Test the actual tarball's JavaScript and types;
   the archive should contain only the intended SDK distribution and metadata.
4. Record the exact reviewed source commit and artifact hashes. The ordinary
   release workflow rebuilds packages; locally tested archives are verification
   evidence, not proof of the bytes it will upload.

## Publish only the accepted version and source

Publishing a GitHub Release for a reviewed version tag (for example `v0.3.0`)
triggers **both** registry jobs. The existing workflow checks out the tag, tests
and builds the clients, then uses PyPI trusted publishing and npm trusted
publishing/provenance. It does not need a new token in source or a local login.
Source inspection alone does not verify current registry publisher configuration.

Creating a published release is the upload boundary: obtain owner authorization
for the exact version and source before publishing it. Do not dispatch the
workflow merely to test it. Its manual-dispatch path runs the **npm job only**;
it is a separately authorized recovery route, not the normal two-registry release.

After upload, read back both registries' versions and artifact digests, inspect
the released methods, and test the downloaded distributions. Check an uncertain
result before any retry: published versions are immutable and the two registry
jobs can finish independently. A source merge or green local test is not a
published-package receipt.

## 0.3.0 scope

Adds native consultation discovery, queue-pressure reading and self-reported
usefulness feedback in both clients. Existing Gate methods, grant/revocation
requirements, advisory boundaries and unknown uncertainty remain intact. The
backend-coupled contextual extensions are not part of this release. No automatic
cross-repository synchronization, new dependencies or deployment changes follow.
