---
name: xhs-fastclaw-upload
description: Generate a FastClaw demo-ready Xiaohongshu image-post package from an uploaded paper, including file finding, parsed analysis, preview HTML, one DOCX publishing guide, and ready-to-save post images.
---

# XHS FastClaw Upload

Turn an uploaded paper into a publish-ready Xiaohongshu note package that includes:

- normalized paper intake
- structured parsed paper JSON
- rewritten Xiaohongshu note copy in readable Chinese
- title options
- cover copy
- carousel card copy
- hashtags
- preview HTML for demo display
- one `.docx` publishing guide
- ready-to-save post images
- extracted paper figure assets when available

This skill is designed specifically for FastClaw demos where the user wants a visible local pipeline instead of a silent long wait.

## When To Use

Use this skill when the user wants:

- a Chinese Xiaohongshu note from a paper
- a local workflow that can still complete even if a remote model is unstable
- a preview page with cover and card-level figure slots
- paper images extracted from the source file when possible
- a deliverable package that is easy to demo inside FastClaw

## Expected Inputs

Accept any mix of:

- `.pdf`
- `.doc`
- `.docx`
- `.md`
- `.txt`
- optional audience or style notes

If the paper is incomplete, continue with a best-effort note package and list the missing information in `next_steps`.

## Required Output

Produce all of the following inside the workspace:

1. `xiaohongshu-package.json`
2. `title-options.md`
3. `cover-copy.md`
4. `carousel-cards.md`
5. `hashtags.md`
6. `xiaohongshu-post.md`
7. `xiaohongshu-preview.html`
8. `xiaohongshu-package.docx`
9. `xiaohongshu-images/`
10. `final-response.json`
11. `final-response.md`

If figures can be extracted from the paper, also create:

- `output/extracted-paper-assets/`

## Workflow

1. Normalize the uploaded paper into a safe ASCII filename.
2. Parse the paper into `output/parsed-paper.json`.
3. Rewrite the content into a Xiaohongshu-style scientific note.
4. Extract embedded paper figures when possible.
5. Build a preview HTML page with cover, card sections, and inline figure slots.
6. Generate one `docx` publishing guide and a batch of ready-to-save post images.
7. Write a compact final response for the agent to surface directly.

## Progress Visibility

Keep the user informed while the package is being generated.

- write `todo.md`
- write `output/xhs-progress.json`
- tell the user when paper intake is complete
- tell the user when note rewriting begins
- tell the user when preview page generation begins
- tell the user when the preview page and assets are ready

## Deterministic Commands

In FastClaw, this skill is mounted under `skills/xhs-fastclaw-upload/`, not the workspace root.
Run this command directly as the happy path:

```bash
python skills/xhs-fastclaw-upload/scripts/run_xhs_pipeline.py --workspace . --output-dir output
```

Normal execution policy:

- prefer exactly one `exec` call for the whole final-generation workflow
- do not use `edit_file` or `write_file` during the normal success path
- do not ask the model to rewrite the note again in chat after local outputs already exist
- do not insert extra workspace inspection before the main workflow unless the command actually fails

If the user explicitly asks for file checking or only wants title/abstract/core findings before final generation, run this inspection-first chain:

```bash
mkdir -p output
python skills/xhs-fastclaw-upload/scripts/prepare_workspace_inputs.py --workspace . --output output/workspace-inputs.json
python skills/xhs-fastclaw-upload/scripts/parse_paper.py --input output/workspace-inputs.json --output-dir output
```

Then answer from `output/parsed-paper.json` directly. Do not stop after only loading the skill or updating `todo.md`.

After success, use the generated local report:

- `output/final-response.json`
- `output/final-response.md`

## Quality Rules

- Rewrite for mobile readers, not for reviewers.
- Start from the research question before introducing the method.
- Avoid hype and unsupported claims.
- Keep the note factual and calm.
- Prefer short card blocks and headings that work in Xiaohongshu.
- If figures are extracted, prefer them over invented visuals.
- If no figures are extracted, keep explicit suggested figure slots in the preview page.

## Final Reply Format

When generation succeeds, surface the main deliverables with workspace links, for example:

- `[Open Preview Page](/workspace/output/xiaohongshu-preview.html)`
- `[Open Note Markdown](/workspace/output/xiaohongshu-post.md)`
- `[Open DOCX Export](/workspace/output/xiaohongshu-package.docx)`
- `[Open Generated Images Folder](/workspace/output/xiaohongshu-images/)`
- `[Open Package JSON](/workspace/output/xiaohongshu-package.json)`

If extracted figure assets exist, mention that they are available under `output/extracted-paper-assets/`.

## Important Execution Rule

- Do not stop after only parsing the paper.
- If `output/parsed-paper.json` exists, either continue to the final `run_xhs_pipeline.py` flow or explicitly return the parsed title/abstract/core findings when the user asked for inspection only.
