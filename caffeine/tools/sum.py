from transformers import BartTokenizer, BartForConditionalGeneration
import os

def summary_text(text,model,tokenizer):

    print("요약 시작")
    inputs = tokenizer([text], max_length=1024, return_tensors="pt")
    summary_ids = model.generate(inputs["input_ids"], num_beams=5, min_length=128, max_length=256)
    summary = tokenizer.batch_decode(summary_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]

    return summary

def sum_model_load():
    print("모델 로드 시작")
    model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")
    tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
    return model, tokenizer


