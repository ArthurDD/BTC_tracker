import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate
import numpy as np

import seaborn as sns


def build_graph(log_name):
    """
    Creates a graph according to the log in arguments.
    :param log_name: str - name of the log inside the logs/ folder.
    :return: Nothing, plots the graph.
    """
    training_data, dev_data = parse_log(log_name)
    loss_train = []
    loss_dev = []
    for i in range(len(training_data)):
        loss_train.append([])
        loss_dev.append([])
        for elt in training_data[i]:
            loss_train[i].append((elt['epoch'], elt['loss']))
        for elt in dev_data[i]:
            loss_dev[i].append((elt['epoch'], elt['eval_loss']))

    # Use plot styling from seaborn.
    sns.set(style='darkgrid')

    if len(training_data) == 1:
        # Increase the plot size and font size.
        sns.set(font_scale=1.5)
        plt.rcParams["figure.figsize"] = (12, 6)

        # Plot the learning curve.
        plt.plot([elt[0] for elt in loss_train[0]], [elt[1] for elt in loss_train[0]], 'b-o', label="Training")
        plt.plot([elt[0] for elt in loss_dev[0]], [elt[1] for elt in loss_dev[0]], 'g-o', label="Validation")
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.legend()

    else:
        figure, axis = plt.subplots(2, 2)

        # Labels here are useless
        axis[0, 0].plot([elt[0] for elt in loss_train[0]], [elt[1] for elt in loss_train[0]], 'b-o', label="Training")
        axis[0, 0].plot([elt[0] for elt in loss_dev[0]], [elt[1] for elt in loss_dev[0]], 'g-o', label="Validation")

        axis[0, 1].plot([elt[0] for elt in loss_train[1]], [elt[1] for elt in loss_train[1]], 'b-o', label="Training")
        axis[0, 1].plot([elt[0] for elt in loss_dev[1]], [elt[1] for elt in loss_dev[1]], 'g-o', label="Validation")

        if len(training_data) > 2:
            axis[1, 0].plot([elt[0] for elt in loss_train[2]], [elt[1] for elt in loss_train[2]], 'b-o',
                            label="Training")
            axis[1, 0].plot([elt[0] for elt in loss_dev[2]], [elt[1] for elt in loss_dev[2]], 'g-o', label="Validation")

        if len(training_data) > 3:
            axis[1, 1].plot([elt[0] for elt in loss_train[3]], [elt[1] for elt in loss_train[3]], 'b-o',
                            label="Training")
            axis[1, 1].plot([elt[0] for elt in loss_dev[3]], [elt[1] for elt in loss_dev[3]], 'g-o', label="Validation")

        # Add a big axe, hide frame
        figure.add_subplot(111, frameon=False)
        # Hide tick and tick label of the big axes
        plt.tick_params(labelcolor='none', top=False, bottom=False, left=False, right=False)
        plt.grid(False)

        # Display the legend
        plt.plot(0, 0, 'b-.', label='Training')
        plt.plot(0, 0, 'g-.', label='Validation')
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.legend(loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=2)

    plt.show()

    # table(log_name)


def parse_log(log_name):
    """
    Parses the logfile to get eval and training data.
    :param log_name:
    :return:
    """
    with open(f"./bitcoin-abuse/logs/{log_name}", 'r') as f:
        param_list = []
        training_data = []
        dev_data = []
        index = -1
        for line in f.readlines():
            if "Params used: " in line:
                param_list.append(line.strip()[line.strip().find("{'epochs': ")])
                training_data.append([])
                dev_data.append([])
                index += 1
            if "{'loss'" in line:
                training_data[index].append(eval(line.strip()))
            elif "{'eval_loss'" in line:
                dev_data[index].append(eval(line.strip()[line.strip().find("{'eval_loss'"):]))

    return training_data, dev_data


def table(log_name):
    """ Creates a table - Only works if there is only one model that has been trained in the log file."""
    training_data, dev_data = parse_log(log_name)
    training_stats = []
    for k in range(len(training_data)):
        training_stats.append([])
        for i in range(len(training_data[k])):
            training_stats[k].append({'train_loss': float(training_data[k][i]['loss']),
                                      'epoch': training_data[k][i]['epoch'],
                                      'eval_loss': dev_data[k][i]['eval_loss']
                                      })

    # Create a DataFrame from our training statistics.
    df_stats = pd.DataFrame(data=training_stats)
    df_stats = np.round(df_stats, decimals=3)

    # Use the 'epoch' as the row index.
    df_stats = df_stats.set_index('epoch')

    # Display the table.
    print(tabulate(df_stats, headers='keys', tablefmt='latex'))


build_graph("BA_log_2022-07-11_18:12:43.txt")  # log_name)
