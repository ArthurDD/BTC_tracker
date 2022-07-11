import random
from langdetect import detect
import json
import langdetect.lang_detect_exception
import pandas as pd

from report_dataset import ReportDataset
import numpy as np


def split_sets(dataset, ratio=0.8):
    """ ratio of 0.8 means 80% of the set will be the training set, and dev_set and tes_set will be equally share the
     remaining 20%
     """
    train_set_texts = []
    train_set_labels = []
    dev_set_texts = []
    dev_set_labels = []
    test_set_texts = []
    test_set_labels = []

    dev_ratio = ratio + (1 - ratio) / 2     # 0 < train_ratio < dev_ratio < 1
    print(f"Dev_ratio is: {dev_ratio}")

    for elt in zip(dataset['description'].tolist(), dataset['label'].tolist()):
        rand = random.random()
        if dev_ratio > rand > ratio:  # If it needs to go in the dev set
            dev_set_texts.append(elt[0])
            dev_set_labels.append(elt[1])
        elif rand >= dev_ratio:
            test_set_texts.append(elt[0])
            test_set_labels.append(elt[1])
        else:
            train_set_texts.append(elt[0])
            train_set_labels.append(elt[1])

    return {"texts": train_set_texts, "labels": train_set_labels}, \
           {"texts": dev_set_texts, "labels": dev_set_labels}, \
           {"texts": test_set_texts, "labels": test_set_labels}


def build_sets(tokenizer):
    """
    :param tokenizer: tokenizer used to tokenize the data
    :return: train_dataset, dev_dataset, test_dataset, experiments
    """
    # {'texts': texts, 'labels': labels}
    dataset = pd.read_csv('./bitcoin-abuse/dataset.csv')

    # Split train dataset in train and test dataset:
    train_set, dev_set, test_set = split_sets(dataset, 0.8)

    # Data augmentation happens inside PatronizingDataset class.
    train_dataset = ReportDataset(tokenizer, train_set)
    dev_dataset = ReportDataset(tokenizer, dev_set)
    test_dataset = ReportDataset(tokenizer, test_set)

    print(f"\nSize of training_set: {len(train_dataset.labels)}\n"
          f"Fake reports: {len([elt for elt in train_dataset.labels if elt == 0])}\n"
          f"Genuine reports: {len([elt for elt in train_dataset.labels if elt == 1])}\n"
          f"Ratio: {np.round(len([elt for elt in train_dataset.labels if elt == 0]) / len(train_dataset.labels), 3)*100}% - "
          f"{np.round(len([elt for elt in train_dataset.labels if elt == 1]) / len(train_dataset.labels), 3)*100}%\n"
          )

    print(f"Size of dev_set: {len(dev_dataset.labels)}\n"
          f"Fake reports: {len([elt for elt in dev_dataset.labels if elt == 0])}\n"
          f"Genuine reports: {len([elt for elt in dev_dataset.labels if elt == 1])}\n"
          f"Ratio: {np.round(len([elt for elt in dev_dataset.labels if elt == 0]) / len(dev_dataset.labels), 3)*100}% - "
          f"{np.round(len([elt for elt in dev_dataset.labels if elt == 1]) / len(dev_dataset.labels), 3)*100}%\n\n"
          )

    return train_dataset, dev_dataset, test_dataset


# Functions to build dataset
def retrieve_data(overwrite=True):
    with open("./credentials.json", "r") as f:
        dic = json.load(f)
        token = dic['bitcoinabuse']['token']
    url = f"https://www.bitcoinabuse.com/api/download/30d?api_token={token}"

    df = pd.read_csv(url)
    if overwrite:
        df.to_csv('out.csv')
    else:
        df.to_csv('out.csv', mode='w', index=False, header=False)

    print(url)


def find_language(row):
    if row['description'] and " " in row['description']:
        try:
            # print(f"Desc: {row['description']}")
            lang = detect(row['description'])
            # print(f"Lang: {lang}\n")
            return lang
        except langdetect.lang_detect_exception.LangDetectException:
            return "-"
    else:
        return "-"


def set_label(row):
    keywords = ['www', 'recover', 'http', 'good work', 'call', '+1 (']
    # print(f"Desc: {row['description']}")
    for keyword in keywords:
        if keyword in row['description']:
            # print(f"False report\n")
            return 0
    # print("Real report\n")
    return 1


def filter_data():
    """
    Removes non-english lines and only keeps the 2 columns we are interested in.
    Fills dataset.csv
    :return: None
    """

    df = pd.read_csv('out.csv')
    df = df.filter(items=['description'])
    df['lang'] = df.apply(find_language, axis=1)
    df = df.query("lang == 'en'")
    df = df.filter(items=['description'])

    # Set labels
    df['label'] = df.apply(set_label, axis=1)

    df.to_csv('dataset.csv')
    print(df.head())
    print(df.size)


def data_stats():
    df = pd.read_csv('./bitcoin-abuse/dataset.csv')
    print(df.label.value_counts())