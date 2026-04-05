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
# INTERNAL GENERATION
# =========================================================
def _generate_refinement(prompt: str, max_new_tokens: int = 420) -> str:
    tokenizer, model = load_finetuned_model()

    model_device = next(model.parameters()).device

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=1024
    )
    inputs = {k: v.to(model_device) for k, v in inputs.items()}

    input_length = inputs["input_ids"].shape[1]

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,  # deterministic for structured rewriting
            repetition_penalty=1.12,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    generated_ids = outputs[0][input_length:]
    response = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    if not response:
        raise RuntimeError("Fine-tuned model returned empty output.")

    return response


# =========================================================
# PROMPTING
# =========================================================
def build_refinement_prompt(chunk_text: str) -> str:
    return f"""### Instruction:
Rewrite the draft analytics report chunk into a polished executive markdown report chunk.
Preserve all facts.
Improve clarity and professionalism.
Maintain markdown headings and bullet structure.
Do NOT add unsupported claims.
Do NOT remove important information.

### Input:
{chunk_text}

### Response:
"""


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

    # fallback: no signal section found -> just one chunk
    return [report_text.strip()]


def merge_refined_chunks(chunks: list[str]) -> str:
    return "\n\n".join([c.strip() for c in chunks if c and c.strip()]).strip()


# =========================================================
# OPTIONAL CLEANUP
# =========================================================
def clean_refined_chunk(text: str) -> str:
    # remove accidental duplicated title if model re-adds it inside chunk 2
    text = re.sub(r"(?m)^# Final Report\s*\n?", "", text).strip()

    # fix common heading typo
    text = text.replace("## Visualization", "## Visualization Insights")

    return text.strip()


# =========================================================
# PUBLIC API
# =========================================================
def refine_report_chunk(chunk_text: str, max_new_tokens: int = 420) -> str:
    """
    Refine a single report chunk.
    """
    try:
        prompt = build_refinement_prompt(chunk_text)
        refined = _generate_refinement(prompt, max_new_tokens=max_new_tokens)
        refined = clean_refined_chunk(refined)
        return refined
    except Exception as e:
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
            refined_chunk = refine_report_chunk(chunk, max_new_tokens=420)
            refined_chunks.append(refined_chunk)

        final_refined = merge_refined_chunks(refined_chunks)

        # ensure title exists
        if not final_refined.startswith("# Final Report"):
            final_refined = "# Final Report\n\n" + final_refined

        return final_refined.strip()

    except Exception as e:
        print("[FineTuned Service] FULL REPORT REFINEMENT ERROR:")
        traceback.print_exc()
        return report_text  # safe fallback
def query_finetuned_model(prompt: str, max_new_tokens: int = 420) -> str:
    """
    Backward-compatible wrapper for older node imports.
    Uses single-chunk refinement.
    """
    return refine_report_chunk(prompt, max_new_tokens=max_new_tokens)