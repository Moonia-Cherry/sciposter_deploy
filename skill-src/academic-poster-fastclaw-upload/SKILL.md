---
name: academic-poster-fastclaw-upload
description: Generate a FastClaw demo-ready academic poster package from an uploaded paper, including safe file intake, visible progress, preview files, and editable PPTX output.
---

# Academic Poster FastClaw Upload

Turn a paper plus optional images into a poster package that includes:

- a parsed paper summary
- a structured poster spec
- a style-locked layout
- a template-selected composition
- a scalable preview artifact
- an editable `.pptx` poster output

This skill is for end-to-end poster generation inside FastClaw, not only content planning.

## When To Use

Use this skill when the user wants any of the following:

- upload a paper and automatically parse the full text
- upload charts, figures, or lab images and place them into a poster
- upload only the paper and still generate a poster by extracting embedded figures
- constrain the poster to a requested visual style or template
- export the final result as an editable PowerPoint poster
- a local FastClaw workflow that visibly progresses instead of silently waiting

## Expected Inputs

Accept any mix of:

- PDF paper
- `.txt`, `.md`, `.doc`, or `.docx` manuscript text
- abstract or notes
- figure images such as `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`
- optional style request such as `classic-blue`, `clean-light`, `green-tech`, `serif-journal`
- optional template request such as `conference-classic`, `data-focus`, `compact-journal`, `visual-showcase`

If some information is missing, continue with a best-effort output and list the gaps in `missing_information`.

## Required Output

Produce all of the following inside the workspace:

1. `poster-package.json`
2. `poster-spec.json`
3. `academic-poster.svg`
4. `academic-poster.png`
5. `academic-poster.pptx`
6. `poster-preview.html`
7. `final-response.json`
8. `final-response.md`

The `.pptx` must remain editable in PowerPoint. Do not output a flat image-only poster as the only deliverable.

## Workflow

1. Normalize the uploaded paper into a safe ASCII filename.
2. Parse the paper into title, authors, abstract, methods, results, conclusion, and references when possible.
3. If no external images are uploaded, extract embedded figures from the paper.
4. Normalize the requested style into one of the supported style profiles.
5. Normalize the requested template into one of the supported template profiles.
6. Build a structured poster package with concise, poster-length content.
7. Render a scalable SVG preview.
8. Render an editable academic poster `.pptx`.
9. Build a compact final report the agent can surface directly.
10. Leave the deliverables in the workspace so the user can preview and download them.

## Progress Visibility

The poster pipeline includes one relatively slow stage: editable PPTX rendering.

To avoid the FastClaw UI looking frozen, you must keep progress visible while the poster is being generated:

1. Before running the pipeline, tell the user you are starting poster generation.
2. During execution, rely on `todo.md` and `output/poster-progress.json` written by the pipeline as the live progress source.
3. As soon as `academic-poster.svg` is ready, explicitly tell the user that the visual preview is already available even if PPTX export is still running.
4. Tell the user that PPTX rendering is the slowest step and that this is expected, not a stuck process.
5. When the pipeline finishes, summarize the ready-to-download files.

## Fast Path

Do not spend multiple rounds planning when the user clearly wants the poster generated now.

- Run the deterministic command directly.
- Prefer exactly one `exec` tool call for the whole poster workflow.
- Do not use `edit_file` or `write_file` during the normal success path.
- Do not ask the model to re-summarize or re-layout the poster in chat after local outputs already exist.
- Do not pause for extra directory inspection unless one of the commands actually fails.
- Do not `read_file` or `cat` the raw uploaded paper path before normalization.
- Do not use `edit_file` to create helper files during a normal poster run.
- Only explain limitations after command execution actually fails.
- Do not run `list_dir`, `find`, `pwd`, `echo`, `ls`, or ad-hoc shell probes before the main workflow command when the user has already uploaded a paper and asked to generate now.

## Deterministic Commands

In FastClaw, this skill is mounted under `skills/academic-poster-fastclaw-upload/`, not the workspace root.
Use this single local workflow command whenever possible:

```bash
python skills/academic-poster-fastclaw-upload/scripts/run_fastclaw_poster_entry.py \
  --workspace . \
  --output-dir output \
  --style classic-blue \
  --template conference-classic
```

Fallback only if the one-command run actually fails:

```bash
python skills/academic-poster-fastclaw-upload/scripts/prepare_workspace_inputs.py \
  --workspace . \
  --output output/workspace-inputs.json

python skills/academic-poster-fastclaw-upload/scripts/run_academic_poster_pipeline.py \
  --workspace . \
  --input output/workspace-inputs.json \
  --output-dir output \
  --style classic-blue \
  --template conference-classic
```

## Execution Policy

When the user uploads a paper and asks for a poster immediately:

1. Reply with one short sentence that generation is starting.
2. Invoke the single entry command above in one `exec`.
3. Wait for that command to finish.
4. Read only the final local report files if needed.

Do not expand the workflow into manual inspection steps unless the command actually fails.

After success, use the generated local report:

- `output/final-response.json`
- `output/final-response.md`

The pipeline produces:

- `academic-poster.pptx`
- `academic-poster.png`
- `academic-poster.svg`
- `poster-preview.html`
- `poster-package.json`
- `poster-spec.json`

`prepare_workspace_inputs.py` must be treated as the source of truth for:

- recursively finding uploaded paper files under the workspace and any `sessions/` subdirectories
- excluding workflow files such as `todo.md` and old poster outputs
- copying the real paper into a safe filename like `paper.docx` or `paper.doc`

If the user also asks for an external export directory, generate into the workspace first. Only after the files exist should you copy them to the extra directory.

## Filename Safety

- Always assume uploaded filenames may contain Chinese characters, spaces, or punctuation that can break shell commands inside the sandbox.
- Never rely on the raw uploaded filename in `cat`, `read_file`, or pipeline commands.
- Prefer `scripts/prepare_workspace_inputs.py` so the user can upload Chinese-named papers normally while the workflow transparently copies them to safe names such as `paper.docx`.
- After normalization, use only the safe normalized filenames for downstream commands.

## Style Rules

Supported style profiles:

- `classic-blue`
- `clean-light`
- `green-tech`
- `serif-journal`

Supported template profiles:

- `conference-classic`
- `data-focus`
- `compact-journal`
- `visual-showcase`
- `autofi-academic-poster`
- `colorful-four-column-academic-poster`
- `icml-spotlight-academic-poster`
- `reference-academic-poster`
- `reference-style-academic-poster`
- `royal-blue-math-academic-poster`

These names map to the template images in `D:\Poster_project\poster_model\`.

If the user gives a free-form request, map it to the closest supported style and template and record that mapping in the JSON.

## Poster Rules

- Prefer a 3-column research poster structure.
- Prefer short sections over pasted full paragraphs.
- Default to 2-4 bullets per section, not full paper text.
- Prefer under-filling to over-filling. A slightly sparse poster is better than overlapping or cramped content.
- Make results visually dominant.
- Never invent metrics, p-values, datasets, or claims not supported by the source.
- Prefer vector figures when available because they remain sharp when enlarged.
- When extracting images from the paper itself, prefer high-resolution figures only.
- Do not place obviously blurry low-resolution paper images into a large poster slot unless there is no better asset.
- If image quality is insufficient, keep the slot but note that a higher-resolution original figure is recommended.
- Small raster figures may still be used, but only in secondary slots.

## Final Reply Format

When generation succeeds, explicitly surface preview and download paths using workspace links, for example:

- `![Poster Preview](/workspace/academic-poster.png)`
- `[Download PPTX](/workspace/academic-poster.pptx)`
- `[Download SVG](/workspace/academic-poster.svg)`
- `[Open Preview Page](/workspace/poster-preview.html)`

When generation is still in progress but SVG is already ready, say so clearly and mention that PPTX export is still running.

## References

- Read [references/poster-schema.md](./references/poster-schema.md)
- Read [references/style-profiles.md](./references/style-profiles.md)
- Read [references/template-profiles.md](./references/template-profiles.md)
