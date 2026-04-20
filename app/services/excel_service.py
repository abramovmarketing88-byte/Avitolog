from pathlib import Path

import pandas as pd


COLUMNS = ["title", "description", "city", "geo", "segment"]


def export_ads_to_excel(rows: list[dict], output_path: str) -> Path:
    df = pd.DataFrame(rows)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out, index=False)
    return out
