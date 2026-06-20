# Publishing the Warm Winter SDKs

Both packages are publish-ready: name `warmwinter` is free on PyPI and npm,
metadata + MIT LICENSE are in place, and both build + validate clean. You only
need to run the final upload with your own credentials (Claude can't — no tokens).

The package name is the same on both registries: **`warmwinter`** →
`pip install warmwinter` and `npm install warmwinter`.

---

## 1. Python → PyPI

**One-time:** create a PyPI account, then a project-scoped or account API token at
https://pypi.org/manage/account/token/ (username is literally `__token__`).

```bash
cd python
python -m build                 # builds dist/*.whl + dist/*.tar.gz (already done)
python -m twine check dist/*    # must say PASSED (it does)
python -m twine upload dist/*   # prompts: user = __token__ , password = pypi-...
```

Verify: `pip install warmwinter` in a clean venv, then `python -c "import warmwinter; print(warmwinter.__version__)"`.

> Optional dry run first: `twine upload --repository testpypi dist/*` (needs a
> separate TestPyPI token), then `pip install -i https://test.pypi.org/simple/ warmwinter`.

## 2. TypeScript / JavaScript → npm

**One-time:** create an npmjs.com account; if 2FA is on, have your authenticator ready.

```bash
cd typescript
npm run build                   # tsc → dist/ (already done)
npm pack --dry-run              # sanity-check the 5 files that will ship
npm login                       # browser/2FA
npm publish --access public     # --access public is required for an unscoped name
```

Verify: `npm install warmwinter` in a scratch dir, then `node -e "import('warmwinter').then(m=>console.log(m.VERSION))"`.

---

## 3. After the first publish (do once)

- **Update the product site's quickstart copy** to lead with `pip install warmwinter` /
  `npm install warmwinter` instead of "grab the files." Do this only *after* publishing,
  so the live site never tells people to install something that isn't there yet.
- The READMEs already say `pip install` / `npm install` — no change needed.

## 4. Cutting a new version later

1. Bump `version` in `python/pyproject.toml` AND `typescript/package.json`
   (keep them in lockstep) and `__version__` / `VERSION` in the source files.
2. Rebuild (`python -m build`, `npm run build`) and re-run the upload steps above.
   PyPI and npm both reject re-uploading an existing version — always bump.

## Notes

- **License is MIT** (the client SDK only — the gate service stays commercial). If
  you'd rather keep the client proprietary, change `license` in both manifests and
  the `LICENSE` files BEFORE the first publish; it's hard to walk back afterward.
- Both SDKs are zero-dependency (stdlib `urllib` / built-in `fetch`), so there's no
  supply-chain surface to audit — a selling point worth keeping.
