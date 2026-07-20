---
name: slides-fastclaw-upload
description: Generate editable group-meeting PPT deliverables for the slides-agent from uploaded papers with local parsing, visible progress, and editable PowerPoint output.
---

# Slides FastClaw Upload

Turn a paper into a lab-meeting slide package that includes:

- normalized paper intake
- structured slide outline
- speaker notes
- figure and chart plan
- editable `.pptx` slides
- a static `.png` preview for direct FastClaw display
- a lightweight preview page

This skill is optimized for FastClaw chat demos where the user wants visible progress instead of silent waiting.
Use the fastest acceptable path: build a compact deck first, then refine only if the paper actually contains richer sections or figures.
This skill is intended to be used directly by `slides-agent` as a one-stop local pipeline.

## When To Use

Use this skill when the user wants:

- a group-meeting PPT from a paper
- a fast local pipeline with progress updates
- Chinese and English paper support
- a downloadable editable PowerPoint deck
- one local workflow that handles upload intake, parsing, planning, PPT generation, and final reporting

## Expected Inputs

Accept any mix of:

- `.pdf`
- `.doc`
- `.docx`
- `.md`
- `.txt`
- optional style request such as `classic-blue`, `clean-light`, or `deep-blue-lab`

## Required Output

Produce all of the following inside the workspace:

1. `slides-package.json`
2. `slides-outline.md`
3. `speaker-notes.md`
4. `figure-plan.md`
5. `discussion-questions.md`
6. `slides-preview.png`
7. `slides.pptx`
8. `slides-preview.html`
9. `final-response.json`
10. `final-response.md`

## Workflow

1. Normalize the uploaded paper into a safe ASCII filename.
2. Parse the paper into `output/parsed-paper.json`.
3. Build a compact slide package from the parsed paper using only the strongest sections and highlights.
4. Render an editable PowerPoint deck.
5. Build a compact final report so the agent can reply with minimal extra reasoning.
6. Leave all deliverables in the workspace so FastClaw can show and download them.

Do not split this into separate intake and slides sub-workflows when this skill is already available.

## Progress Visibility

Keep the user informed while the PPT is being generated.

- write `todo.md`
- write `output/slides-progress.json`
- tell the user when intake is done
- tell the user when outline drafting begins
- tell the user as soon as `slides-preview.png` is ready
- tell the user when PPT export begins
- tell the user when the deck is ready for download
- after generation, prefer the local `final-response.json` / `final-response.md` instead of writing a long custom summary

## Quality Rules

- Prefer a 9-slide to 12-slide lab-meeting structure.
- Prefer the minimum viable slide set that still looks complete: title, background, question, method, setup, results, discussion, conclusion, questions.
- Keep titles short.
- Do not invent experimental results.
- If the paper is incomplete, clearly mark missing details.
- Support both Chinese and English text.
- Make the deck editable in PowerPoint.
- Do not install packages or spin up a virtual environment during the PPT export path.

## Deterministic Commands

In FastClaw, this skill is mounted under `skills/slides-fastclaw-upload/`, not the workspace root.
Prefer one direct local workflow command whenever possible. Do not pause for extra directory inspection between commands unless one of them actually fails:

```bash
mkdir -p output && python skills/slides-fastclaw-upload/scripts/run_academic_slides_pipeline.py --workspace . --output-dir output
```

Default execution rule:

- prefer exactly one `exec` call for the whole workflow
- do not use `edit_file` or `write_file` during the normal success path
- do not draft extra slide text in chat after local files already exist
- do not insert `list_dir`, `pwd`, or exploratory checks in the happy path
- only inspect the workspace if one of the commands fails

Fallback only if the one-command run actually fails:

```bash
python skills/slides-fastclaw-upload/scripts/prepare_workspace_inputs.py --workspace . --output output/workspace-inputs.json
python skills/slides-fastclaw-upload/scripts/parse_paper.py --input output/workspace-inputs.json --output-dir output
python skills/slides-fastclaw-upload/scripts/run_academic_slides_pipeline.py --workspace . --input output/parsed-paper.json --output-dir output
```

After success, use the generated local report:

- `final-response.json`
- `final-response.md`

## Deliverables Guidance

Good deliverables include:

- `slides-outline.md`
- `speaker-notes.md`
- `figure-plan.md`
- `discussion-questions.md`
- `slides-preview.png`
- `slides.pptx`
