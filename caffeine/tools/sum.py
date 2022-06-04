from transformers import BartTokenizer, BartForConditionalGeneration
import os, re
import torch

def tokenize_split(text, tokenizer):
    split_size = 800   # 클수록 global, 작을수록 local information 더 담을 수 있음
    tokens = tokenizer([text], return_tensors='pt', add_special_tokens=False)
    input_ids_chunks = list(tokens['input_ids'][0].split(split_size))
    attention_mask_chunks = list(tokens['attention_mask'][0].split(split_size))

    for i in range(len(input_ids_chunks)):
        input_ids_chunks[i] = torch.cat([torch.tensor([0]), input_ids_chunks[i], torch.tensor([2])])
        attention_mask_chunks[i] = torch.cat([torch.tensor([1]), attention_mask_chunks[i], torch.tensor([1])])

        pad_len = 1024 - len(input_ids_chunks[i])
        if pad_len > 0:
            input_ids_chunks[i] = torch.cat([input_ids_chunks[i], torch.tensor([0] * pad_len)])
            attention_mask_chunks[i] = torch.cat([attention_mask_chunks[i], torch.tensor([0] * pad_len)])

    input_ids = torch.stack(input_ids_chunks)
    att_masks = torch.stack(attention_mask_chunks)

    return {'input_ids': input_ids, 'attention_mask': att_masks}


def process_text(pre_summary):
    summary = pre_summary.replace('\n', ' ')
    if 'we propose' in summary or 'we present' in summary:
        summary = summary.replace('we propose', 'this lecture is about')
        summary = summary.replace('we present', 'this lecture is about')
    if 'in this paper' in summary:
        summary = summary.replace('in this paper', 'in this course')

    ## 공백 처리(마침표/쉼표 앞뒤 공백), 대문자 변경(문장 첫문자 소문자)
    # 마침표 기준으로 문장 나눠주기
    summary_split = summary.split('.')
    pro_summary = ''
    for sent in summary_split:
        sent = sent.strip()
        if len(sent) <= 1:
            continue
        if sent[0].islower():
            sent = sent[0].upper() + sent[1:]
        sent += '. '
        while '  ' in sent:
            sent = sent.replace('  ', ' ')
        sent = sent.replace(' ,', ',')
        pro_summary += sent

    return pro_summary


def summary_text(text, model, tokenizer, max_length=None):
    print("요약 시작")
    text = text.replace('\n', ' ')
    inputs = tokenize_split(text, tokenizer)
    n_seg = inputs['input_ids'].shape[0]  # max_length로 split된 개수
    summary = ''
    for i in range(n_seg):
        print(n_seg - i, end=' >> ')
        summary_ids = model.generate(input_ids=inputs["input_ids"][i].reshape(1, -1),
                                     attention_mask=inputs['attention_mask'][i].reshape(1, -1),
                                     max_length=max_length)
        summary_seg = tokenizer.batch_decode(summary_ids,
                                             skip_special_tokens=True,
                                             clean_up_tokenization_spaces=False)[0]

        summary += summary_seg
    print(0)
    summary_end = process_text(summary)

    return summary_end


def sum_model_load():
    print("모델 로드 시작")
    model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")
    tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
    return model, tokenizer
