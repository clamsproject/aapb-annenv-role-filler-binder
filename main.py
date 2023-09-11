import argparse
import json
import pickle
from collections import defaultdict
from pathlib import Path

import cv2 as cv
import streamlit as st

KEY = 'key'
VALUE = 'value'
DELIM = '\n'
REASON_DUPE = 'DUPLICATE'


def get_image_id(guid, fnum):
    return '.'.join(map(str, [guid, fnum]))


def get_image_fname(guid, fnum):
    return f'{image_dir}/{Path(get_image_id(guid, fnum))}.png'


def get_annotation_fname(guid, fnum):
    return Path(annotation_dir) / f'{get_image_id(guid, fnum)}.json'


def get_progress_guid(guid, string=False):
    done, total = len(list(Path(annotation_dir).glob(f'{guid}.*.json'))), len(list(Path(image_dir).glob(f'{guid}.*.png')))
    if string:
        return f'{done}/{total}'
    else:
        return done, total


def get_progress_guid_fnum(guid, fnum):
    return get_annotation_fname(guid, fnum).exists()


def draw(results, image):
    annotated_img = image.copy()
    if len(results) == 0:
        st.warning('No results to draw')
        return annotated_img
    for i, result in enumerate(results):
        top_left = tuple(result[0][0])
        bottom_right = tuple(result[0][2])
        annotated_img = cv.rectangle(annotated_img, (int(top_left[0]), int(top_left[1])),
                                     (int(bottom_right[0]), int(bottom_right[1])), (255, 0, 0), 3)
        annotated_img = cv.putText(annotated_img, str(i), (int(top_left[0]), int(top_left[1])),
                                   cv.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3, cv.LINE_AA)
    return annotated_img


def add_pair():
    d = defaultdict(list, st.session_state['annotations'])
    k = st.session_state[KEY]
    v = st.session_state[VALUE]
    d[k].extend(v.split(DELIM))
    st.session_state['annotations'] = d
    st.session_state[KEY] = ''
    st.session_state[VALUE] = ''
    st.toast(f'"{v.split(DELIM)}" added to "{k}"')


def delete_pair(index):
    if len(st.session_state['annotations']) == 0:
        st.warning('No annotations to delete')
        return
    if index < 0 or index >= len(st.session_state['annotations']):
        st.warning('Index out of range')
        return
    annotations = list(st.session_state['annotations'])
    annotations.pop(index)
    st.session_state['annotations'] = annotations


def save_pairs(guid, fnum, continuing=True):
    """
    Append annotations to the existing annotation file for the image that started this series of continuing credits
    annotations
    """
    with st.spinner('Saving...'):
        if continuing and st.session_state['first_credit_image_id'] is None:
            st.warning('No existing annotation to append current pairs, failed to save annotations as "continuing"')
            return False
        annotations = st.session_state['annotations']
        if len(annotations) == 0:
            st.warning('No annotations to save')
            return False
        if continuing:
            starting_fnum = int(st.session_state['starting_fnum'])
            annotations['_continued_from'] = get_image_id(guid, starting_fnum)
        else:
            st.session_state['starting_fnum'] = fnum
        annotations['_image_id'] = get_image_id(guid, fnum)
        with open(get_annotation_fname(guid, fnum), 'w') as f:
            f.write(json.dumps(annotations, indent=2))
        st.success('Saved annotations')
        st.toast('Saved annotations')
        st.session_state['annotations'] = {}
        return True


def save_dupe_annotations(guid, fnum):
    with st.spinner('Downloading Duplicate annotations...'):
        # Download JSON referencing image id of last image
        with open(get_annotation_fname(guid, fnum), 'w') as f:
            f.write(json.dumps({'_image_id': get_image_id(guid, fnum), '_skip_reason': REASON_DUPE}, indent=2))
    return True


def save_na_annotations(guid, fnum):
    with st.spinner('Downloading N/A annotations...'):
        # Download JSON referencing image id of last image
        with open(get_annotation_fname(guid, fnum), 'w') as f:
            f.write(json.dumps({'_image_id': get_image_id(guid, fnum), '_skip_reason': skip_reason}, indent=2))
    return True


def autofill(result, slot):
    if slot == KEY:
        if not st.session_state[KEY]:
            st.session_state[KEY] = result
        else:
            st.session_state[KEY] += f" {result}"
    elif slot == VALUE:
        if not st.session_state[VALUE]:
            st.session_state[VALUE] = result
        else:
            st.session_state[VALUE] += f" {result}"


# Cycle to next image, clear annotations, rerun OCR and redraw
def cycle_images(images, guid, fnum, action: str):
    if len(st.session_state['annotations']) == 0 and action == 'next':
        st.warning('Please annotate image before moving on or classify as duplicate')
        return
    if action == 'next':
        valid = save_pairs(guid, fnum, False)
    elif action == 'cont':
        valid = save_pairs(guid, fnum)
    elif action == 'dupe':
        valid = save_dupe_annotations(guid, fnum)
    elif action == 'skip':
        valid = save_na_annotations(guid, fnum)
    if st.session_state['image_index'] == len(images) - 1:
        st.warning('No more images to annotate')
        return
    if valid:
        st.session_state['image_index'] = (st.session_state['image_index'] + 1)
        st.cache_data.clear()


def load_results(guid, fnum):
    """
    Load results from OCR
    """
    with open(f'{image_dir}/ocr/{get_image_id(guid,fnum)}', 'rb') as f:
        results = pickle.load(f)
    return results


@st.cache_data
def load_ocr():
    return OCR(sample_img, results)


class OCR:
    def __init__(self, image, results):
        self.image = image
        self.results = results
        self.annotated_image = draw(self.results, self.image)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', type=str, help='<Image Directory>:<Annotation Directory>', default='images')
    args = parser.parse_args()
    dirs = args.dir.split(':')
    image_dir = dirs[0]
    annotation_dir = dirs[1]
    Path(annotation_dir).mkdir(parents=True, exist_ok=True)
    guids = defaultdict(list)
    for img_f in Path(image_dir).glob('*.png'):
        guid, fnum = img_f.name.split('.', 2)[:2]
        guids[guid].append(int(fnum))
    for fnums in guids.values():
        fnums.sort()
    indexed_images = {}
    revindex_images = {}
    idx = 0
    for guid, fnums in guids.items():
        for fnum in fnums:
            indexed_images[idx] = (guid, fnum)
            revindex_images[(guid, fnum)] = idx
            idx += 1
    
    #############################
    # Streamlit
    #############################
    st.set_page_config(layout="wide")
    # Load first image
    if 'image_index' not in st.session_state:
        img_idx = 0
        while get_progress_guid_fnum(*indexed_images[img_idx]):
            img_idx += 1
        st.session_state['image_index'] = img_idx
    ann_fname = get_annotation_fname(*indexed_images[st.session_state['image_index']])
    if 'annotations' not in st.session_state:
        if ann_fname.exists():
            st.session_state['annotations'] = json.load(open(ann_fname, 'r'))
        else:
            st.session_state['annotations'] = {}

    # This is the image that will be annotated
    guid, fnum = indexed_images[st.session_state['image_index']]
    sample_img = cv.imread(get_image_fname(guid, fnum))
    # load results for image
    results = load_results(guid, fnum)
    image_name = get_image_id(guid, fnum)
    ocr = OCR(sample_img, results)

    st.title('OCR Annotation')
    st.divider()

    img_col, nav_col, skip_col = st.columns((7, 2, 1))
    with img_col:
        ##############################
        # Drawn Image
        ##############################
        st.subheader(f'Current image: `{guid}` {fnum}')
        st.markdown(f'Last "significant" frame: {st.session_state["starting_fnum"] if "starting_fnum" in st.session_state else "None"}')
        st.caption(f':red[TODO]: explain what "significant" means in the guidelines')
        st.image([sample_img, ocr.annotated_image])
    with nav_col:
        #############################
        # Image Navigation
        #############################
        st.subheader('Data Navigator')
        ops = list(guids.keys())
        idx = ops.index(guid)
        nav_guid_picker = st.selectbox('Select video', options=ops, index=idx, 
                                       format_func=lambda x: f'{x} ({get_progress_guid(x, string=True)})')
        ops = guids[nav_guid_picker]
        idx = ops.index(fnum) if nav_guid_picker == guid else 0
        nav_fnum_picker = st.selectbox('Select frame', options=ops, index=idx, 
                                       format_func=lambda x: f'{x} {"✅" if get_progress_guid_fnum(nav_guid_picker, x) else "❌"}')
        st.button('Go', help='Go to selected image', on_click=lambda: st.session_state.update({'image_index': revindex_images[(nav_guid_picker, nav_fnum_picker)]}))
    with skip_col:
        #############################
        # "Skip" Buttons
        #############################
        # On click, cycle to next image, clear annotations, save annotations, rerun OCR and redraw
        st.button("Next Frame", help="Go to next image", on_click=cycle_images, args=(indexed_images, guid, fnum, 'next'))
        # Handle duplicate frames. If image is duplicate of last image, save json referencing last image's image id
        st.button("Duplicate Frame", help="Duplicate frame", on_click=cycle_images, args=(indexed_images, guid, fnum, 'dupe'))
        # Button for scrolling credits where there are new key-value annotations to add to last image
        st.button("Continuing Credits", help=f"Add new {KEY}-{VALUE} annotations to last image", on_click=cycle_images, args=(indexed_images, guid, fnum, 'cont'))
        # Skip frame for which key-value annotations are not applicable
        st.button("Skip Frame", help="Skip frame", on_click=cycle_images, args=(indexed_images, guid, fnum, 'skip'))
        # Add skip reason text form
        skip_reason = st.text_area('Reason for skipping', key='skip_reason')
    st.divider()
    
    with st.form("annotation"):
        st.write("## Add Annotation")
        col1, col2 = st.columns(2)
        col1.text_input(f'Key', key=KEY, value=st.session_state[KEY] if KEY in st.session_state else '')
        col2.text_area(f'Value', key=VALUE, value=st.session_state[VALUE] if VALUE in st.session_state else '')
        add_pair_btn = st.form_submit_button("Add a new pair", on_click=add_pair)

    for i in range(len(ocr.results) // 4 + 1):
        cols = st.columns(4)
        for j in range(4):
            with cols[j]:
                r_idx = i * 4 + j
                if r_idx >= len(ocr.results):
                    break
                result = ocr.results[r_idx]
                if result[2] > 0.8:
                    color = 'green'
                elif result[2] > 0.5:
                    color = 'orange'
                else:
                    color = 'red'
                st.markdown(f'{r_idx}: :{color}[{result[1]}]')
                st.button(f'append to `{KEY}`', help='Click to annotate',
                          on_click=autofill,
                          args=(result[1], KEY), key=f"key_{result[1]}_{r_idx}")
                st.button(f'append to `{VALUE}`', help='Click to annotate', on_click=autofill,
                          args=(result[1], VALUE), key=f"value_{result[1]}_{r_idx}")
        if DELIM == '\n':
            delim_str = 'hit "ENTER" key while in the text field'
        else:
            delim_str = f'type "{DELIM}" in the text field'
        st.button(f'Add a delimiter to values field (to manually type a delimiter, {delim_str}).', key=f'delim_{i}', on_click=autofill, args=(DELIM, VALUE), use_container_width=True)
        b = st.button("extra 'add' button", key=f'add_{i}', on_click=add_pair)
        st.divider()
        st.image([sample_img, ocr.annotated_image])

    ##############################
    # Annotation Viewer
    ##############################

    st.markdown('## Current Annotations')
    st.write(st.session_state['annotations'])

    ##############################
    # Annotation Editor 
    ##############################
    with st.form("delete"):
        st.write("## Delete Annotation")
        index = st.number_input(f'Index', step=1, min_value=0)
        st.form_submit_button("Delete Key-Value Pair", on_click=delete_pair, args=(index,))
