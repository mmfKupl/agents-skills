---
name: pdf-analysis-images
description: Render missing PDF page images and agent-preview thumbnails for the glinet-file-mcp medical/lab analysis archive. Use when the user asks to process '/Volumes/Storage/kkupl/glinet-file-mcp/мама анализы', extract pictures/pages from PDFs, create images next to analysis PDFs, create agent-preview images, or refresh PDF/image preprocessing for the personal file MCP archive.
---

# PDF Analysis Images

## Writing quality

Before drafting the user-facing report, read
[`../unslop/SKILL.md`](../unslop/SKILL.md) and apply its relevant editing
guidance. Preserve user-provided wording, exact command output, and required
output formats when they conflict with that guidance.

## Purpose

Use the existing `ensure-pdf-images.sh` workflow for analysis archives. The script renders PDF pages to PNG files beside the source PDFs and creates `agent-preview-*.jpg` previews for PDFs and standalone image files.

Known default archive:

```bash
/Volumes/Storage/kkupl/glinet-file-mcp/мама анализы
```

## Source Script

Prefer the canonical local git checkout:

```bash
/Users/kupl/dev/glinet-file-mcp/ensure-pdf-images.sh
```

Fallbacks:

```bash
/Volumes/Storage/kkupl/glinet-file-mcp/ensure-pdf-images.sh
/Users/kupl/Documents/Codex/2026-05-28/new-chat/ensure-pdf-images.sh
```

Repository context: `/Users/kupl/dev/glinet-file-mcp` tracks `git@github.com:mmfKupl/glinet-file-mcp.git`. The relevant commit is `ffc0fd2 Add image previews for PDF extracts`.

Do not edit the source script unless the user explicitly asks. For normal runs, copy it to a local temporary directory and execute the copy.

## Workflow

1. Resolve targets from the user request.
   - If the user says "мама анализы" or does not provide a path, use the known default archive path.
   - If the user provides files, pass them to the wrapper; it will run the source script on their parent directories so outputs are written beside the originals.
   - If the user provides directories, pass those directories directly.
2. Run the bundled wrapper:

```bash
bash /Users/kupl/.codex/skills/pdf-analysis-images/scripts/run-pdf-analysis-images.sh "/path/to/folder-or-file"
```

For the default archive:

```bash
bash /Users/kupl/.codex/skills/pdf-analysis-images/scripts/run-pdf-analysis-images.sh --mama-analizy
```

3. Report the command summary from the script. Mention dependency failures clearly.

## Behavior

The wrapped script is idempotent:

- one-page PDF: creates `<stem>-image.png`;
- multi-page PDF: creates `<stem>-image-01.png`, `<stem>-image-02.png`, etc.;
- preview files: creates `agent-preview-<stem>...jpg`;
- existing outputs are skipped.

When a single file is requested, the wrapper processes the file's directory. This may also fill missing outputs for neighboring files in that directory; that is expected and usually desirable for the archive.

## Requirements

Required:

```bash
pdftoppm
pdfinfo
```

These come from Poppler. On macOS, the user can install them with:

```bash
brew install poppler
```

Optional:

```bash
magick
```

This comes from ImageMagick and enables previews for standalone image files:

```bash
brew install imagemagick
```

Do not install dependencies without user approval.
