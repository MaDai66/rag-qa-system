import re
import uuid
from typing import List

import jieba
import jieba.posseg

jieba_word_list_cache = [chr(item) for item in range(38, 84)]

for jieba_word in jieba_word_list_cache:
    jieba.add_word('#' + jieba_word + '#')
# r"(?i)\b(?:https?|ftp|tcp|file)://[^\s]+\b",
# 某些不分词数据
# r'"([^"]*)"'
word_pattern_list = [r"v\d+.\d+.\d+",
                     r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"]

remove_chars = '\n , :\'<>！@#￥%……&*（）!@#$%^&*()： ；，/"./'

jieba_remove_flag_list = ['x', 'w']


def get_word_list(text: str):
    result = []
    for pattern in word_pattern_list:
        word_list = re.findall(pattern, text)
        for child_list in word_list:
            for word in child_list if isinstance(child_list, tuple) else [child_list]:
                # 不能有: 所以再使用: 进行分割
                if word.__contains__(':'):
                    item_list = word.split(":")
                    for w in item_list:
                        result.append(w)
                else:
                    result.append(word)
    return result


def replace_word(word_dict, text: str):
    for key in word_dict:
        pattern = '(?<!#)' + re.escape(word_dict[key]) + '(?!#)'
        text = re.sub(pattern, key, text)
    return text


def get_word_key(text: str, use_word_list):
    j_word = next((j for j in jieba_word_list_cache if j not in text and all(j not in used for used in use_word_list)),
                  None)
    if j_word:
        return j_word
    j_word = str(uuid.uuid1())
    jieba.add_word(j_word)
    return j_word


def to_word_dict(word_list: List, text: str):
    word_dict = {}
    for word in word_list:
        key = get_word_key(text, set(word_dict))
        word_dict['#' + key + '#'] = word
    return word_dict


def get_key_by_word_dict(key, word_dict):
    v = word_dict.get(key)
    if v is None:
        return key
    return v


def sanitize_text_for_tsvector(text: str) -> str:
    if not text:
        return ""
    # 替换掉非法字符
    text = text.replace('-\n', '') \
              .replace('\n', ' ') \
              .replace('\r', ' ') \
              .replace('[', '') \
              .replace(']', '') \
              .replace('\\', '') \
              .strip()
    # 移除 URL、Email 等非文本内容（可选）
    text = re.sub(r"(https?|ftp|file)://[^\s]+", "", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", text)
    return text

def to_ts_vector(text: str):
    # 分词
    cleaned_text = sanitize_text_for_tsvector(text)
    tokens = jieba.lcut(cleaned_text, cut_all=True)
    filtered_tokens = [token for token in tokens if token.strip() and token not in remove_chars]
    print(" ".join(filtered_tokens))
    return " ".join(filtered_tokens)


def to_query(text: str):
    cleaned_text = sanitize_text_for_tsvector(text)
    tokens = jieba.lcut(cleaned_text, cut_all=True)
    filtered_tokens = [token for token in tokens if token.strip() and token not in remove_chars]
    result = " | ".join(filtered_tokens)
    return result
