# Public Release Checklist

Use this before pushing the repository to a public remote.

## Secrets

Keep these outside the repo:

- `Project/secrets/bard-local.env`
- service-account JSON keys
- API tokens for image or model providers
- downloaded credentials from Google Cloud
- generated local `.env` files

Run a quick text scan before publishing:

```powershell
rg -n -i "(api[_-]?key|secret|token|password|credential|private[_-]?key|client[_-]?secret|google_application_credentials|BEGIN .*PRIVATE KEY)"
```

The example files in `configs/` should contain placeholders only.

## Generated Files

Do not publish local run output, caches, or machine-specific tool state:

- `runs/`
- `outputs/`
- `data/audio/audio_private/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`
- `.codex/`
- `.agents/`
- `__pycache__/`
- `*.pyc`

These are ignored by `.gitignore`, but already tracked files still need to be removed from the Git
index before the first public push.

## Large Media

Check that every tracked audio file is intentional and has a license that allows redistribution.
The notes in [data/audio/README.md](../data/audio/README.md) list the sample sources that are already
documented.

```powershell
git ls-files data/audio
```

For private rehearsal recordings, keep them outside the repo or inside an ignored folder. Do not rely
on `.gitignore` for files that are already tracked.

## Git History

If unlicensed audio or credentials were ever committed to a branch that will become public, removing
the files in the latest commit is not enough. Rewrite the branch history before pushing publicly, then
force-push only to a remote where collaborators know the history is being replaced.

Use a history rewrite tool such as `git filter-repo` or BFG Repo-Cleaner, then verify:

```powershell
git log --all -- data/audio/audio_private
git log --all -- <old-private-audio-path>
```

Those commands should return no commits on the public branch.

## Final Smoke Test

From a clean checkout, the main README should be enough to reach a first run:

```powershell
python -m pip install -e ".[api,cloud]"
python -m bard_core --help
```
