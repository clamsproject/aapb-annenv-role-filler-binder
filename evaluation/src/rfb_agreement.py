# Role-Filler Binding
# Inter-Annotator Agreement Calculations
"""
 Binary agreement calculation using fuzzy match to associate kv pairs 
 within frames and various aggregation functions to create an IOU agreement
 metric for the pairings.
 """

# ====================================|
# Imports
import argparse 
from collections import defaultdict
import csv 
from thefuzz import fuzz, process
import json
import os

import pprint
# Imports - Typing
from typing import Dict, List, Union
from os import PathLike
# ====================================|
def load_data(annotator_a_dir: Union[str, PathLike],
              annotator_b_dir: Union[str, PathLike],
              include_skips  : bool = False):
    """TODO: docstring
    Load in data from two annotators"""
    a_annotations = []
    b_annotations = []
    for fname in os.listdir(annotator_a_dir):
        filename = os.path.join(annotator_a_dir, fname)
        with open(filename, 'r', encoding='utf8') as f:
            a_annotations.append(json.load(f))

    for fname in os.listdir(annotator_b_dir):
        filename = os.path.join(annotator_b_dir, fname)
        with open(filename, 'r', encoding='utf8') as f:
            b_annotations.append(json.load(f))

    if not include_skips:
        a_annotations = filter(lambda x: "_skip_reason" not in x, a_annotations)
        b_annotations = filter(lambda x: "_skip_reason" not in x, b_annotations)
    
    frames_dict = defaultdict(dict)

    for frame_anno in a_annotations:
        id = frame_anno["_image_id"]
        frames_dict[id].update({"A": {k:v 
                                      for k, v in frame_anno.items() 
                                      if k != "_image_id" and (k != "" and v != [])}})
    for frame_anno in b_annotations:
        id = frame_anno["_image_id"]
        frames_dict[id].update({"B": {k:v 
                                      for k, v in frame_anno.items() 
                                      if k != "_image_id" and (k != "" and v != [])}})   
                     
    return frames_dict
    
def make_pairs(anno_one, anno_two):
    """TODO: Docstring"""
    a_pairs = []
    b_pairs = []

    for key, vals in anno_one.items():
        if len(vals) == 1:
            a_pairs.append((key, vals[0]))
        else:
            a_pairs.extend((key, v) for v in vals)
    for key, vals in anno_two.items():
        if len(vals) == 1:
            b_pairs.append((key, vals[0]))
        else:
            b_pairs.extend((key, v) for v in vals)
    a_pairs.sort(key = lambda x: x[0])
    b_pairs.sort(key = lambda x: x[0])
    return a_pairs, b_pairs

def assoc_pairs(anno_one, anno_two, threshold: int = 3, verbose=False) -> None:
    """Create the associative pairs for agreement 
    comparison. 
    """
    a_pairs, b_pairs = make_pairs(anno_one, anno_two)
    return a_pairs, b_pairs

def pair_iou(seq_one, seq_two, threshold=90):
    """Intersect Over Union for the matched pairs"""
    intersection = 0
    union = 0
    for x in seq_one:
        threshold_avg = 0
        test_pairs = [y for y in seq_two]
        similarity = get_max_similarity(x, test_pairs)
        if similarity[1] > threshold:
            intersection += similarity[1] / 100
        union += 1
        threshold_avg /= len(seq_two)
    return intersection / union

def get_max_similarity(gold, test_seq):
    comp_gold = "_".join(gold)
    comp_seq = ["_".join(pair) for pair in test_seq]
    match = process.extractBests(comp_gold, comp_seq, limit=1)
    return match[0]

def get_agreement(annotations, skips=False):
    """Calculate IOU agreement over KV pairs"""

    def get_iou(seq_one, seq_two) -> float:
        """Simpler IOU function for key and value calculation"""
        intersection = 0
        union = 0
        for x in seq_one:
            if x in seq_two:
                intersection += 1
            union += 1
        return intersection / union
    
    overall_agreement = defaultdict(dict)

    for guid, frame_annos in annotations.items():
        a_annos = frame_annos["A"] if "A" in frame_annos.keys() and frame_annos["A"] != {} else None
        b_annos = frame_annos["B"] if "B" in frame_annos.keys() and frame_annos["B"] != {} else None

        if b_annos is None or a_annos is None:
            if b_annos is None and a_annos is None:
                overall_agreement[guid]["key"] =1
                overall_agreement[guid]["val"] =1
                overall_agreement[guid]["pair"]= 1
                overall_agreement[guid]["total"] =1
                continue
            else:
                overall_agreement[guid]["key"] =0
                overall_agreement[guid]["val"] =0
                overall_agreement[guid]["pair"] =0
                overall_agreement[guid]["total"] =0
                continue


        pairs = assoc_pairs(a_annos, b_annos)

        key_agreement = get_iou(a_annos.keys(), b_annos.keys())
        val_agreement = get_iou(a_annos.values(), b_annos.values())
        pair_agreement = pair_iou(pairs[0], pairs[1])
        total_agreement = aggregate_vals(key_agreement, val_agreement, pair_agreement)


        overall_agreement[guid]["key"] = key_agreement
        overall_agreement[guid]["val"] = val_agreement
        overall_agreement[guid]["pair"] = pair_agreement
        overall_agreement[guid]["total"] = total_agreement

    return overall_agreement


def aggregate_vals(*args):
    """aggregation function, for combining
    kv-pair agreement values in different ways.
    Currently calculates the AVERAGE of the values."""

    out = args[0] 
    for arg in args[1:]:
        out *= arg
    return out



# Main
def main(args):
    in_dir   = args.in_dir
    out_file = args.out_file
    skip     = args.skip
    ANNOTATOR_A = 20007
    ANNOTATOR_B = 20008
    a_dir = f"{in_dir}/{ANNOTATOR_A}"
    b_dir = f"{in_dir}/{ANNOTATOR_B}"

    # load in frames
    frames = load_data(a_dir,
                       b_dir, 
                       include_skips=skip)
    
    # calculate agreement
    results = get_agreement(frames, skips = skip)
    
    # write to file
    with open(f"results/skips/product-complexfuzzy-{out_file}", 'w', encoding='utf8') as f:
        writer = csv.writer(f)
        writer.writerow(["guid", "keys","vals","pairs","total"])
        for guid, agreement in results.items():
            writer.writerow([guid, agreement["key"], agreement["val"], agreement["pair"], agreement["total"]])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--in_dir",
                        help="Directory where annotation json files are stored",
                        default="./data/rfb-r2-annotations.231117")
    parser.add_argument("-s", "--skip",
                        action="store_true",
                        help="whether or not to include skipped files in the agreement calculation")
    parser.add_argument('-o', "--out_file",
                        help="location of the results output file",
                        default="results.csv")
    runtime_args = parser.parse_args() 
    main(args=runtime_args)
