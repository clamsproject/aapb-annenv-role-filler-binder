from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm
import argparse

cached_paths = {}
for prev_csv in Path(__file__).parent.parent.glob("*paths.csv"):
    df = pd.read_csv(prev_csv)
    cached_paths.update(pd.Series(df.path.values, index=df.guid).to_dict())


def get_full_path(guid, url):
    if guid in cached_paths:
        return cached_paths[guid]
    full_url = f"{url}/searchapi?file=video&guid={guid}"
    response = requests.get(full_url)
    data = response.json()
    return data[0]


def process_data(input_file, output_file, url):
    tqdm.pandas()

    df = pd.read_csv(input_file)
    df["path"] = df["guid"].progress_apply(get_full_path, args=(url,))
    df.to_csv(output_file, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process data")
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--url", required=True, help="URL (including port) for the search API")
    args = parser.parse_args()

    process_data(args.input, args.output, args.url)
