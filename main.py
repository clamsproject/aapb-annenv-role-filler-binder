import argparse
import datetime
import json
import pickle
from collections import defaultdict
from pathlib import Path

import cv2 as cv
import streamlit as st

KEY = 'key'
VALUE = 'value'
DELIM = '\n'
delim_str = 'hit "ENTER" key while in the text field' if DELIM == '\n' else f'type "{DELIM}" in the text field'
REASON_DUPE = 'DUPLICATE'
skip_reason_otherkey = 'other'
skip_reason_opts = [
    REASON_DUPE,
    'no text in image',
    'not K-V',
    'commercial',
    skip_reason_otherkey,
]


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
    vs = st.session_state[VALUE]
    if vs:
        for v in vs.split(DELIM):
            if v:
                d[k].append(v.strip())
        st.session_state['annotations'] = d
        st.session_state[KEY] = ''
        st.session_state[VALUE] = ''
        st.toast(f'"{v.split(DELIM)}" added to "{k}"')


def delete_pairs(keys):
    if len(st.session_state['annotations']) == 0:
        st.warning('No annotations to delete')
        return
    for key in keys:
        st.session_state['annotations'].pop(key)


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


def save_na_annotations(guid, fnum):
    reason = st.session_state.get('skip_reason', None)
    if not (reason is None or reason == ''):
        with st.spinner('Downloading N/A annotations...'):
            # Download JSON referencing image id of last image
            with open(get_annotation_fname(guid, fnum), 'w') as f:
                f.write(json.dumps({'_image_id': get_image_id(guid, fnum), '_skip_reason': reason}, indent=2))
        st.session_state.skip_reason_sel = (0, REASON_DUPE)
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
    if action in ['next', 'cont']:
        add_pair()
    if len(st.session_state['annotations']) == 0 and action == 'next':
        st.toast('⛔️ Please annotate image before moving on or classify as duplicate')
        st.error('⛔️ Please annotate image before moving on or classify as duplicate')
        return
    if action == 'next':
        valid = save_pairs(guid, fnum, False)
    elif action == 'cont':
        valid = save_pairs(guid, fnum)
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


def copy_prev_annotations(cur_guid):
    iidx = st.session_state['image_index'] - 1
    prev_annotations = {}
    prev_guid, prev_fnum = indexed_images[iidx]
    while prev_guid == cur_guid:
        anns = json.load(open(get_annotation_fname(prev_guid, prev_fnum), 'r'))
        if '_skip_reason' not in anns:
            prev_annotations = anns
            break
        iidx -= 1
        prev_guid, prev_fnum = indexed_images[iidx]
    for k, v in prev_annotations.items():
        if not k.startswith('_'):
            st.session_state['annotations'][k] = v
            st.toast(f'"{k}" copied from frame {prev_fnum}')

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
    if 'annotations' not in st.session_state or st.session_state['annotations'] is None:
        st.session_state['annotations'] = {}
        if ann_fname.exists():
            existing_ann = json.load(open(ann_fname, 'r'))
            for k, v in existing_ann.items():
                if k.startswith('_'):
                    continue
                st.session_state['annotations'][k] = v
    if 'show_img_twice' not in st.session_state:
        st.session_state['show_img_twice'] = False
    if 'show_navigator' not in st.session_state:
        st.session_state['show_navigator'] = False
    if KEY not in st.session_state:
        st.session_state[KEY] = ''
    if VALUE not in st.session_state:
        st.session_state[VALUE] = ''


    # This is the image that will be annotated
    guid, fnum = indexed_images[st.session_state['image_index']]
    sample_img = cv.imread(get_image_fname(guid, fnum))
    # load results for image
    results = load_results(guid, fnum)
    image_name = get_image_id(guid, fnum)
    ocr = OCR(sample_img, results)
    st.subheader(f'Current image: `{guid}` {fnum} ({datetime.timedelta(seconds=fnum // 30)}) [AAPB reading room](https://americanarchive.org/catalog/{guid.replace("cpb-aacip-", "cpb-aacip_")})')
    img_col, skip_col = st.columns((7, 1))
    with img_col:
        ##############################
        # Drawn Image
        ##############################
        st.image([sample_img, ocr.annotated_image])
    # with nav_col:
    with skip_col:
        # Add skip reason text form
        st.session_state['skip_reason'] = st.selectbox(
            'Reason for skipping', key='skip_reason_sel',
            options=enumerate(skip_reason_opts),
            format_func=lambda x: f'0.{x[1]}' if x[1] == skip_reason_otherkey else f'{x[0]}.{x[1]}' if x[1] != REASON_DUPE else x[1],
        )[1]
        if st.session_state['skip_reason'] == skip_reason_otherkey:
            st.session_state['skip_reason'] = st.text_area('Reason for skipping', key='skip_reason_free')
        # Skip frame for which key-value annotations are not applicable
        st.button("Skip Frame", on_click=cycle_images, args=(indexed_images, guid, fnum, 'skip'),  use_container_width=True,
                  disabled='skip_reason' not in st.session_state or st.session_state['skip_reason'] is None or st.session_state['skip_reason'] == '')
        st.button("Copy prev. annotations", on_click=copy_prev_annotations, args=[guid],
                  disabled=guids[guid].index(fnum) == 0, use_container_width=True,)
        st.button("Save and proceed to next Frame", use_container_width=True, key='cont_top',
                  disabled=len(st.session_state[VALUE]) + len(st.session_state['annotations']) == 0,
                  on_click=cycle_images, args=(indexed_images, guid, fnum, 'next'))
    ##############################
    # Add annotation
    ##############################
    with st.container():
        st.write("## Add Annotation")
        col1, col2 = st.columns(2)
        col1.text_input(f'Key', key=KEY, value=st.session_state[KEY] if KEY in st.session_state else '')
        col2.text_area(f'Value', key=VALUE, value=st.session_state[VALUE] if VALUE in st.session_state else '')
        add_pair_btn = st.button("Add a new pair", use_container_width=True, on_click=add_pair)
        st.button(f'Add a delimiter to values field (to manually type a delimiter, {delim_str}).', use_container_width=True, key=f'delim', on_click=autofill, args=(DELIM, VALUE))
    single_col_ratio = [2, 1, 1]  # text, to_key btn, to_val btn
    num_cols = 4
    num_col_cols = len(single_col_ratio)
    # i = rows, j = cols
    for i in range(len(ocr.results) // num_cols + 1):
        with st.expander(f'boxes row {i}', expanded=True):
            cols = st.columns(single_col_ratio * num_cols)
            for j in range(num_cols):
                r_idx = i * num_cols + j
                if r_idx >= len(ocr.results):
                    break
                with cols[j*num_col_cols]:
                    result = ocr.results[r_idx]
                    if result[2] > 0.8:
                        color = 'green'
                    elif result[2] > 0.5:
                        color = 'orange'
                    else:
                        color = 'red'
                    st.markdown(f'{r_idx}: :{color}[{result[1]}]')
                with cols[j*num_col_cols+1]:
                    st.button(f'{KEY}', help='Click to annotate',
                              on_click=autofill,
                              args=(result[1], KEY), key=f"key_{result[1]}_{r_idx}")
                with cols[j*num_col_cols+2]:
                    st.button(f'{VALUE}', help='Click to annotate', on_click=autofill,
                              args=(result[1], VALUE), key=f"value_{result[1]}_{r_idx}")
            st.button(f'Add a delimiter to values field (to manually type a delimiter, {delim_str}).', use_container_width=True, key=f'delim_{i}', on_click=autofill, args=(DELIM, VALUE))

    ##############################
    # Annotation Viewer
    ##############################
    with st.expander('View Images Again', expanded=st.session_state['show_img_twice']):
        st.image([sample_img, ocr.annotated_image])

    with st.container():
        st.markdown('## Current Annotations')
        st.write(st.session_state['annotations'])
    edit_col, next_col = st.columns(2)
    with next_col:
        st.button("Save and proceed to next Frame", use_container_width=True, key='cont_bottom',
                  disabled=len(st.session_state[VALUE]) + len(st.session_state['annotations']) == 0,
                  on_click=cycle_images, args=(indexed_images, guid, fnum, 'next'))
    with edit_col:
        ##############################
        # Annotation Editor 
        ##############################
        with st.expander('Edit Annotations', expanded=False):
            st.write("## Delete Annotation")
            opts = list(st.session_state['annotations'].keys())
            if not opts:
                st.warning('No annotations to delete')
            else:
                ks = st.multiselect(f'Select {KEY} to delete', options=opts,
                                 format_func=lambda x: f'"{x}"' if x else "EMPTY KEY")
                st.button(f"Delete {KEY}-{VALUE} Pair", on_click=delete_pairs, args=(ks,))
    # with st.expander('Data Navigator', expanded=st.session_state['show_navigator']):
    st.divider()
    with st.container():
        #############################
        # Image Navigation
        #############################
        sel_video_col, sel_frame_col, go_btn_col = st.columns((2, 2, 1))
        with sel_video_col:
            ops = list(guids.keys())
            idx = ops.index(guid)
            nav_guid_picker = st.selectbox('Select video', options=ops, index=idx,
                                           format_func=lambda x: f'{x} ({get_progress_guid(x, string=True)})')
        with sel_frame_col:
            ops = guids[nav_guid_picker]
            idx = ops.index(fnum) if nav_guid_picker == guid else 0
            nav_fnum_picker = st.selectbox('Select frame', options=guids[nav_guid_picker], index=idx,
                                           format_func=lambda x: f'{x} {"✅" if get_progress_guid_fnum(nav_guid_picker, x) else "❌"}')
        with go_btn_col:
            st.button('Go', help='Go to selected image', on_click=lambda: st.session_state.update(
                {'image_index': revindex_images[(nav_guid_picker, nav_fnum_picker)], 'annotations': None}))

