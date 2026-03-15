# Contributing to claude-lark

Thanks for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/ysyecust/claude-lark.git
cd claude-lark
```

No dependencies needed — the project uses only Python stdlib.

## Running Tests

```bash
python3 -m pytest tests/ -v
```

## Guidelines

- **Zero dependencies** — only Python 3.8+ stdlib. Do not add pip packages.
- **Silent failures** — the hook must never block Claude Code. All errors should be caught and silently ignored.
- **Keep it simple** — this is a single-file tool. Avoid over-engineering.

## Submitting Changes

1. Fork the repo
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a Pull Request

## Reporting Issues

Open an issue on GitHub with:
- Your Python version (`python3 --version`)
- Your Claude Code version
- Steps to reproduce
- Expected vs actual behavior
