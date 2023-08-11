import argparse
from typing import Dict
import os

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
    st.session_state['key'] = ''
    st.session_state['value'] = ''


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


def download_annotations(file_name, continue_annotating: bool) -> bool:
    with st.spinner('Downloading...'):
        annotations = st.session_state.annotations
        if len(annotations) == 0:
            st.warning('No annotations to download')
            return False
        annotations_dict = {}
        for key, value in annotations:
            if key in annotations_dict:
                annotations_dict[key].append(value)
            else:
                annotations_dict[key] = [value]
        annotations = json.dumps(annotations_dict, indent=2)
        if not continue_annotating:
            # Add image id to annotations
            annotations = annotations.replace('{', f'{{\n"_image_id": "{file_name}",')
        else:
            # Add image id and image id of last image to annotations
            annotations = annotations.replace('{', f'{{\n"_image_id": "{file_name},'
                                                   f'\n"_prev_image_id: {st.session_state["image_id"]},')
        # Download
        with open(f'{image_dir}/{annotation_dir}/{file_name}.json', 'w') as f:
            f.write(annotations)
        st.session_state['image_id'] = file_name
        st.success('Downloaded annotations')
        st.session_state['annotations'] = []
        return True


def download_dupe_annotations(file_name):
    with st.spinner('Downloading Duplicate annotations...'):
        # Download JSON referencing image id of last image
        with open(f'{image_dir}/{annotation_dir}/{file_name}.json', 'w') as f:
            f.write(json.dumps({'_image_id': file_name, '_duplicate_image_id': st.session_state['image_id']}, indent=2))
    return True


def download_na_annotations(file_name):
    with st.spinner('Downloading N/A annotations...'):
        # Download JSON referencing image id of last image
        with open(f'{image_dir}/{annotation_dir}/{file_name}.json', 'w') as f:
            f.write(json.dumps({'_image_id': file_name, '_skip_reason': skip_reason}, indent=2))
    return True


def autofill(result, slot):
    if slot == 'key':
        st.session_state['key'] += f" {result}"
    elif slot == 'value':
        st.session_state['value'] += f" {result}"


# Cycle to next image, clear annotations, rerun OCR and redraw
def cycle_images(images, file_name, action: str):
    if len(st.session_state['annotations']) == 0 and action == 'next':
        st.warning('Please annotate image before moving on or classify as duplicate')
        return
    if action == 'next':
        valid = download_annotations(file_name, False)
    elif action == 'dupe':
        valid = download_dupe_annotations(file_name)
    elif action == 'skip':
        valid = download_na_annotations(file_name)
    elif action == 'cont':
        valid = download_annotations(file_name, True)
    if st.session_state['image_index'] == len(images) - 1:
        st.warning('No more images to annotate')
        return
    if valid:
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
    os.makedirs(f'{image_dir}/{annotation_dir}', exist_ok=True)
    # Images will have filenames of the form <video_guid>.<frame_number>.png
    images = [image.name for image in Path(image_dir).glob('*.png')]
    indexed_images: Dict[int, str] = {i: image for i, image in enumerate(images)}

    #############################
    # Streamlit
    #############################
    st.set_page_config(layout="wide")
    # Load first image
    if 'image_index' not in st.session_state:
        st.session_state['image_index'] = 0
    if 'annotations' not in st.session_state:
        st.session_state['annotations'] = []

    # This is the image OCR will be run on
    sample_img = cv.imread(f"{image_dir}/{indexed_images[st.session_state['image_index']]}")

    image_name = indexed_images[st.session_state['image_index']]
    # Remove file extension
    image_name = image_name.rsplit('.', 1)[0]
    ocr = run_ocr()

    ##############################
    # OCR Results and Drawn Image
    ##############################
    st.title('OCR Annotation')
    if 'annotations' not in st.session_state:
        st.session_state['annotations'] = []
    with st.container():
        col1, col2, col3 = st.columns(3)
        col1.image(sample_img)
        col1.image(ocr.annotated_image)
        col2.markdown(f'**KEY**')
        col3.markdown(f'**VALUE**')
        for i, result in enumerate(ocr.results):
            if result[2] > 0.8:
                col2.button(f'{i}: :green[{result[1]}]', help='Click to annotate', on_click=autofill,
                            args=(result[1], 'key'), key=f"key_{result[1]}")
                col3.button(f'{i}: :green[{result[1]}]', help='Click to annotate', on_click=autofill,
                            args=(result[1], 'value'), key=f"value_{result[1]}")
            elif result[2] > 0.5:
                col2.button(f'{i}: :orange[{result[1]}]', help='Click to annotate', on_click=autofill,
                            args=(result[1], 'key'), key=f"key_{result[1]}")
                col3.button(f'{i}: :orange[{result[1]}]', help='Click to annotate', on_click=autofill,
                            args=(result[1], 'value'), key=f"value_{result[1]}")
            else:
                col2.button(f'{i}: :red[{result[1]}]', help='Click to annotate', on_click=autofill,
                            args=(result[1], 'key'), key=f"key_{result[1]}")
                col3.button(f'{i}: :red[{result[1]}]', help='Click to annotate', on_click=autofill,
                            args=(result[1], 'value'), key=f"value_{result[1]}")

    #############################
    # Submit Buttons
    #############################
    with st.container():
        col1, col2, col3, col4, col5 = st.columns(5)
        # On click, cycle to next image, clear annotations, save annotations, rerun OCR and redraw
        col1.button("Next Frame", help="Go to next image", on_click=cycle_images,
                    args=(indexed_images, image_name, 'next'))
        # Handle duplicate frames. If image is duplicate of last image, download json referencing last image's image id
        col2.button("Duplicate Frame", help="Duplicate frame", on_click=cycle_images,
                    args=(indexed_images, image_name, 'dupe'))
        # Button for scrolling credits where there are new key-value annotations to add to last image
        col3.button("Continuing Credits", help="Add new key-value annotations to last image", on_click=cycle_images,
                    args=(indexed_images, image_name, 'cont'))
        # Skip frame for which key-value annotations are not applicable
        col4.button("Skip Frame", help="Skip frame", on_click=cycle_images,
                    args=(indexed_images, image_name, 'skip'))
        # Add skip reason text form
        skip_reason = col5.text_input('Reason for skipping', key='skip_reason', value='N/A')

    ##############################
    # Annotation Form
    ##############################
    with st.form("annotation"):
        st.write("## Annotation")
        with st.container():
            col1, col2 = st.columns(2)
            col1.text_input(f'Key', key='key', value=st.session_state['key'] if 'key' in st.session_state else '')
            col2.text_input(f'Value', key='value', value=st.session_state['value'] if 'value' in st.session_state else '')
        st.form_submit_button("Add New Key-Value Pair", on_click=annotate)

    st.write(st.session_state.annotations)

    ##############################
    # Delete Form
    ##############################
    with st.form("delete"):
        st.write("## Delete Annotation")
        index = st.number_input(f'Index', step=1, min_value=0)
        st.form_submit_button("Delete Key-Value Pair", on_click=delete_annotation, args=(index,))
