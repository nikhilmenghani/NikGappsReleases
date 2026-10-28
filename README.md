# NikGappsReleases

Public Android app APK releases for [NikGapps](https://github.com/nikhilmenghani/NikGapps).
This repository contains release automation and public changelogs, not the app source.

## Migration

1. Add `RELEASES_TOKEN` to **NikGapps** Actions secrets. It needs Contents read/write on **NikGappsReleases**.
2. Commit the source app's migration changes before building the next release. Keep the source repository public during the transition.
3. Increment `dev.txt` or `release.txt` as usual. The source workflow builds once and uploads the identical signed APK to both repositories. Do not also run the public workflow for that same release.
4. Existing installations find the migration APK through NikGapps. Updated installations check NikGapps first, then this repository when NikGapps has no newer version or is unavailable.
5. After sufficient migration releases, use the workflows here and turn off **mirror_source**. NikGapps can then become private; older clients without the migration update cannot discover releases here.

No version increment or release is triggered by the initial setup commit.

## Build from this repository

Run **Build development release from source** or **Build stable release from source** under Actions. Choose a trusted source branch, tag, or commit. Development versions come from the source's `dev.txt`; stable versions are supplied explicitly (for example `0.81`) using the existing stable version-code scheme.

Configure these Actions secrets here first:

| Secret | Purpose |
| --- | --- |
| `SOURCE_REPO_TOKEN` | Contents read on NikGapps for private checkout; Contents write there while `mirror_source` is enabled |
| `KEYSTORE` | The exact existing signing keystore, base64 encoded |
| `KEYSTORE_PASSWORD` | The existing keystore/key password |
| `NIKGAPPS_CLIENT_ID` | Existing GitHub sign-in client ID |
| `POSTHOG_API_KEY`, `POSTHOG_HOST` | Existing analytics configuration |

Public publishing uses this repository's automatic `GITHUB_TOKEN`. Preserve the original signing key, application IDs, filenames, tags, and monotonically increasing version codes so installed apps accept updates. Source-repository secrets are not inherited here. Supply secrets through GitHub Settings, never committed files.

Only manual dispatch is enabled here. Public pull requests never run the private checkout or receive release secrets. A release can expose the APK and CHANGELOG.md publicly even when its source is private; run only trusted source revisions.

The app changelog is also maintained here for access after the source repository becomes private. Release workflows synchronize it after publication. Test the first dual-published release and in-app download on both channels before changing visibility.
