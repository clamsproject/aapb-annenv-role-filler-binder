import argparse
from typing import Dict

import easyocr
import torch
import cv2 as cv
import streamlit as st
import json
from pathlib import Path


def draw(results, image):
    annotated_img = image.copy()
    for i, result in enumerate(results):
        top_left = tuple(result[0][0])
        bottom_right = tuple(result[0][2])
        annotated_img = cv.rectangle(annotated_img, top_left, bottom_right, (255, 0, 0), 3)
        annotated_img = cv.putText(annotated_img, str(i), top_left, cv.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3,
                                   cv.LINE_AA)
    return annotated_img


def annotate():
    st.session_state['annotations'].append((st.session_state.key, st.session_state.value))


def delete_annotation(index):
    if len(st.session_state['annotations']) == 0:
        st.warning('No annotations to delete')
        return
    if index < 0 or index >= len(st.session_state['annotations']):
        st.warning('Index out of range')
        return
    annotations = list(st.session_state['annotations'])
    annotations.pop(index)
    st.session_state['annotations'] = annotations


def download_annotations(file_name):
    with st.spinner('Downloading...'):
        annotations = st.session_state.annotations
        if len(annotations) == 0:
            st.warning('No annotations to download')
            return
        annotations_dict = {}
        for key, value in annotations:
            if key in annotations_dict:
                annotations_dict[key].append(value)
            else:
                annotations_dict[key] = [value]
        annotations = json.dumps(annotations_dict, indent=2)
        # Add image id to annotations
        annotations = annotations.replace('{', f'{{\n"_image_id": "{file_name}",')
        st.session_state['image_id'] = file_name
        # Download
        with open(f'{annotation_dir}/{file_name}.json', 'w') as f:
            f.write(annotations)
        st.success('Downloaded annotations')
        st.session_state['annotations'] = []


def download_dupe_annotations(file_name):
    with st.spinner('Downloading Duplicate annotations...'):
        # Download JSON referencing image id of last image
        with open(f'{annotation_dir}/{file_name}.json', 'w') as f:
            f.write(json.dumps({'_image_id': file_name, '_duplicate_image_id': st.session_state['image_id']}, indent=2))


# Cycle to next image, clear annotations, rerun OCR and redraw
def cycle_images(images, file_name, duplicate):
    if len(st.session_state['annotations']) == 0 and not duplicate:
        st.warning('Please annotate image before moving on or classify as duplicate')
        return
    if not duplicate:
        download_annotations(file_name)
    else:
        download_dupe_annotations(file_name)
    if st.session_state['image_index'] == len(images) - 1:
        st.warning('No more images to annotate')
        return
    st.session_state['image_index'] = (st.session_state['image_index'] + 1)
    st.session_state['annotations'] = []
    st.cache_data.clear()


@st.cache_data
def run_ocr():
    return OCR(sample_img)


class OCR:
    def __init__(self, image):
        self.reader = easyocr.Reader(['en'], gpu=True if torch.cuda.is_available() else False)
        self.image = image
        self.results = self.reader.readtext(self.image)
        self.annotated_image = draw(self.results, self.image)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help='<Image Directory>:<Annotation Directory>', default='images')
    args = parser.parse_args()
    dirs = args.dir.split(':')
    image_dir = dirs[0]
    annotation_dir = dirs[1]
    # Images will have filenames of the form <video_guid>.<frame_number>.png
    images = [image.name for image in Path(image_dir).glob('*.png')]
    indexed_images: Dict[int, str] = {i: image for i, image in enumerate(images)}

    #############################
    # Streamlit
    #############################
    st.set_page_config(layout="centered")
    # Load first image
    if 'image_index' not in st.session_state:
        st.session_state['image_index'] = 0
    if 'annotations' not in st.session_state:
        st.session_state['annotations'] = []

    # This is the image OCR will be run on
    sample_img = cv.imread(f"{image_dir}/{indexed_images[st.session_state['image_index']]}")

    image_name = indexed_images[st.session_state['image_index']]
    # Remove file extension
    image_name = image_name.rsplit('.')[0]
    ocr = run_ocr()

    #############################
    # Top Buttons
    #############################
    with st.container():
        col1, col2= st.columns(2)
        # On click, cycle to next image, clear annotations, save annotations, rerun OCR and redraw
        col1.button("Next Image", help="Go to next image", on_click=cycle_images,
                    args=(indexed_images, image_name, False))
        # Handle duplicate frames. If image is duplicate of last image, download json referencing last image's image id
        col2.button("Duplicate Frame", help="Duplicate frame", on_click=cycle_images,
                    args=(indexed_images, image_name, True))

    ##############################
    # OCR Results and Drawn Image
    ##############################
    st.title('OCR Annotation')
    if 'annotations' not in st.session_state:
        st.session_state['annotations'] = []
    with st.container():
        col1, col2 = st.columns(2)
        col1.image(sample_img)
        col1.image(ocr.annotated_image)
        for i, result in enumerate(ocr.results):
            if result[2] > 0.8:
                col2.markdown(f'**{i}:** :green[{result[1]}]')
            elif result[2] > 0.5:
                col2.markdown(f'**{i}:** :orange[{result[1]}]')
            else:
                col2.markdown(f'**{i}:** :red[{result[1]}]')

    ##############################
    # Annotation Form
    ##############################
    with st.form("annotation"):
        st.write("## Annotation")
        with st.container():
            col1, col2 = st.columns(2)
            col1.text_input(f'Key', key='key')
            col2.text_input(f'Value', key='value')
        st.form_submit_button("Add New Key-Value Pair", on_click=annotate)

    st.write(st.session_state.annotations)

    ##############################
    # Delete Form
    ##############################
    with st.form("delete"):
        st.write("## Delete Annotation")
        index = st.number_input(f'Index', step=1, min_value=0)
        st.form_submit_button("Delete Key-Value Pair", on_click=delete_annotation, args=(index,))
