from transformers import BartTokenizer, BartForConditionalGeneration

def summary_text(text):

    print("모델 로드 시작")
    model_sci = BartForConditionalGeneration.from_pretrained("bart_model/finetuning_scitldr")
    tokenizer_sci = BartTokenizer.from_pretrained("bart_model/tokenizer")

    print("요약 시작")
    inputs = tokenizer_sci([text], max_length=1024, return_tensors="pt")
    summary_ids = model_sci.generate(inputs["input_ids"], num_beams=5, min_length=0, max_length=150)
    summary = tokenizer_sci.batch_decode(summary_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]

    return summary



