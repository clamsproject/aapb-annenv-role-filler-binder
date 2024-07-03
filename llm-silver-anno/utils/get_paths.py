import pandas as pd
import requests
from tqdm import tqdm
import argparse

def get_full_path(guid, url):
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
   parser.add_argument("--input_file", required=True, help="Input CSV file path")
   parser.add_argument("--output_file", required=True, help="Output CSV file path")
   parser.add_argument("--url", required=True, help="URL (including port) for the search API")
   args = parser.parse_args()

   process_data(args.input_file, args.output_file, args.url)