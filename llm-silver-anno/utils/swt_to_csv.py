import argparse
from mmif import Mmif
import pandas as pd
from tqdm import tqdm
import os
import re
from mmif.vocabulary.annotation_types import AnnotationTypes

def dir_to_csv(in_dir: str, out_file: str):
    """
    Gathers annotations from all SWT/OCR MMIF files in a directory
    and writes them to a single CSV file.
    """
    data = []
    for file in tqdm(os.listdir(in_dir)):
        full_path = os.path.join(in_dir, file)
        try:
            with open(full_path, "r") as f:
                mmif = Mmif(f.read())

            for doc in mmif.documents:
                if doc.properties["mime"] == "video":
                    video_path = doc.location
            
            guid = re.search(r"cpb-aacip-[0-9]*-[a-zA-Z0-9]*", video_path).group(0)

            for view in mmif.views:
                alignments = view.get_annotations(AnnotationTypes.Alignment)
                for alignment in alignments:
                    if "tp" not in alignment.properties["source"] or "td" not in alignment.properties["target"]:
                        continue
                    source_timepoint = alignment.properties["source"]
                    target_td = alignment.properties["target"]

                    if target_td in mmif:
                        td_anno = mmif[target_td]
                    else:
                        for view in mmif.views:
                            if target_td in view:
                                td_anno = view[target_td]
                    ocr_text = td_anno.properties["text"].value

                    if source_timepoint in mmif:
                        timepoint_anno = mmif[source_timepoint]
                    else:
                        for view in mmif.views:
                            if source_timepoint in view:
                                timepoint_anno = view[source_timepoint]
                    timepoint = timepoint_anno.properties["timePoint"]
                    scene_label, confidence = max(timepoint_anno.properties["classification"].items(), key=lambda x: x[1])

                    if scene_label in ["I", "N", "Y"]:
                        scene_label = "chyron"
                    elif scene_label == "C":
                        scene_label = "credits"
                    # If scene label isn't one of those two, we aren't interested in it
                    else:
                        continue

                    data.append({
                        "guid": guid,
                        "timepoint": timepoint,
                        "scene_label": scene_label,
                        "confidence": confidence,
                        "textdocument": ocr_text
                    })

            # print(f"Total {len(data)} annotations.")

        except Exception as e:
            print(f"Error processing {full_path}: {e}")
            continue

    df = pd.DataFrame.from_dict(data)

    print(f"Found {len(df)} annotations.")
    
    df = df.drop_duplicates(subset=["textdocument"])

    print(f"Saving {len(df)} unique annotations to {out_file}.")
    print(f"Total: {len(df[df['scene_label'] == 'chyron'])} chyrons, {len(df[df['scene_label'] == 'credits'])} credits")
    df.to_csv(out_file, index=False)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MMIF -> CSV conversion script for RFB annotations.")
    parser.add_argument("--input_dir", type=str, required=True, help="The directory containing the MMIF files.")
    parser.add_argument("--output_file", type=str, required=True, help="The output CSV file.")
    args = parser.parse_args()
    
    dir_to_csv(args.input_dir, args.output_file)