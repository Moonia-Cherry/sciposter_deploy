---
name: popular-article-fastclaw-upload
description: Generate a FastClaw demo-ready WeChat-style article package from an uploaded paper, including file finding, parsed analysis, preview HTML, and md/docx/pdf exports.
---

# Popular Article FastClaw Upload

Turn an uploaded paper into a public-facing WeChat article package that includes:

- normalized paper intake
- structured parsed paper JSON
- rewritten article copy in readable Chinese
- title options
- chart and motion briefs
- preview HTML for demo display
- editable/exportable `.docx` article file
- exportable `.pdf` article file
- extracted paper figure assets when available

This skill is designed specifically for FastClaw demos where the user wants a visible local pipeline instead of a silent long wait.

## When To Use

Use this skill when the user wants:

- a Chinese WeChat public-account article from a paper
- a local workflow that can still complete even if a remote model is unstable
- a preview page with paragraph-level figure slots
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

If the paper is incomplete, continue with a best-effort article and list the missing information in `next_steps`.

## Required Output

Produce all of the following inside the workspace:

1. `popular-article-package.json`
2. `popular-article.md`
3. `article-title-options.md`
4. `chart-briefs.md`
5. `animation-briefs.md`
6. `popular-article-preview.html`
7. `popular-article.docx`
8. `popular-article.pdf`
9. `wechat-cover.png`
10. `wechat-cover.pptx`
11. `final-response.json`
12. `final-response.md`

If figures can be extracted from the paper, also create:

- `output/extracted-paper-assets/`

## Workflow

1. Normalize the uploaded paper into a safe ASCII filename.
2. Parse the paper into `output/parsed-paper.json`.
3. Rewrite the content into a WeChat-style public explainer.
4. Extract embedded paper figures when possible.
5. Build a preview HTML page with article sections and inline figure slots.
6. Generate `docx` and `pdf` article exports.
7. Generate a `900x383` WeChat header cover in `png` and `pptx`.
8. Write a compact final response for the agent to surface directly.

## Progress Visibility

Keep the user informed while the package is being generated.

- write `todo.md`
- write `output/popular-article-progress.json`
- tell the user when paper intake is complete
- tell the user when article rewriting begins
- tell the user when preview page generation begins
- tell the user when the preview page and assets are ready

## Deterministic Commands

In FastClaw, this skill is mounted under `skills/popular-article-fastclaw-upload/`, not the workspace root.
Run this command directly as the happy path:

```bash
python skills/popular-article-fastclaw-upload/scripts/run_popular_article_pipeline.py --workspace . --output-dir output
```

Normal execution policy:

- prefer exactly one `exec` call for the whole final-generation workflow
- do not use `edit_file` or `write_file` during the normal success path
- do not ask the model to rewrite the article again in chat after local files already exist
- do not insert extra workspace inspection before the main workflow unless the command actually fails

If the user explicitly asks for a file check, title/abstract extraction, or "do not generate final content yet", run this deterministic inspection path instead:

```bash
mkdir -p output
python skills/popular-article-fastclaw-upload/scripts/prepare_workspace_inputs.py --workspace . --output output/workspace-inputs.json
python skills/popular-article-fastclaw-upload/scripts/parse_paper.py --input output/workspace-inputs.json --output-dir output
python skills/popular-article-fastclaw-upload/scripts/inspect_parsed_paper.py --input output/parsed-paper.json --output output/inspection-report.md
```

When this inspection path succeeds, directly answer using `output/inspection-report.md` and do not stop after only updating `todo.md`.

After success, use the generated local report:

- `output/final-response.json`
- `output/final-response.md`

## Quality Rules

- Rewrite for public readers, not for reviewers.
- Start from the research question before introducing the method.
- Avoid hype and unsupported claims.
- Keep the article factual and calm.
- Prefer short paragraphs and section headings that work in WeChat.
- If figures are extracted, prefer them over invented visuals.
- If no figures are extracted, keep explicit suggested figure slots in the preview page.

## Final Reply Format

When generation succeeds, surface the main deliverables with workspace links and stop. Do not ask the model to regenerate the same article content again in a later round. For example:

- `[Open Preview Page](/workspace/output/popular-article-preview.html)`
- `[Open Article Markdown](/workspace/output/popular-article.md)`
- `[Open DOCX Export](/workspace/output/popular-article.docx)`
- `[Open PDF Export](/workspace/output/popular-article.pdf)`
- `[Open WeChat Cover PNG](/workspace/output/wechat-cover.png)`
- `[Open WeChat Cover PPT](/workspace/output/wechat-cover.pptx)`
- `[Open Package JSON](/workspace/output/popular-article-package.json)`
- `[Open Final Report JSON](/workspace/output/final-response.json)`
- `[Open Final Report Markdown](/workspace/output/final-response.md)`

If extracted figure assets exist, mention that they are available under `output/extracted-paper-assets/`.

## Important Execution Rule

- Do not stop after only parsing the paper.
- If `output/parsed-paper.json` exists and the user asked for inspection, you must continue to `inspect_parsed_paper.py` and return the extracted title, abstract, and three key findings.
- If the user asked for final article generation, you must continue through `run_popular_article_pipeline.py` until `output/final-response.json` exists or a concrete error file is written.
