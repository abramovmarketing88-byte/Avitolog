# Assistants Setup

Add these variables to your `.env`:

```env
ASSISTANT_JTBD_PARSER_ID=asst_...
ASSISTANT_CREATIVE_BUILDER_ID=asst_...
ASSISTANT_SPINTAX_HTML_ID=asst_...
```

## Mapping

- `ASSISTANT_JTBD_PARSER_ID` -> `assistant-jtbd-parser`
- `ASSISTANT_CREATIVE_BUILDER_ID` -> `assistant-creative-builder`
- `ASSISTANT_SPINTAX_HTML_ID` -> `assistant-spintax-html`

## Notes

- If any assistant ID is missing, the bot falls back to local prompt files in `app/prompts/`.
- On startup, logs show active assistant configuration in masked form:
  - `Assistants config: jtbd_parser=yes (...) creative_builder=yes (...) spintax_html=yes (...)`
