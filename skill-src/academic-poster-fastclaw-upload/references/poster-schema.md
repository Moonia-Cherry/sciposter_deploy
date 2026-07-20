# Poster Schema

Use this schema when generating a poster draft for FigPad or any other poster editor.

## Root Object

```json
{
  "poster_type": "academic",
  "theme": {
    "tone": "clean",
    "accent_color": "optional",
    "layout": "three-column"
  },
  "paper": {
    "title": "",
    "authors": [],
    "affiliation": "",
    "venue": "",
    "year": "",
    "keywords": []
  },
  "hero": {
    "headline": "",
    "subheadline": "",
    "key_findings": []
  },
  "sections": [],
  "figures": [],
  "footer": {
    "references": [],
    "contact": "",
    "acknowledgements": ""
  },
  "missing_information": []
}
```

## Section Object

```json
{
  "id": "results",
  "title": "Results",
  "kind": "bullets",
  "content": [
    "Main point 1",
    "Main point 2"
  ],
  "layout_hints": {
    "priority": "high",
    "column_span": 1
  }
}
```

## Figure Object

```json
{
  "id": "fig1",
  "title": "Model overview",
  "purpose": "Explain the pipeline",
  "source_needed": true,
  "caption": "",
  "placement_hint": "top-right"
}
```

## Content Rules

- `hero.headline` should express the main contribution, not the paper topic alone.
- `key_findings` should be short and quantitative when possible.
- `sections[].kind` should be one of `paragraph`, `bullets`, `metrics`, `timeline`, or `references`.
- `missing_information` should list facts the system could not safely infer.
- Keep `content` concise enough for a poster, not a paper.
