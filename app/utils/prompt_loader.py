from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(file_name: str) -> str:
    prompt_path = PROMPTS_DIR / file_name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8").strip()
