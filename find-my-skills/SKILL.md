---
name: find-my-skills
description: Search and install skills from the my-skills registry (https://skills.sixiangjia.de). Discover available skills by keyword, then install them into the user's WorkBuddy skills directory.
---

# find-my-skills

Search and install skills from the my-skills registry.

## Registry

- **Index**: `https://skills.sixiangjia.de/index.json`
- **Search API**: `https://skills.sixiangjia.de/api/search?q=<query>`
- **Skill URL pattern**: `https://skills.sixiangjia.de/<skill-name>/SKILL.md`

## When to use

- User asks to find, browse, search, or install a skill from this registry
- User mentions "my-skills", "skill registry", or references a specific skill hosted here
- A task could benefit from a skill and the user hasn't installed it yet

## Instructions

### Step 1: Search

Use WebFetch to search the registry:

```
WebFetch(
  url = "https://skills.sixiangjia.de/api/search?q=<keyword>",
  prompt = "List all matching skills with their name, description, and url. Return the full JSON."
)
```

Or browse all available skills:

```
WebFetch(
  url = "https://skills.sixiangjia.de/index.json",
  prompt = "List all available skills with their name, description, and url. Return the full JSON."
)
```

### Step 2: Present results to user

Show the user what's available in a concise list format:

```
| Skill | Description | URL |
|-------|-------------|-----|
| name  | desc        | url |
```

### Step 3: Confirm and install

After the user picks a skill (or confirms the only match):

1. Use WebFetch to fetch the full SKILL.md content:
   ```
   WebFetch(
     url = "https://skills.sixiangjia.de/<skill-name>/SKILL.md",
     prompt = "Return the COMPLETE raw content of this SKILL.md file, including the YAML frontmatter. Do not summarize or modify anything."
   )
   ```

2. Write it to the user's skill directory:
   - **User-level**: `~/.workbuddy/skills/<skill-name>/SKILL.md`
   - **Project-level**: `{workspace}/.workbuddy/skills/<skill-name>/SKILL.md`
   - **Nanobot**: `nanobot\skills\<skill-name>\SKILL.md`

   Create the directory first if it doesn't exist.

3. Confirm to the user that the skill is installed and ready to use.

### Notes

- Always confirm with the user before installing (unless they explicitly said "install it" or equivalent).
- If the search returns no results, suggest the user try different keywords or browse the full index.
- The search API scores results by relevance: name match (3pts) > description match (2pts) > body match (1pt).
