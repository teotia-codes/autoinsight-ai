import os
import json

INSTRUCTION = (
    "Rewrite the draft analytics report into a polished executive markdown report. "
    "Preserve all facts, improve clarity, maintain section headings, and do not add unsupported claims."
)

DRAFTS_DIR = "training_data/drafts"
POLISHED_DIR = "training_data/polished"
OUTPUT_PATH = "training_data/report_refinement_data.jsonl"

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def build_text(draft_report, polished_report):
    return (
        f"### Instruction:\n{INSTRUCTION}\n\n"
        f"### Input:\n{draft_report}\n\n"
        f"### Response:\n{polished_report}"
    )

def main():
    os.makedirs("training_data", exist_ok=True)

    if not os.path.exists(DRAFTS_DIR):
        print(f"Error: {DRAFTS_DIR} does not exist.")
        return

    if not os.path.exists(POLISHED_DIR):
        print(f"Error: {POLISHED_DIR} does not exist.")
        return

    draft_files = sorted([f for f in os.listdir(DRAFTS_DIR) if f.endswith(".md")])
    examples = []

    for filename in draft_files:
        draft_path = os.path.join(DRAFTS_DIR, filename)
        polished_path = os.path.join(POLISHED_DIR, filename)

        if not os.path.exists(polished_path):
            print(f"Skipping {filename}: no matching polished file")
            continue

        draft_text = read_file(draft_path)
        polished_text = read_file(polished_path)

        if not draft_text or not polished_text:
            print(f"Skipping {filename}: empty file")
            continue

        examples.append({
            "text": build_text(draft_text, polished_text)
        })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Saved {len(examples)} examples to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()