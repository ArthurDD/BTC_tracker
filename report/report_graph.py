import csv
import numpy as np


def read_csv(filename):
    with open(filename, "r") as f:
        csv_content = csv.reader(f)
        header = next(csv_content)
        rows = [row for row in csv_content]

    return header, rows


def build_graph(header, rows):
    years = [i for i in range(2013, 2023)]
    months = [i for i in range(1, 13)]

    data_dict = {key: [] for key in header if "date" not in key.lower()}

    entries = []

    for year in years:
        for month in months:
            if month < 10:
                f_month = f"0{month}"
            else:
                f_month = month
            if year != 2022 or month <= 8:
                entries.append(f"{year}-{f_month}")

    for entry in entries:
        for i, key in enumerate(data_dict.keys()):
            data_dict[key].append(np.average([int(row[i + 1]) for row in rows if entry in row[0]]))

    write_csv(data_dict, entries)


def write_csv(data_dict, entries):
    header = list(data_dict.keys())
    lines = np.around([[data_dict[key][i] for key in header]for i in range(len(list(data_dict.values())[0]))], 2).tolist()
    # lines = np.insert(lines, 0, entries, axis=0)

    for i, entry in enumerate(entries):
        lines[i].insert(0, entry)
    header.insert(0, "date")
    filename = 'average_input_tx_monthly.csv'
    with open(filename, 'w', newline="") as f:
        csvwriter = csv.writer(f)  # 2. create a csvwriter object
        csvwriter.writerow(header)  # 4. write the header
        csvwriter.writerows(lines)  # 5. write the rest of the data


if __name__ == "__main__":
    header, rows = read_csv("average_input_tx.csv")
    build_graph(header, rows)
