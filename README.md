# NikGappsReleases

Public Android app APK releases and changelogs for [NikGapps](https://github.com/nikhilmenghani/NikGapps).

## Release process

This repository's `dev.txt` and `release.txt` are the only release version controls. The source repository contains app code and `CHANGELOG.md`, but no version files or release workflows.

1. Commit and push code and release notes to NikGapps.
2. Include an exact heading such as `## 0.80.22` for development or `## 0.81` for stable, with at least one change beneath it.
3. Increment the matching version file here on `main`. That file's value is the exact version to publish.
4. The corresponding workflow clones the source, validates the changelog before building/signing, builds once, publishes the same signed APK to both repositories, and synchronizes the public changelog.

Missing, empty, placeholder-only, or duplicate matching changelog sections fail the build before publication. After fixing and pushing source notes, start a new manual run for the same public version; no extra version increment is needed.

You can also run either workflow manually and select a trusted source branch, tag, or commit. Manual runs read the same public version files. Both manual runs and version-file pushes publish the same APK to **NikGappsReleases and NikGapps**, replacing existing assets with matching names. If either publication fails, the workflow fails; run a new manual build after resolving the failure to synchronize both copies.

To replace an existing development APK without changing its version, start a **new manual run** of `Build development release from source` using workflow branch `main`, keep `dev.txt` at that version, and set `source_ref` to the original source tag or commit (for example, `dev-v0.80.21`). This uses the current workflow/signing checks with the original app source. Re-running an older workflow run uses that run's workflow revision and may omit later fixes. Replacing an APK at the same version does not notify users who already have that version installed; increment the version when a new update notification is needed.

NikGappsReleases checks out the NikGapps source and builds it directly; it does not dispatch another release workflow in NikGapps. Publishing the migration copy there does not perform a second build. No source-repository release workflow or source version file is required for this flow.

Do not start multiple builds for the same version. The app prefers updates in NikGapps and falls back here when no newer source release is available or the source repository cannot be reached. Older clients without fallback support still need a source-repository migration release before that repository becomes private.

## Required Actions secrets

| Secret | Purpose |
| --- | --- |
| `AUTH` | Token with Contents read/write on both repositories, including access to private NikGapps |
| `KEYSTORE` | The exact existing signing keystore, base64 encoded |
| `KEYSTORE_PASSWORD` | Existing signing keystore/key password |
| `NIKGAPPS_CLIENT_ID` | GitHub sign-in client ID |
| `POSTHOG_API_KEY`, `POSTHOG_HOST` | Analytics configuration |

Configure secrets here separately; source repository secrets are not shared automatically. Private source checkout, publication and changelog synchronization use `AUTH`.

Preserve signing keys, application IDs and artifact names; increase version codes with each release so installed apps accept updates. Development versions use `major.minor.patch`; stable versions use `major.minor`, retaining the existing code schemes.

Only version-file pushes to `main` and manual dispatch build releases. Public pull requests do not run the private checkout or receive release credentials. Publishing makes the APK and changelog public, not the source files.

## Development APK signing

After Gradle builds the development APK, the workflow re-signs it with Android Build Tools 36.1.0 and the existing release key before publishing. It verifies the pinned release certificate, v2 signature, every APK entry and the compressed entry bytes. Code, permissions, package/version information and in-app updates must remain unchanged. Verification failures stop publication; both repositories receive the same verified output.

This follows the signing procedure tested on OnePlus with the published 0.80.21 APK. The original was blocked by Play Protect; the re-signed APK passed and updated the existing app while retaining its files and preferences. It does not identify Google's internal classification reason or guarantee future scan results. Play Protect remains enabled; no warnings are bypassed. Stable release signing is unchanged.

The signing helper takes passwords through environment variables, leaves the original Gradle APK intact, and records public certificate and APK hashes in the job log. The temporary decoded keystore is removed even if a later step fails. The expected certificate fingerprint is public signing identity, not a credential; changing it requires an intentional signing-key migration.

Run the release-helper checks locally with `python3 -m unittest discover -s .github/scripts -p 'test_*.py'`.
