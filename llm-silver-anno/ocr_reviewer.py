import streamlit as st
import pandas as pd
import cv2
from streamlit_extras.tags import tagger_component
from streamlit_shortcuts import add_keyboard_shortcuts
import os
from utils.clean_ocr import clean_ocr

st.set_page_config(page_title="SWT OCR Annotator", layout="wide")

# -- SESSION STATE --

if "csv_file" not in st.session_state:
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"], key="filepath")
    uploaded_filename = st.text_input("Or, enter name of already uploaded annotation file", placeholder="filename.csv", key="csv_filename")
    if uploaded_filename:
        st.session_state["csv_file"] = os.path.join("annotations/1-ocr-in-progress", uploaded_filename)
        st.rerun()
    elif uploaded_file is not None:
        if os.path.exists(os.path.join("annotations/1-ocr-in-progress", uploaded_file.name)):
            st.session_state["csv_file"] = os.path.join("annotations/1-ocr-in-progress", uploaded_file.name)
        else:
            st.session_state["csv_file"] = uploaded_file
        st.rerun()
    st.stop()

if "df" not in st.session_state:
    st.session_state["df"] = pd.read_csv(st.session_state["csv_file"])
    # Save the name as a string for server saving
    if not isinstance(st.session_state["csv_file"], str):
        st.session_state["csv_file"] = os.path.join("annotations/1-ocr-in-progress", st.session_state["csv_file"].name)

df = st.session_state["df"]

# Add annotation fields if not already present
annotation_fields = ["ocr_accepted", "deleted", "label_adjusted", "annotated"]
for field in annotation_fields:
    if field not in df.columns:
        df[field] = False
if "cleaned_text" not in df.columns:
    df["cleaned_text"] = df["textdocument"].apply(clean_ocr)

def submit_final_annotations():
    df = st.session_state["df"]
    df = df[df["deleted"] == False]
    df = df.drop(columns=["annotated", "label_adjusted", "deleted", "confidence"], inplace=False)
    df = df.dropna(inplace=False)
    next_step_path = os.path.join("annotations/2-ocr-complete", os.path.basename(st.session_state["csv_file"]))
    df.to_csv(next_step_path, index=False)
    os.remove(st.session_state["csv_file"])
    st.write("Annnotations completed and submitted!")
    st.balloons()
    st.stop()

try:
    if st.session_state.get("jump") and int(st.session_state.get("jump")) < len(df) and int(st.session_state.get("jump")) >= 0:
        index = int(st.session_state.get("jump"))
    else:
        index = st.session_state.get("index", df.loc[df['annotated'] == False].index[0])
    st.session_state["index"] = index
except IndexError:
    st.header("All images annotated.")
    st.warning("Warning: submitted annotation files cannot be re-annotated. If you need to make changes before submitting, use 'Jump to Row' button below.")
    st.button("Submit Annotations", on_click=submit_final_annotations)
    st.text_input("Jump to row", key="jump", placeholder="Enter row index")
    st.write(df)
    st.stop()

label_adjusted = st.session_state.get("label_adjusted", False)
st.session_state["label_adjusted"] = label_adjusted

ocr_rejected = st.session_state.get("ocr_rejected", False)
st.session_state["ocr_rejected"] = ocr_rejected

if "scene_label" not in st.session_state:
    st.session_state["scene_label"] = df["scene_label"].iloc[index]

# ----------------------

st.header(f"SWT OCR Annotator ({index}/{len(df)})", divider='gray')

sidebar = st.sidebar
with sidebar:
    submit_key = st.text_input("Submit Key", key="submit", value="y")
    reject_key = st.text_input("Reject Key", key="reject", value="x")
    swap_key = st.text_input("Swap Key", key="swap", value="s")
    delete_key = st.text_input("Delete Key", key="delete", value="Ctrl+Shift+X")
    st.divider()


# Shortcuts for key logging
keyboard_shortcuts = [f"**{submit_key}**: Submit", f"**{reject_key}**: Reject OCR (toggle)", f"**{swap_key}**: Swap frame type (toggle)", f"**{delete_key}**: Remove (invalid scene type)"]
tagger_component(
    "",
    keyboard_shortcuts,
    color_name=["rgb(38, 39, 48)", 'red', "blue", "orange"],
)
add_keyboard_shortcuts({
    submit_key: 'Submit',
    reject_key: 'Reject',
    swap_key: 'Swap',
    delete_key: 'Delete'
})

row = df.iloc[index]
fpath = row["path"]
timepoint = row["timepoint"]
scene_label = row["scene_label"]
formatted_text = row["cleaned_text"].replace("\n", "<br>")

# Get frame image from video
frame = cv2.VideoCapture(fpath)
frame.set(cv2.CAP_PROP_POS_MSEC, timepoint)
success, image = frame.read()

# Set styles for annotation panel
st.markdown("""
<style>
.big-font {
    font-size:25px !important;
}
.rejected {
    color: rgb(255, 75, 75);
}
</style>
""", unsafe_allow_html=True)

if success:
    col1, col2 = st.columns(2)
    with col1:
        # Image panel
        st.image(image, channels="BGR")
    with col2:
        with col2.container(border=True):
            # Scene label panel
            if label_adjusted:
                st.write(f"## :blue[{st.session_state['scene_label']}]")
            else:
                st.write(f"## {st.session_state['scene_label']} (confidence {row['confidence']:.2f})")
        with col2.container(border=True):
            # OCR text panel
            if ocr_rejected:
                st.markdown(f'<p class="big-font rejected">{formatted_text}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p class="big-font">{formatted_text}</p>', unsafe_allow_html=True)

else:
    st.write("Failed to retrieve frame from the specified timepoint.")

def submit_callback():
    global df
    df.loc[index, "ocr_accepted"] = not st.session_state["ocr_rejected"]
    next_example()

def reject_callback():
    ocr_rejected = not st.session_state["ocr_rejected"]
    st.session_state["ocr_rejected"] = ocr_rejected

def swap_callback():
    global df
    new_scene_label = "credits" if st.session_state["scene_label"] == "chyron" else "chyron"
    df.loc[index, "scene_label"] = new_scene_label
    df.loc[index, "label_adjusted"] = not st.session_state["label_adjusted"]
    st.session_state["scene_label"] = new_scene_label
    st.session_state["label_adjusted"] = not st.session_state["label_adjusted"]

def delete_callback():
    global df
    df.loc[index, "deleted"] = True
    next_example()

def next_example():
    global df, index
    df.loc[index, "annotated"] = True
    df.loc[index, "ocr_accepted"] = not st.session_state["ocr_rejected"]
    df.to_csv(st.session_state["csv_file"], index=False)
    st.session_state["index"] = index = index + 1
    refresh_all()

def refresh_all():
    global df, index
    df.loc[index, "deleted"] = False
    df.loc[index, "label_adjusted"] = False
    df.loc[index, "ocr_accepted"] = False
    st.session_state["ocr_rejected"] = False
    st.session_state["scene_label"] = df["scene_label"].iloc[st.session_state["index"]]
    st.session_state["label_adjusted"] = df.loc[st.session_state["index"], "label_adjusted"]
    st.session_state["jump"] = None

def undo():
    global df, index
    if index > 0:
        refresh_all()
        st.session_state["index"] = index = index - 1
        df.loc[st.session_state["index"], "annotated"] = False
        refresh_all()
        df.to_csv(st.session_state["csv_file"], index=False)

# Custom CSS to improve alignment issues
st.markdown("""
            <style>
                div[data-testid="column"] {
                    width: fit-content !important;
                    flex: unset;
                }
                div[data-testid="column"] * {
                    width: fit-content !important;
                }

            </style>
            """, unsafe_allow_html=True)


button_col1, button_col2, button_col3, button_col4 = st.columns(4)
with button_col1:
    st.button("Submit", on_click=submit_callback)
with button_col2:
    st.button("Reject", on_click=reject_callback)
with button_col3:
    st.button("Swap", on_click=swap_callback)
with button_col4:
    st.button("Delete", on_click=delete_callback)


with sidebar:
    st.button("Oops (Undo last annotation)", on_click=undo)

st.divider()

st.text_input("Jump to row", key="jump", placeholder="Enter row index")
st.write(df)