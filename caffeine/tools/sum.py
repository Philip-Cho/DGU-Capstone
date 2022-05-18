from transformers import BartTokenizer, BartForConditionalGeneration
import os

def summary_text(text):
    path = os.getcwd()

    print("모델 로드 시작")
    model_sci = BartForConditionalGeneration.from_pretrained(os.path.join(path, "bart_model/finetuning_scitldr_3epoch"),use_auth_token=True)
    tokenizer_sci = BartTokenizer.from_pretrained(os.path.join(path, "bart_model/tokenizer"),use_auth_token=True)

    print("요약 시작")
    inputs = tokenizer_sci([text], max_length=1024, return_tensors="pt")
    summary_ids = model_sci.generate(inputs["input_ids"], num_beams=5, min_length=0, max_length=150)
    summary = tokenizer_sci.batch_decode(summary_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]

    return summary



