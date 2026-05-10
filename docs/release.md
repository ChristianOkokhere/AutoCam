# Releasing AutoCam

The `publish` workflow handles everything once. These steps are the human
prerequisites — do them once, then every future release is a `git tag`
push.

## One-time setup

### 1. Claim the `autocam` name on PyPI

- Create / log into a PyPI account at <https://pypi.org/account/login/>.
- Open <https://pypi.org/manage/account/publishing/>.
- Under **"Add a new pending publisher"**, fill in:

| Field            | Value                          |
|------------------|---------------------------------|
| PyPI Project Name | `autocam`                       |
| Owner            | `ChristianOkokhere`             |
| Repository name  | `AutoCam`                       |
| Workflow name    | `publish.yml`                   |
| Environment name | `pypi`                          |

This authorises the GitHub Actions OIDC token to publish to that name
without storing an API key.

### 2. Create the `pypi` environment on the repo

- Go to <https://github.com/ChristianOkokhere/AutoCam/settings/environments>.
- New environment → **`pypi`**.
- (Optional) Add a required reviewer or a deployment branch rule so a
  human eyeballs every release.

### 3. Verify the test workflow is green on trunk

```bash
gh run list --workflow=test.yml --branch docs/initial-readme-and-plan --limit 1
```

If the latest run isn't green, fix the failure before tagging.

## Every release

```bash
# Bump the version in pyproject.toml AND src/autocam/__init__.py.
# Keep them in lock-step — the build smoke check imports __version__.

git add pyproject.toml src/autocam/__init__.py
git commit -m "chore: bump to v0.X.Y"
git tag -a v0.X.Y -m "v0.X.Y"
git push origin main v0.X.Y
```

The publish workflow runs automatically on a `v*.*.*` tag push.
You'll see it in <https://github.com/ChristianOkokhere/AutoCam/actions/workflows/publish.yml>.

When it lands, the package shows up at <https://pypi.org/project/autocam/>.

### Post-release check

```bash
# from a clean machine or a fresh venv:
uv tool install autocam==0.X.Y
create --version       # should print 0.X.Y
create --help
```

If anything is wrong, **yank the release** rather than overwrite it —
PyPI doesn't allow re-uploading the same version number:

```bash
# from <https://pypi.org/manage/project/autocam/release/0.X.Y/>
# → Options → Yank release
```

Then bump the patch version and retag.
