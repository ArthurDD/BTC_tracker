import torch
from sklearn.metrics import classification_report
from tqdm import tqdm


def predict_BA(report_input):
    """
    Predicts the label of the input according to the model.
    :param report_input: texts to predict label of.
    :param tokenizer: tokenizer used
    :param model: trained model
    :return: {'prediction': _, 'confidence': _}
    """
    keywords = ['recover', 'good work', 'call', '+1 (']  # www, 'http'
    for keyword in keywords:
        if keyword in report_input:
            # print(f"False report\n")
            return 0
    # print("Real report\n")
    return 1


def evaluate(model, tokenizer, data_loader):
    """

    :param model: trained model
    :param tokenizer: tokenizer used
    :param data_loader: data to predict label of
    :return: dict of evaluation metrics of the predictions on the dataset.
    """
    tot_labels, preds = run_evaluation(model, tokenizer, data_loader)

    # with the saved predictions and labels we can compute accuracy, precision, recall and f1-score
    report = classification_report(tot_labels, preds, target_names=["Fake_Reports", "Genuine_Reports"],
                                   output_dict=True)
    return report


def run_evaluation(model, tokenizer, data_loader):
    preds = []
    true_labels = []
    with torch.no_grad():
        for data in tqdm(data_loader):
            tweets = data['text']
            labels = data['label']

            pred = predict_BA(tokenizer, model, tweets)

            preds.append(pred['prediction'].tolist())
            true_labels.append(labels.tolist())
    return true_labels, preds
