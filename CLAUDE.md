# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository is currently an empty scaffold. It contains no source code yet — only dependency manifests and a stub README. When the first feature lands, update this file with the real architecture, commands, and conventions.

## Declared dependencies

Two ecosystems are declared but neither has any code wired up yet:

- **Node.js** (`package.json`): depends on `express` ^5.2.1. `main` is set to `index.js`, but that file does not exist. The `test` script is the npm default stub (`echo "Error: no test specified" && exit 1`) — there is no real test runner configured.
- **Python** (`requirements.txt`): declares `flask`. No Python source, virtualenv config, or entry point exists.

Before adding code, decide which stack is actually intended (or whether both are needed) and remove the unused manifest. Do not assume a build/test/lint command exists — none are configured. If you add one, document it here.

## Repository

- GitHub: `paskercrew/my-project`
- GitHub MCP tools in this environment are restricted to that repo only.

Push to the development branch specified in the session prompt (do not push directly to `main`), and open PRs as drafts.

