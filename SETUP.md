# Chess.com animated replay for kirlyr profile

This is a **real looping SVG replay** of the most recent **completed public Chess.com game** played by `kirlur`, NOT a recent-matches card and NOT a live in-progress game feed.

The generated SVG has moving pieces and move-by-move frames. It plays in supported web browsers when embedded as an image in GitHub README. A static image viewer may show only the first frame.

## Install in GitHub profile repository `kirlyr/kirlyr`

1. Clone your **profile repository** (`https://github.com/kirlyr/kirlyr`), **not** AI-Orchestrator.
2. Copy the `.github/`, `scripts/`, and `assets/` directories from this package to the profile repository. Keep its existing README; **do not overwrite** it unless you prefer `README_PROFILE_EXAMPLE.md`.
3. Copy the full contents of `README_SECTION.md` to the END of the existing `README.md`, removing the old Repobeats section. The two `<!-- chess-replay:... -->` marker lines are IMPORTANT; the script updates only that block when a new game appears.
4. Commit and push these files to `main`.
5. Open https://github.com/kirlyr/kirlyr/actions/workflows/chess-replay.yml, select **Run workflow**, and run it once.
6. Verify that the job succeeds and that `assets/chess/last-game.svg` is updated. Refresh https://github.com/kirlyr.

The included `last-game.svg` and `.json` are **DEMO DATA** (with a visible demo label) for verifying the graphics while the first Action run is pending. The first successful Action run replaces them with `kirlur`'s latest completed game.

No Chess.com credentials or token are required for public games.

## Suggested PowerShell commands (from your profile repository)

```powershell
# After extracting this package into the profile repository folder:
git status --short
# Ensure you only stage files you intend to add.
git add README.md .github/workflows/chess-replay.yml scripts/chess_replay.py assets/chess/last-game.svg assets/chess/last-game.json
git diff --cached --check
git diff --cached --stat
git commit -m "feat(profile): animate latest Chess.com game in README"
git push origin main
```

## Test locally

```powershell
py -3 -m pip install python-chess==1.999
py -3 scripts/chess_replay.py --demo
# This overwrites the SVG with a demo, so run the real fetch before committing:
py -3 scripts/chess_replay.py
```

`--demo` works without any dependencies and without Internet access. If your environment cannot access Chess.com, let GitHub Actions fetch the actual game instead.

## Notes

- Chess.com archive API is for completed games, not real-time in-progress games. GitHub scheduled Actions may run late; Chess.com API data is cached.
- GitHub or local preview tools that don't support SVG animations may display only the initial board. The HTML/browser-supported SVG CSS replay was validated separately on a demo game.
- If the API fails, the Action should fail rather than overwrite the last working replay with fake data.
- Playing as Black flips board orientation.
- The code deliberately avoids copying Chess.com-specific piece art or proprietary board styles.
