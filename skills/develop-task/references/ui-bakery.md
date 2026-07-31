# UI Bakery Repository Context

Load this reference only after repository evidence identifies the UI Bakery
monorepo. Verify every starting assumption against current code.

## Workflow Integration

When `$develop-please` wraps `$develop-task`, let `$develop-please` own:

- Linear issue lifecycle;
- branch source, base, and naming policy;
- PR target, title, body, and draft/ready state;
- GitHub checks;
- Hetzner preview and e2e behavior;
- review-thread handling;
- terminal Ready, No-op, or Blocked outcome;
- final reporting channel.

Keep `$develop-task` responsible for mandatory engineering gates, adaptive model
routing, implementation ownership, validation evidence, scope control, and
approval state. Do not independently commit, push, open or edit a PR, update
Linear, wait on CI or preview environments, or resolve review threads unless the
outer workflow delegates that exact action.

Treat an explicit combined prompt as user intent to use `$develop-task` review
delegation. It does not override higher-priority instructions, runtime
concurrency limits, safety constraints, or an outer workflow rule that cannot
delegate the requested role.

## Owner Map

Use this map only as a starting point:

- Custom Apps AI agent runtime: `front/projects/chat/app/agent`
- Custom App renderer/runtime: `front/projects/components/src/lib/custom-react-app`
- AI builder UI in Bakery: `front/projects/bakery/src/app/tools/builder/module-chat`
- User-facing bottom-tab assistant, unrelated to Custom Apps:
  `front/projects/bakery/src/app/tools/layout/bottom-tabs/chat-dialog`
- Bakery Angular shell and workspace/account UI: `front/projects/bakery`
- Workbench builder canvas and preview host: `front/projects/workbench`
- Oven renderer library: `front/projects/oven`
- Low-code component definitions and schemas: `front/projects/components`
- Datasource runtime and connectors: `front/projects/datasource`
- Automations frontend/server: `front/projects/automation`
- Chat backend service: `front/projects/chat`
- Docker sandbox service: `front/projects/docker-sandbox`
- Java backend: `back/projects/bakery` and `back/projects/bakery-cloud`

## Validation Hints

Choose the narrowest check that proves the changed behavior:

- Angular project changes: run the affected `front` test target and focused
  lint/typecheck when available.
- Chat backend or Custom Apps agent changes: run focused Jest tests in
  `front/projects/chat`; use relevant evals for generated-app, tool, planning,
  datasource sync, screenshot, file-operation, or sandbox behavior changes.
- Datasource changes: run focused tests in `front/projects/datasource`.
- Docker sandbox changes: run focused tests in
  `front/projects/docker-sandbox`.
- Java backend changes: run a narrow Maven test from `back/projects`, or a
  compile check when Testcontainers or Docker blocks integration tests.
- Duplication-sensitive broad frontend changes: consider
  `cd front && npm run jscpd`.
- User-visible UI changes: consider a screenshot, browser smoke, or focused
  Playwright flow when runtime layout matters.

For NgRx changes, explicitly review effect races, stale state, rollback hazards,
and lifecycle behavior.

Do not run `npm run -s build bakery` unless the user explicitly asks or no
smaller useful validation exists.
