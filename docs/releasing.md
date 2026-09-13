# Releases

The version in `pyproject.toml` is the single version source.
Each release tag identifies the tested commit on the public `main` branch.
Release notes describe only the behavior available in that version.

1. Update the version and release notes.
2. Run the development commands in README.md.
3. Build and smoke-test both distributions:

```sh
uv run python scripts/release.py build --tag v0.2.0
```

4. Commit the release to `main` through normal review.
5. Create the matching tag and publish a GitHub release.

The release workflow runs tests, lint, type validation, and installed-distribution smoke tests before publication.
The publish job receives the resulting artifacts and publishes those exact files.
Its `pypi` environment uses PyPI Trusted Publishing. No permanent PyPI token is required.
