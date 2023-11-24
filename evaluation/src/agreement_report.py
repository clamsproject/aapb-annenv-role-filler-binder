# Imports 
from collections import namedtuple, defaultdict
import csv
import os
import json 


def read_in_results(fname: str) -> dict:

    out= {}
    with open(fname, 'r', encoding='utf8') as f:
        reader = csv.reader(f)
        fields = next(reader)[1:]
        for row in reader:
            out[row[0]] = dict(zip(fields, row[1:]))
    return out

def get_metrics(results_dict):
    output_dict={}
    metrics = ["zero_agreement",
               "perfect_agreement",
               "averages"]
    
    num_docs = len(results_dict)
    values = defaultdict(float)

    for guid, results in results_dict.items():
        if float(results["total"]) == 0:
            values["zeros"] += 1

        if float(results["total"]) == 1:
            values["perfect"] += 1

        values["k_total"] += float(results["keys"])
        values["v_total"] += float(results["vals"])
        values["p_total"] += float(results["pairs"])
        values["t_total"] += float(results["total"])
    
    output_dict.update({"zero_agreement": values["zeros"] / num_docs,
                        "perfect_agreement": values["perfect"] / num_docs,
                        "averages": {"keys": values["k_total"] / num_docs,
                                     "vals": values["v_total"] / num_docs,
                                     "pairs": values["p_total"] / num_docs,
                                     "total": values["t_total"] / num_docs}})
    return output_dict




def process_file(fname):
    results = get_metrics(read_in_results(f"./results/noskips/{fname}"))
    print(results)
    fname = os.path.basename(fname)
    with open(f"{fname}_agreement_report.json", 'w', encoding='utf8') as f:
        json.dump(results, f, indent=2)

def main():
    fnames = ["product-nofuzzy-results.csv",
              "product-simplefuzzy-results.csv",
              "average-nofuzzy-results.csv",
              "average-simplefuzzy-results.csv"]

    for name in fnames:
        process_file(name)





if __name__ == "__main__":
    main()