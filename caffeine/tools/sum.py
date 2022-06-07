from transformers import BartTokenizer, BartForConditionalGeneration
import os, re
import torch

def tokenize_split(text, tokenizer):
    split_size = 1000
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
    replace_sents_path = 'text/replace_sentences.txt'
    summary = pre_summary

    with open(replace_sents_path, 'r', encoding='utf-8') as f:
        replace_sents = f.readlines()
        replace_sents = [word.strip() for word in replace_sents]

    if 'we propose' in summary or 'we present' in summary:
        summary = summary.replace('we propose', 'this lecture is about')
        summary = summary.replace('we present', 'this lecture is about')
    if 'in this paper' in summary or 'in this article' in summary:
        summary = summary.replace('in this paper', 'in this lecture')
        summary = summary.replace('in this article', 'in this lecture')
    for sent in replace_sents:
        if sent[:3]=='the' and sent[-2:]=='is':   # the first part is
            summary = summary.replace(sent, 'this part is')
        elif 'published' in sent or 'extension' in sent:   #
            summary = summary.replace(sent, '')   # this paper is an extension of
        elif 'and in the' in sent:   # and in the first part
            summary = summary.replace(sent, 'and')
        elif sent[:7]=='this is' and sent[-2:]=='on':   # this is the {} in a series of {} {} on
            summary = summary.replace(sent, 'this is about')

    ## 공백 처리(마침표/쉼표 앞뒤 공백), 대문자 변경(문장 첫문자 소문자)
    # 마침표 기준으로 문장 나눠주기
    summary_split = summary.split('.')
    if summary[-1] != '.':
        summary_split = summary_split[:-1]
    pro_summary = ''
    for sent in summary_split:
        sent = sent.strip()
        if len(sent) <= 1 or sent.count('#') > 1 or '* keyword' in sent:
            continue
        if sent[0].islower():
            sent = sent[0].upper() + sent[1:]
        if sent[0] == '*':
            sent = sent[2:]
        sent += '. '  # punctuation
        while '  ' in sent:
            sent = sent.replace('  ', ' ')
        sent = sent.replace(' ,', ',')
        sent = sent.replace(',.', '.')

        pro_summary += sent

    return pro_summary


def summary_text(text, model, tokenizer, max_length=100):
    print("요약 시작=D")
    text = text.replace('\n', ' ')
    inputs = tokenize_split(text, tokenizer)

    n_seg = inputs['input_ids'].shape[0]  # max_length로 split된 개수
    summary_list = []
    summary_part = ''
    summary = ''

    #     if n_seg > 4:  ##
    #         summary += '[Part 1]\n'  ##
    #         n = 2  ##

    for i in range(n_seg):
        print(n_seg - i, end=' >> ')
        summary_ids = model.generate(input_ids = inputs["input_ids"][i].reshape(1, -1),
                                     attention_mask = inputs['attention_mask'][i].reshape(1, -1),
                                     max_length = max_length
                                    )
        summary_seg = tokenizer.batch_decode(summary_ids,
                                         skip_special_tokens = True,
                                         clean_up_tokenization_spaces = False)[0]

        if i % 5 == 0 and i != 0:  ##
            summary_list.append(summary_part)
            summary_part = ''

        summary_seg = summary_seg.replace('\n', '')
        summary_seg = process_text(summary_seg)

        summary_part += summary_seg  # 각 part summary(string)
        summary += summary_seg  # 전체 summary(string)

    summary_list.append(summary_part)  #
    print(0)
    #    summary_end = process_text(summary)

    return summary_list


def sum_model_load():
    print("모델 로드 시작")
    path = os.getcwd()
    model = BartForConditionalGeneration.from_pretrained(os.path.join(path, "bart_model/finetuning_cnn_pubmed_arxiv"))
    tokenizer = BartTokenizer.from_pretrained(os.path.join(path, "bart_model/finetuning_cnn_pubmed_arxiv"))
    return model, tokenizer
