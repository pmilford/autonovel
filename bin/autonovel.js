#!/usr/bin/env node
// Thin wrapper that delegates to the Python `autonovel` CLI.
//
// The npm package ships the Python source under `src/`; the user
// installs that source into their Python environment (pipx is the
// recommended path) and this shim just forwards arguments. We do not
// auto-install the Python side because that would silently mutate the
// user's Python environment on first npx call, which is a surprise we
// don't want.

'use strict';

const { spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

function pickPython() {
  for (const candidate of ['python3', 'python']) {
    const probe = spawnSync(candidate, ['-c', 'import sys; sys.exit(0)']);
    if (probe.status === 0) return candidate;
  }
  return null;
}

function importable(python, module) {
  const probe = spawnSync(python, ['-c', `import ${module}`], {
    stdio: ['ignore', 'ignore', 'ignore'],
  });
  return probe.status === 0;
}

function fail(msg, code = 1) {
  process.stderr.write(`autonovel: ${msg}\n`);
  process.exit(code);
}

const python = pickPython();
if (!python) {
  fail(
    'Python ≥3.12 is required and was not found on $PATH.\n' +
      'Install Python, then run:\n' +
      '  pipx install autonovel\n' +
      'or, from a clone of the repo:\n' +
      '  pipx install /path/to/autonovel'
  );
}

if (!importable(python, 'autonovel')) {
  // Try to fall back to running from this package's bundled source —
  // useful for `npx autonovel ...` against a user that hasn't pipx-
  // installed yet. We add `<package_root>/src` to PYTHONPATH and
  // try once more.
  const pkgRoot = path.resolve(__dirname, '..');
  const bundledSrc = path.join(pkgRoot, 'src');
  if (fs.existsSync(path.join(bundledSrc, 'autonovel', '__init__.py'))) {
    const env = { ...process.env, PYTHONPATH: bundledSrc + path.delimiter + (process.env.PYTHONPATH || '') };
    const r = spawnSync(python, ['-m', 'autonovel.cli', ...process.argv.slice(2)], {
      stdio: 'inherit',
      env,
    });
    process.exit(r.status ?? 1);
  }
  fail(
    'The `autonovel` Python package is not installed in this Python.\n' +
      `Detected Python: ${python}\n` +
      'Run:\n' +
      '  pipx install autonovel\n' +
      'and re-run this command.'
  );
}

const r = spawnSync(python, ['-m', 'autonovel.cli', ...process.argv.slice(2)], {
  stdio: 'inherit',
});
process.exit(r.status ?? 1);
