from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize, sent_tokenize
from google.cloud import storage

import random
import re
import numpy as np
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64


# 2) Preprocess the sentences
def preprocess_sents(sentences, stop_words):
    sents_after = []  # stop_words 제거, lower()한 list of sentences
    for sent in sentences:
        words = word_tokenize(sent)
        sents_after.append(
            ' '.join([word.lower() for word in words if word.lower() not in stop_words and len(word) > 1]))
        sents_after = [s for s in sents_after if s != '']
    return sents_after


# 3-1) Build the sentence graph
def build_sent_graph(sents, tfidf):  # 문장 리스트 -> tf-idf matrix -> sentence graph
    graph_sentence = []
    tfidf_mat = tfidf.fit_transform(sents).toarray()
    graph_sentence = np.dot(tfidf_mat, tfidf_mat.T)
    return graph_sentence


# 4) Calculate the ranks of each sentence or word
def get_ranks(graph, d=0.85):
    A = graph
    matrix_size = A.shape[0]
    for id in range(matrix_size):
        A[id, id] = 0  # diagonal 부분 -> 0으로 바꿔줌(diagonal matrix)
        link_sum = np.sum(A[:, id])
        if link_sum != 0:
            A[:, id] /= link_sum
        A[:, id] *= -d
        A[id, id] = 1

    B = (1 - d) * np.ones((matrix_size, 1))
    ranks = np.linalg.solve(A, B)

    return {idx: r[0] for idx, r in enumerate(ranks)}


# 5-1) Get the list of keywords
def get_keywords(text, kw_model=KeyBERT('all-MiniLM-L12-v2'), word_num=10, stopwords_list=None):
    stopwords_list = stopwords_list
    keywords = kw_model.extract_keywords(text, top_n=word_num,
                                         keyphrase_ngram_range=(1, 1),
                                         stop_words=stopwords_list)
    return keywords


# 5-2) Get the list of keysentences
def get_keysents(sorted_sent_idx, sentences, sent_num=2):
    keysents = []
    index = []
    for idx in sorted_sent_idx[:sent_num]:
        index.append(idx)
    for idx in index:
        keysents.append(sentences[idx])

    return keysents


# 6) Final: Get the sentence with blank, answer sentence, answer word
def keysents_blank(keywords: list, keysents: list):
    keysent = ''  # blank 만들 keysent
    keysent_blank = ''  # blank 만든 keysent
    keyword_keysent = ''  # keysent의 blank에 들어갈 keyword
    lowest_weight = 23  # 가장 작은 weight(초기값: 최대 weight+1)

    for sent in keysents:
        sent_weight = keysents.index(sent) + 1

        keyword = ''
        for word in keywords:
            if word in sent:
                keyword = word
                break  # keywords 리스트는 앞의 index일수록 순위가 높은 키워드 -> 문장에 존재하면 break
        if keyword != '':
            word_weight = keywords.index(keyword) + 1
        else:
            word_weight = 23

        weight = sent_weight + word_weight
        if weight < lowest_weight:
            lowest_weight = weight
            keysent = sent
            keyword_keysent = keyword

    keysent_blank = keysent.replace(keyword_keysent, '__________')
    print("키워드 추출 완료")
    return {'keywords': keywords, 'sentence_blank': keysent_blank, 'sentence': keysent, 'answer': keyword_keysent}


def keysents_blank_rd(keywords: list, keysents: list):
    qas = []
    for keysent in keysents:
        words_keysent = word_tokenize(keysent)
        for word in words_keysent:
            for keyword in keywords:
                if re.findall(keyword, word, re.IGNORECASE) != [] and words_keysent.index(word) != 0:
                    sent_blank = keysent.replace(' ' + word, ' __________')  # 'ai'같은 단어 빈칸 방지
                elif re.findall(keyword, word, re.IGNORECASE) != [] and words_keysent.index(word) == 0:
                    sent_blank = keysent.replace(word + ' ', '__________ ')  # 문장 첫단어
                else:
                    continue
                qa = {'sentence_blank': sent_blank, 'sentence': keysent, 'answer': word}
                qas.append(qa)

    random.shuffle(qas)  # random!

    qas_5 = {}
    n=len(qas) if len(qas)<5 else 5   # 생성된 문제가 5개 이하일 때
    for i in range(5):
        qas_5['sentence_blank{}'.format(i + 1)] = qas[i]['sentence_blank'] if i < len(qas) else None
        qas_5['sentence{}'.format(i + 1)] = qas[i]['sentence'] if i < len(qas) else None
        qas_5['answer{}'.format(i + 1)] = qas[i]['answer'] if i < len(qas) else None
        print(qas_5)

    return qas_5


def postprocess_keywords(keywords):
    for kw in keywords:
        if len(kw) < 5 or kw not in keywords:
            continue
        idx = keywords.index(kw)
        n_gram = int(len(kw) * 0.7)  # n_gram: 단어의 70% 이상 겹치면 out
        window = [kw[i:i + n_gram] for i in range(len(kw) - n_gram + 1)]
        for w in window:
            keywords = keywords[:idx + 1] + [keyword for keyword in keywords[idx + 1:] if w not in keyword]
    return keywords[:10]


def load_key_model():
    model = KeyBERT('all-MiniLM-L12-v2')
    return model


def plot_keywords(key_dict=dict):
    keywords = key_dict['keywords']
    weights = key_dict['weights']
    x = [i for i in range(10)]
    y = [i for i in range(10)]
    random.shuffle(x)
    random.shuffle(y)
    df = pd.DataFrame(zip(keywords, weights), columns=['keywords', 'weights'])
    # plotting
    plt.figure(figsize=(10, 10))
    plt.tick_params(left=False, right=False, labelleft=False,
                    labelbottom=False, bottom=False)
    sns.despine(bottom=True, left=True)

    for i in range(10):
        if df.loc[i,'weights']* 50 < 10:
           fontdict={'color':'white', 'size':df.loc[i,'weights'] * 100}
        else:
            fontdict={'color':'white', 'size':df.loc[i,'weights'] * 50}
        plt.text(x=x[i], y=y[i],
                 verticalalignment='center',
                 horizontalalignment='center',
                 s=df.loc[i, 'keywords'],
                 fontdict=fontdict)
    #     plt.bar(x=weights, height=keywords)
    #     sns.barplot(x=weights, y=keywords, palette='Reds')
    sns.scatterplot(x, y, alpha=0.6, linewidth=0,
                    s=[w*80000 for w in weights],
                    hue=weights,
                    palette='Paired')  #coolwarm, Paired, flare, rocket
    plt.xlim(-3,13)
    plt.ylim(-3,13)
    plt.legend([], [], frameon=False)

    plot_file = BytesIO()
    plt.savefig(plot_file, format='png')
    encoded_file = plot_file.getvalue()
    encoded_file = base64.b64encode(encoded_file)
    encoded_file = encoded_file.decode('utf-8')
    return encoded_file


def key_question(text_all, model):
    sent_ngram = 2
    stopwords_path = 'text/stop_words_english.txt'
    print("키워드 추출 시작")

    text = text_all
    sentences = sent_tokenize(text)
    sentences = [sent.replace('\n', ' ') for sent in sentences]

    with open(stopwords_path, 'r', encoding='utf-8') as f:
        stop_words = f.readlines()
        stop_words = [word.strip() for word in stop_words]

    tfidf = TfidfVectorizer(ngram_range=(1, sent_ngram))
    sents_after = preprocess_sents(sentences, stop_words)
    sent_graph = build_sent_graph(sents_after, tfidf)
    sent_rank_idx = get_ranks(sent_graph)  # 문장 가중치 그래프
    sorted_sent_idx = sorted(sent_rank_idx,  # 문장 가중치 그래프-가중치 작은 차순 정렬
                             key=lambda k: sent_rank_idx[k], reverse=True)
    keysents = get_keysents(sorted_sent_idx, sentences, sent_num=10)
    kw_model = model

    keywords_w_weight = get_keywords(text, kw_model, 20, stop_words)  # (키워드, 중요도) 20개
    keywords_20 = [word_tup[0] for word_tup in keywords_w_weight]  # 키워드만 20개
    #     keywords_weights_20 = [word_tup[1] for word_tup in keywords_w_weight]
    print('키워드 추출 완료')

    qa = keysents_blank_rd(keywords_20[:10],
                           keysents)  # {'sentence_blank':sent_blank, 'sentence':keysent, 'answer':keyword}
    keywords = postprocess_keywords(keywords_20)  # 복수/단수 or 동사/명사 차이의 유사도 높은 단어 처리 후 10개 리턴
    weights = [w for (kw, w) in keywords_w_weight if kw in keywords]
    qa['keywords'] = keywords
    qa['weights'] = weights

    return qa  # return qa, keywords : 데이터 적재시
