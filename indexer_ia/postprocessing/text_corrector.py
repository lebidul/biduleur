import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Utiliser un modèle approprié pour la correction grammaticale en français
model_name = 'facebook/bart-large-cnn'  # Exemple de modèle
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

def correct_text_with_model(text):
    """
    Corrige le texte en utilisant un modèle de langage.

    Args:
    - text (str): Le texte à corriger.

    Returns:
    - str: Le texte corrigé.
    """
    if not text.strip():
        print("Warning: Input text is empty or contains only whitespace.")
        return text

    input_text = f"corriger: {text}"

    # ✅ Troncature pour éviter IndexError
    input_ids = tokenizer.encode(
        input_text,
        return_tensors="pt",
        truncation=True,
        max_length=model.config.max_position_embeddings  # typiquement 1024 pour BART
    )

    if input_ids.shape[-1] == 0:
        print("Warning: Tokenizer produced an empty tensor.")
        return text

    with torch.no_grad():
        outputs = model.generate(
            input_ids,
            max_length=512,
            num_beams=4,
            early_stopping=True
        )

    corrected_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return corrected_text
