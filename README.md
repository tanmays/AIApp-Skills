# AIApp Skills

This repository is a collection of skills for AIApp, an upcoming personal AI agent app for iOS.

Skills give AIApp focused instructions, workflows, and optional bundled resources for handling specific tasks. A skill can teach the agent how to work with a domain, follow a repeatable process, use supporting scripts, or load reference material only when it is needed.

## What Is a Skill?

A skill is a modular, self-contained package. Each skill lives in its own directory and must include a `SKILL.md` file. The `SKILL.md` file starts with YAML frontmatter, followed by Markdown instructions for the agent.

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name + description required)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/       - Executable code
    ├── references/    - Documentation loaded as needed
    └── assets/        - Files used in output (templates, icons, etc.)
```

### Required Frontmatter

Every `SKILL.md` should include:

```yaml
---
name: skill-name
version: 1.0.0
description: This skill should be used when the user asks to ...
---
```

- `name`: The skill name. Keep it short, lowercase, and directory-friendly.
- `version`: The skill version. New skills should generally start at `1.0.0`.
- `description`: The trigger description. This is how AIApp decides when to load the skill, so it should be specific and include concrete user intents or phrases.

## Writing a Good Skill

Good skills are concise, practical, and easy for an AI agent to apply. Assume the model is already capable; the skill should provide the extra domain knowledge, workflow, constraints, examples, or resources needed to do the task well.

### Format

Use this general structure for `SKILL.md`:

```markdown
---
name: example-skill
version: 1.0.0
description: This skill should be used when the user asks to "do a specific task", "handle a specific workflow", or mentions a specific tool/domain.
---

# Example Skill

Briefly explain what the skill is for.

## Workflow

1. Start with the required context.
2. Follow the core procedure.
3. Use bundled resources when needed.
4. Verify the result.

## Additional Resources

- `references/patterns.md` - Detailed patterns.
- `scripts/example.sh` - Helper script for repeatable work.
- `assets/template.ext` - Template used in generated output.
```

### Do

- Write clear trigger descriptions with exact tasks, phrases, tools, or domains that should activate the skill.
- Use imperative instructions such as "Read the config", "Validate the input", and "Run the helper script".
- Keep `SKILL.md` focused on the core workflow.
- Move long explanations, API notes, examples, and edge cases into `references/`.
- Put repeatable or fragile operations in `scripts/` instead of describing them manually.
- Use `assets/` for templates, icons, fixtures, or other files the skill should reuse.
- Document any required configuration, credentials, or environment assumptions.
- Test the skill on realistic prompts before submitting it.

### Don't

- Do not make the description vague, such as "Helps with APIs" or "Use for automation".
- Do not put large manuals or exhaustive reference material directly in `SKILL.md`.
- Do not include secrets, personal credentials, tokens, or machine-specific paths.
- Do not rely on hidden assumptions that are not documented in the skill.
- Do not add bundled resources that are not referenced or useful.
- Do not over-explain general knowledge the model already has.

## Contributor Checklist

Before opening a pull request:

- Confirm the skill has a directory with a valid `SKILL.md`.
- Confirm `name`, `version`, and `description` are present in YAML frontmatter.
- Confirm the description clearly states when the skill should be used.
- Confirm instructions are concise and actionable.
- Confirm optional resources are organized under `scripts/`, `references/`, or `assets/`.
- Confirm no secrets or local-only configuration are committed.
- Confirm the skill has been tested against at least one realistic user request.

## License

This project is licensed under the MIT License.
