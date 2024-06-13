import pandas as pd
import argparse


def has_alnum(string: str) -> bool:
    """Returns True if any character in the string is an alphanumeric."""
    return any(char.isalnum() for char in string)


def has_alpha(string: str) -> bool:
    """Returns True if any character in the string contains alpha characters."""
    return any(char.isalpha() for char in string)


def clean_ocr(text_document: str) -> list[str]:
    """Cleans ocr text document"""
    allowable_chars = {r'&'}
    cleaned = []
    for line in text_document.split('\n'):
        if not has_alpha(line):
            continue
        else:
            line = [s for s in line.split() if (len(s) > 1 and has_alpha(s)) or s in allowable_chars]
        cleaned.extend(line)
    return cleaned


def main(input_file, output_file):
    df = pd.read_csv(input_file, usecols=['textdocument'])
    df['cleaned'] = df['textdocument'].map(clean_ocr)
    df.to_csv(output_file, index=True)


if __name__ == '__main__':
    # To run standalone on a CSV file, run e.g.:
    # python clean_ocr.py input.csv output.csv
    
    parser = argparse.ArgumentParser(description='Clean OCR text')
    parser.add_argument('input_file', type=str, help='Input CSV file path')
    parser.add_argument('output_file', type=str, help='Output CSV file path')
    args = parser.parse_args()

    main(args.input_file, args.output_file)