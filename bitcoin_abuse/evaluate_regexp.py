# Python file to evaluate BitcoinAbuse reports


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
            return 0
    return 1

