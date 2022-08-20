import gc
import sys
import time
import traceback

import torch
from torch.utils.data import DataLoader

from transformers import BertTokenizer, TrainingArguments, IntervalStrategy
from data_building import build_sets
from evaluate import evaluate
from bert_model import BertBA, TrainerBA
from logger import Logger, ErrorLogger


def train_model(train_dataset, eval_dataset, params):
    # call our custom BERT model and pass as parameter the name of an available pretrained model
    model = BertBA.from_pretrained("bert-base-cased")

    training_args = TrainingArguments(
        output_dir='./bitcoin_abuse/experiment/BA',
        learning_rate=params["learning_rate"],
        logging_steps=100,
        evaluation_strategy="steps",
        eval_steps=100,
        save_strategy=IntervalStrategy.NO,
        per_device_train_batch_size=params["batch_size"],  # 32 original
        per_device_eval_batch_size=params["batch_size"],  # 32 original
        num_train_epochs=params["epochs"],
    )
    trainer = TrainerBA(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=train_dataset.collate_fn
    )

    print("Clearing GPU memory")

    gc.collect()
    torch.cuda.empty_cache()  # Clean GPU memory before use

    time.sleep(2.0)

    print("\n\n\n------- Starting Training -------\n")

    torch.cuda.memory_stats_as_nested_dict()

    trainer.train()

    trainer.save_model(f"./bitcoin_abuse/models/ht_bert_finetuned_{params['id_param']}/")


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
    param_list = [{"id_param": 0, "epochs": 1, "batch_size": 32, "learning_rate": 0.0005},
                  {"id_param": 1, "epochs": 1, "batch_size": 16, "learning_rate": 0.0005},]
                  # {"id_param": 2, "epochs": 3, "batch_size": 32, "learning_rate": 0.00005},
                  # {"id_param": 3, "epochs": 3, "batch_size": 16, "learning_rate": 0.00005}]

    train_dataset, dev_dataset, test_dataset = build_sets(tokenizer)

    # param_list = {}
    for params in param_list:
        print(f"Params used: {params}")
        train_model(train_dataset, dev_dataset, params)

        # Evaluate the model:
        model_name = f'./bitcoin_abuse/models/ht_bert_finetuned_{params["id_param"]}/'
        model = BertBA.from_pretrained(model_name)

        test_loader = DataLoader(dev_dataset)

        # FINAL EVALUATION ON THE TEST DATASET:
        print(f"\n\n--------- EVALUATION ON THE DEV DATASET ---------")
        report = evaluate(model, tokenizer, test_loader)
        print(f"Accurary: {report['accuracy']}")
        print(f"Fake_reports f1-score: {report['Fake_Reports']['f1-score']}")
        print(f"Genuine_reports f1-score: {report['Genuine_Reports']['f1-score']}")


if __name__ == "__main__":
    sys.stdout = Logger()
    sys.stderr = ErrorLogger(sys.stdout)
    try:
        main()
    except:
        traceback.print_exc(file=sys.stderr)
    sys.stdout.terminate()

