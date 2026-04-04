import os
import torch
import traceback
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# =========================================================
# CONFIG
# =========================================================
BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
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

    try:
        print("[FineTuned Service] Loading tokenizer...")
        # SAFER: load tokenizer from base model, not adapter folder
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        print("[FineTuned Service] Tokenizer loaded successfully.")

        print("[FineTuned Service] Loading base model...")

        # Safe loading for Windows/local laptop
        if torch.cuda.is_available():
            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype=torch.float16
            )
            base_model = base_model.to("cuda")
        else:
            base_model = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True
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


def query_finetuned_model(prompt: str, max_new_tokens: int = 220) -> str:
    """
    Generate text using base model + LoRA adapter.
    Safe fallback if model fails.
    """
    try:
        tokenizer, model = load_finetuned_model()

        # Put inputs on the same device as model
        model_device = next(model.parameters()).device
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
        inputs = {k: v.to(model_device) for k, v in inputs.items()}

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

        # Return only generated continuation if prompt is included
        if response.startswith(prompt):
            response = response[len(prompt):].strip()

        return response.strip()

    except Exception as e:
        print("[FineTuned Service] QUERY ERROR:")
        traceback.print_exc()
        return f"[Fine-tuned model error] {str(e)}"