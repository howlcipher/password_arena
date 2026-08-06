with open("improvements.md", "r") as f:
    content = f.read()
import re
content = re.sub(
    r"\*\*Status:\*\* Done\n\nImplement an optional OpenAI backend",
    "**Status:** Done\n\n**Implementation note:**\nAdded `OpenAIProvider` to `src/password_arena/openai_provider.py`. Registered supported models, mapped error cases to `AvailabilityState`, and captured usage metrics.\n\n**Validation performed:**\n`pytest`, `mypy src/password_arena`, and `ruff check .` were run locally and all passed.\n\nImplement an optional OpenAI backend",
    content
)
with open("improvements.md", "w") as f:
    f.write(content)
