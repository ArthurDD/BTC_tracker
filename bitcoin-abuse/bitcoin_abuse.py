import gc

import torch
from torch.utils.data import DataLoader

from transformers import BertTokenizer
from data_building import build_sets
from NLP_model import train_model
from bert_model import BertBA
from evaluate import evaluate


def main():

    if not torch.cuda.is_available():
        print('WARNING: You may want to change the runtime to GPU for faster training!')
        DEVICE = 'cpu'
    else:
        DEVICE = 'cuda:0'
        gc.collect()
        torch.cuda.empty_cache()  # Clean GPU memory before use

    # tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
    # model = AutoModelForSequenceClassification.from_pretrained("distilbert-base-cased", num_labels=2)

    # Load the tokenizer
    tokenizer = BertTokenizer.from_pretrained('bert-base-cased')

    # Train the model:
    param_list = [{"id_param": 0, "epochs": 3, "batch_size": 16, "learning_rate": 0.00005}]
    # {"id_param": 1, "epochs": 3, "batch_size": 16, "learning_rate": 0.00005,},
    # {"id_param": 2, "epochs": 3, "batch_size": 32, "learning_rate": 0.00005,},
    # {"id_param": 3, "epochs": 3, "batch_size": 32, "learning_rate": 0.00005,}]

    train_dataset, dev_dataset, test_dataset = build_sets(tokenizer)

    for params in param_list:
        print(f"Params used: {params}")
        train_model(train_dataset, dev_dataset, params)

        # Evaluate the model:
        # your saved model name here
        model_name = f'./bitcoin-abuse/models/ht_bert_finetuned_{params["id_param"]}/'
        # model_name = f'./models/ht_bert_best'     # Best trained model
        model = BertBA.from_pretrained(model_name)

        test_loader = DataLoader(dev_dataset)

        # FINAL EVALUATION ON THE TEST DATASET:
        print(f"\n\n--------- EVALUATION ON THE DEV DATASET ---------")
        report = evaluate(model, tokenizer, test_loader)
        print(f"Accurary: {report['accuracy']}")
        print(f"non-PCL f1-score: {report['Fake_Reports']['f1-score']}")
        print(f"PCL f1-score: {report['Genuine_Reports']['f1-score']}")


if __name__ == "__main__":
    main()
