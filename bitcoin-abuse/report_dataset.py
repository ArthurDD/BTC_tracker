import random
import torch
from torch.utils.data import Dataset


class BADataset(Dataset):

    def __init__(self, tokenizer, input_set):
        self.tokenizer = tokenizer

        # Shuffle the data to avoid the PCL examples to be grouped together
        shuffle_l = random.sample(list(zip(input_set['texts'], input_set['labels'])), len(input_set['texts']))

        self.texts = [elt[0] for elt in shuffle_l]
        self.labels = [elt[1] for elt in shuffle_l]

    def collate_fn(self, batch):
        texts = []
        labels = []

        for b in batch:
            texts.append(b['text'])
            labels.append(b['label'])

        # The maximum sequence size for BERT is 512 but here the tokenizer truncate sentences longer than 256 tokens.
        encodings = self.tokenizer(texts, return_tensors='pt', padding=True, truncation=True, max_length=128)
        encodings['labels'] = torch.tensor(labels)

        return encodings

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        item = {'text': self.texts[idx],
                'label': self.labels[idx]}
        return item
