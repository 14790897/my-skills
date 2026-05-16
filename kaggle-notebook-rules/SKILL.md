---
name: kaggle-notebook-rules
description: >
  Use this skill when creating Python scripts that target Kaggle Notebooks.
  This skill ensures correct cell separator format (# %% [code] and # %% [markdown])
  and Kaggle-specific conventions.
  Trigger when user mentions Kaggle, notebook format, # %% separators, or asks to create notebook-style Python scripts.
---

# Kaggle Notebook Format Rules

## Cell Separators

- Code cells: `# %% [code]`
- Markdown cells: `# %% [markdown]`

## Markdown Cell Formatting

**CRITICAL RULES:**

1. **Every line** must start with `# ` (hash + space)
2. **NEVER** use triple quotes (`"""` or `'''`) for markdown cells
3. **NO empty lines** with only `# ` - they create extra whitespace in rendered notebook

Correct markdown cell:
```python
# %% [markdown]
# # Title
# Content line 1
# Content line 2
# - Bullet point 1
# - Bullet point 2
```

## Code Cell Conventions

- Printed output in English
- File extension: `.py` (not `.ipynb`)
- Dataset paths: `/kaggle/input/dataset-name/`

## Package Installation

- Only install packages NOT pre-installed on Kaggle
- Use `%pip install -q package-name` (not `!pip install`)
- Common libraries (pandas, numpy, scipy, scikit-learn, torch, torchvision) are already available

## Common Mistakes to Avoid

1. Triple quotes in markdown cells → Use `# ` prefix on every line
2. Empty `# ` lines → Remove them
3. Missing `# ` prefix → Every line must start with `# `
4. Using `## Title` → Use `# Title` only
5. Using `!pip` → Use `%pip`
