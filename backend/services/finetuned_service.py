import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# =========================================================
# CONFIG
# =========================================================
BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

# Adjust path if needed
ADAPTER_PATH = os.path.join("models", "lora-final-report")

# Global cache so model loads only once
_tokenizer = None
_model = None


def load_finetuned_model():
    global _tokenizer, _model

    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    if not os.path.exists(ADAPTER_PATH):
        raise FileNotFoundError(
            f"LoRA adapter not found at: {ADAPTER_PATH}. "
            f"Make sure you copied the adapter folder into autoinsight-ai/models/lora-final-report"
        )

    print("[FineTuned Service] Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(ADAPTER_PATH)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("[FineTuned Service] Loading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )

    print("[FineTuned Service] Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    model.eval()

    _tokenizer = tokenizer
    _model = model

    return _tokenizer, _model


def query_finetuned_model(prompt: str, max_new_tokens: int = 220) -> str:
    """
    Generate text using base model + LoRA adapter.
    Safe fallback if model fails.
    """
    try:
        tokenizer, model = load_finetuned_model()

        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.3,
                do_sample=True,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Return only the generated continuation if possible
        if prompt in response:
            response = response[len(prompt):].strip()

        return response.strip()

    except Exception as e:
        return f"[Fine-tuned model error] {str(e)}"