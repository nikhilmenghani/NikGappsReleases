# Publishing NikGapps

Releases and APK assets are published only in NikGappsReleases. The NikGapps repository supplies the app source.

1. Commit and push the app changes and changelog to NikGapps. Wait for Android verification to pass and verify affected behavior on a device.
2. Set `source.txt` to the full verified NikGapps commit SHA. Increment `dev.txt` (three components) and/or `release.txt` (two components), with matching changelog entries in the source.
3. Commit and push these controls. Changing a version file builds its channel; changing `source.txt` rebuilds both channels from the exact source revision, including when the version stays the same.
4. Both workflows validate the changelog, run unit tests and debug/release lint, build the signed APK, and verify its signing certificate before publishing. Any failed verification blocks publication.

Manual workflow runs can override the source revision through `source_ref`; the same verification gates apply. Existing release assets are replaced on a rebuild of the same version.
