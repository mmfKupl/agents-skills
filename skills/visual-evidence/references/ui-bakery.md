# UI Bakery

Load this reference only after repository evidence identifies the UI Bakery monorepo.
It replaces the Screenshot Evidence section of `$develop-please`'s
`references/validation.md`; the rest of `$develop-please` still owns the Linear report and
the PR. Capture once the PR Hetzner preview is Ready, or on a local stand before one exists.

## Visual Evidence

What to show:

- walk each main scenario from the ticket by hand and record a video, with screenshots
  of its key states; for API, MCP, or agent changes, add the request and response or the
  agent conversation;
- capture a before screenshot from `dev`, `next`, or the closest available baseline
  preview when the change alters something that existed;
- prefer same viewport, data, account, route, and UI state for before/after;
- for trivial copy, icon-only, or tiny layout changes, record why evidence adds little
  value instead of forcing it.

How to capture on the preview:

- Use a disposable copy of the PR head commit, never the task worktree, and remove it
  when done. It is a disposable worktree, or, in a session that cannot make one, an
  export of the commit: `git archive --output=<file> HEAD front
  .github/workflows/preview-hetzner`, unpacked into a temporary folder. Export the whole
  `front`: with `front/projects/e2e` alone the run fails on imports such as
  `projects/e2e/fixtures/base`.
- Install the copy's own dependencies: `cd front && npm ci`, adding
  `--engine-strict=false` when only the local Node patch version differs, then
  `npx playwright install chromium`. Another checkout's `node_modules` can be weeks old.
  A link to `front/node_modules` of the task worktree will do instead when that was
  installed at the same commit.
- Write a scratch spec under `front/projects/e2e/tests/<scratch>/` on
  `baseAuthorizedTest`, which registers a new organization user on the preview, and the
  existing page objects. Set `video: 'on'`, `ignoreHTTPSErrors: true`, and
  `launchOptions: { slowMo: 250 }` with `test.use`, and log the API responses the
  scenario depends on. Never commit the spec.
- Run it from `front` with `E2E_BASE_URL=<preview URL>`,
  `NODE_EXTRA_CA_CERTS=../.github/workflows/preview-hetzner/PREVIEW_CA_CERT.crt`, and
  `npx playwright test --config=projects/e2e/playwright.config.ts --workers=1 --output=<temporary directory> <spec>`.

Storybook:

- The preview serves one Storybook per project under `https://storybook.<preview host>/`,
  for example `/bakery/` and `/workbench/`. Read story IDs from
  `https://storybook.<preview host>/<project>/index.json` and link each story as
  `https://storybook.<preview host>/<project>/?path=/story/<id>`.
- Post them as a Storybook comment of its own on the Linear issue, before the final
  report, with what to look at or click for each story. The final report links to that
  comment and does not repeat the list, in Details or anywhere else.

Where to post:

- upload the videos and screenshots to Linear and put them in the final Linear report, each
  video on its own `▶ Video` line, and API logs and details in a collapsible block; link
  it from the PR;
- do not paste local filesystem paths as Linear evidence;
- acceptable evidence: Linear-uploaded attachments, GitHub/PR comment attachments,
  accessible Playwright report URL, or another stable HTTPS artifact;
- if no preview/browser/upload path exists, state that evidence could not be captured or
  attached and include the blocker.

## Preview MCP

To run an agent against a preview's MCP server, pass the server for that run only:
`claude -p --mcp-config <file> --strict-mcp-config` or `codex exec -c mcp_servers.<name>.url=...`.
Never add a preview to `~/.claude.json` or `~/.codex/config.toml`: previews are deleted
after inactivity, and a stale entry times out at every session start. If you find an
entry for a preview that no longer answers, tell the user and propose removing it.

Steps on a preview: register with `POST <preview>/api/auth/register`
`{email, password, terms: true, name, forceCreateNewOrganization: true}` and take
`token.access_token`; read `organizationId` from `GET /api/user/mcp-keys/options`; create a
key with `POST /api/user/mcp-keys` `{clientName, organizationId, capabilities, expiresInDays: 1}`,
which returns `token` and `serverUrl`. Trust the preview CA with `--cacert`,
`NODE_EXTRA_CA_CERTS` for Claude, or `SSL_CERT_FILE` with the system bundle plus the CA for
Codex, and give Codex `mcp_servers.<name>.default_tools_approval_mode="approve"`, or every
MCP call fails under `approval_policy="never"`.
