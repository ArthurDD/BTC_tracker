import gc
import time

import torch
from transformers import TrainingArguments, IntervalStrategy
from bert_model import BertBA, TrainerBA


def train_model(train_dataset, eval_dataset, params):
    # call our custom BERT model and pass as parameter the name of an available pretrained model
    model = BertBA.from_pretrained("bert-base-cased")

    training_args = TrainingArguments(
        output_dir='./bitcoin-abuse/experiment/BA',
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

    trainer.save_model(f"./bitcoin-abuse/models/ht_bert_finetuned_{params['id_param']}/")
