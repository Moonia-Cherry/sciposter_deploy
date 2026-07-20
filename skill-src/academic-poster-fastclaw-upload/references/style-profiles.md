# Style Profiles

Use these stable style profiles for poster generation.

## `classic-blue`

- background: white
- headline color: deep navy
- accent color: conference blue
- body style: clean sans serif
- use case: standard academic conference poster

## `clean-light`

- background: off-white
- headline color: charcoal
- accent color: muted slate blue
- body style: restrained and neutral
- use case: journal club, formal lab poster, general research summary

## `green-tech`

- background: pale mint-white
- headline color: forest green
- accent color: emerald
- body style: modern research-tech
- use case: AI, engineering, systems, sustainability, computational science

## `serif-journal`

- background: warm paper
- headline color: near-black
- accent color: muted burgundy
- body style: serif title with sans body
- use case: humanities, communication, social science, editorial poster tone

## Mapping Rule

If the user gives a custom description such as:

- "科研正常一点"
- "正式学术风格"
- "不要花哨"

map to `classic-blue` or `clean-light`.

If the request emphasizes:

- sustainability
- biology
- environment
- green technology

map to `green-tech`.

If the request emphasizes:

- journal
- editorial
- literature review
- humanistic

map to `serif-journal`.
