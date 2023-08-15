import easyocr
import torch
import argparse
import os
import cv2 as cv
import pickle
from tqdm import tqdm

from pathlib import Path


class OCR:
    def __init__(self, image):
        self.reader = easyocr.Reader(['en'], gpu=True if torch.cuda.is_available() else False)
        self.image = image
        self.results = self.reader.readtext(self.image, width_ths=0.3)  # smaller width_ths -> more split results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help='Image Directory', default='images')
    args = parser.parse_args()
    image_dir = args.dir
    os.makedirs(f'{image_dir}/ocr', exist_ok=True)
    # Images will have filenames of the form <video_guid>.<frame_number>.png
    images = [image.name for image in Path(image_dir).glob('*.png')]
    # Sort images
    images = sorted(images, key=lambda x: int(x.split('.')[1]))

    for image in tqdm(images, desc='Processing images'):
        image_name = image.rsplit('.', 1)[0]
        ocr = OCR(cv.imread(f"{image_dir}/{image}"))
        with open(f'{image_dir}/ocr/{image_name}', 'wb') as f:
            pickle.dump(ocr.results, f)
