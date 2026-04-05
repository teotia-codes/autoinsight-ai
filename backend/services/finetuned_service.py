import os
import re
import torch
import traceback
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# =========================================================
# CONFIG
# =========================================================
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
ADAPTER_PATH = os.path.join("models", "qwen15b-full-report-refiner")

# Global cache so model loads only once
_tokenizer = None
_model = None


# =========================================================
# MODEL LOADING
# =========================================================
def load_finetuned_model():
    global _tokenizer, _model

    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    if not os.path.exists(ADAPTER_PATH):
        raise FileNotFoundError(
            f"LoRA adapter not found at: {ADAPTER_PATH}. "
            f"Make sure you extracted the adapter folder into "
            f"autoinsight-ai/models/qwen15b-full-report-refiner"
        )

    try:
        print("[FineTuned Service] Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        print("[FineTuned Service] Tokenizer loaded successfully.")
        print("[FineTuned Service] Loading base model...")

        # Windows-safe loading
        if torch.cuda.is_available():
            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype=torch.float16,
                trust_remote_code=True
            )
            base_model = base_model.to("cuda")
        else:
            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
                trust_remote_code=True
            )
            base_model = base_model.to("cpu")

        print("[FineTuned Service] Base model loaded successfully.")
        print("[FineTuned Service] Loading LoRA adapter...")

        model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
        model.eval()

        print("[FineTuned Service] LoRA adapter loaded successfully.")
        print("[FineTuned Service] Fine-tuned model ready.")

        _tokenizer = tokenizer
        _model = model

        return _tokenizer, _model

    except Exception as e:
        print("[FineTuned Service] ERROR while loading model:")
        traceback.print_exc()
        raise e


# =========================================================
# PROMPTING (QWEN CHAT FORMAT)
# =========================================================
def build_refinement_instruction(chunk_text: str) -> str:
    return f"""Rewrite the following draft analytics report chunk into a polished executive markdown report chunk.

Rules:
- Preserve all factual meaning
- Improve clarity and executive tone
- Keep markdown headings and bullet structure
- Do NOT add unsupported claims
- Do NOT introduce dialogue or Q&A text
- Return ONLY the improved markdown chunk

Draft report chunk:

{chunk_text}
"""


# =========================================================
# INTERNAL GENERATION (QWEN CHAT TEMPLATE)
# =========================================================
def _generate_refinement(chunk_text: str, max_new_tokens: int = 320) -> str:
    tokenizer, model = load_finetuned_model()

    model_device = next(model.parameters()).device

    system_msg = (
        "You are an executive analytics report refiner. "
        "Rewrite report sections cleanly in markdown. "
        "Never output dialogue, Q&A, Human:, Assistant:, or explanations."
    )

    user_msg = build_refinement_instruction(chunk_text)

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(
        prompt_text,
        return_tensors="pt",
        truncation=True,
        max_length=1536
    )
    inputs = {k: v.to(model_device) for k, v in inputs.items()}

    input_length = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,   # deterministic for structured rewriting
            repetition_penalty=1.08,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    generated_ids = outputs[0][input_length:]
    response = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    if not response:
        raise RuntimeError("Fine-tuned model returned empty output.")

    return response


# =========================================================
# CLEANUP
# =========================================================
def clean_refined_chunk(text: str) -> str:
    if not text:
        return text

    # Remove chat artifacts
    text = re.sub(r"(?im)^Human:\s*", "", text)
    text = re.sub(r"(?im)^Assistant:\s*", "", text)
    text = re.sub(r"(?im)^User:\s*", "", text)
    text = re.sub(r"(?im)^System:\s*", "", text)

    # Remove fenced code blocks if model adds them
    text = text.replace("```markdown", "").replace("```", "")

    # Remove duplicated "Final Report" heading inside chunks
    text = re.sub(r"(?m)^# Final Report\s*\n?", "", text)
    text = re.sub(r"(?m)^Final Report\s*\n?", "", text)

    # Cut off if model starts generating fake follow-up dialogue
    stop_markers = [
        "\nHuman:",
        "\nAssistant:",
        "\nUser:",
        "\n### Task:",
        "\n### Response:",
        "\nInput:",
        "\nResponse:",
        "\nRevised Report Chunk:"
    ]

    cut_positions = [text.find(marker) for marker in stop_markers if text.find(marker) != -1]
    if cut_positions:
        text = text[:min(cut_positions)].strip()

    # Fix heading typo if partial
    text = text.replace("## Visualization", "## Visualization Insights")

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text.strip()


# =========================================================
# REPORT CHUNKING
# =========================================================
def split_report_into_chunks(report_text: str):
    """
    Split full report into 2 stable chunks:
    Chunk 1 = from start through KPI Highlights
    Chunk 2 = everything after KPI Highlights
    """
    marker = "## Signal Ranking Highlights"

    if marker in report_text:
        idx = report_text.find(marker)
        chunk1 = report_text[:idx].strip()
        chunk2 = report_text[idx:].strip()
        return [chunk1, chunk2]

    return [report_text.strip()]


def merge_refined_chunks(chunks: list[str]) -> str:
    merged = "\n\n".join([c.strip() for c in chunks if c and c.strip()]).strip()

    # Ensure single title only
    merged = re.sub(r"(?m)^(# Final Report\s*\n)+", "# Final Report\n\n", merged)

    if not merged.startswith("# Final Report"):
        merged = "# Final Report\n\n" + merged

    return merged.strip()


# =========================================================
# PUBLIC API
# =========================================================
def refine_report_chunk(chunk_text: str, max_new_tokens: int = 320) -> str:
    """
    Refine a single report chunk.
    Safe fallback if model output is malformed.
    """
    try:
        refined = _generate_refinement(chunk_text, max_new_tokens=max_new_tokens)
        refined = clean_refined_chunk(refined)

        # Safety fallback if output is too weak / malformed
        if len(refined.strip()) < 80:
            print("[FineTuned Service] Refined chunk too short. Falling back to original chunk.")
            return chunk_text

        return refined

    except Exception:
        print("[FineTuned Service] CHUNK REFINEMENT ERROR:")
        traceback.print_exc()
        return chunk_text  # safe fallback


def refine_full_report_chunked(report_text: str) -> str:
    """
    Refine full report by splitting into 2 chunks, refining each, then merging.
    Safe fallback if anything fails.
    """
    try:
        if not report_text or not report_text.strip():
            return report_text

        chunks = split_report_into_chunks(report_text)

        refined_chunks = []
        for i, chunk in enumerate(chunks):
            print(f"[FineTuned Service] Refining chunk {i+1}/{len(chunks)}...")
            refined_chunk = refine_report_chunk(chunk, max_new_tokens=320)
            refined_chunks.append(refined_chunk)

        final_refined = merge_refined_chunks(refined_chunks)
        return final_refined.strip()

    except Exception:
        print("[FineTuned Service] FULL REPORT REFINEMENT ERROR:")
        traceback.print_exc()
        return report_text  # safe fallback


# =========================================================
# BACKWARD-COMPAT WRAPPER (optional safety)
# =========================================================
def query_finetuned_model(prompt: str, max_new_tokens: int = 320) -> str:
    """
    Backward-compatible wrapper for any legacy imports.
    Treats the incoming prompt as a chunk and refines it.
    """
    return refine_report_chunk(prompt, max_new_tokens=max_new_tokens)