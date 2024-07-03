import streamlit as st
import pandas as pd
import cv2
import os
from collections import defaultdict
from utils.clean_ocr import clean_ocr
import re

st.set_page_config(page_title="LLM Adjudicator", layout="wide")

# -- SESSION STATE --

if "csv_file" not in st.session_state:
    uploaded_filename = st.text_input("Enter name of annotation file", placeholder="filename.csv", key="csv_filename")
    if uploaded_filename:
        st.session_state["csv_file"] = os.path.join("annotations/3-llm-in-progress", uploaded_filename)
        st.rerun()
    st.stop()

if "df" not in st.session_state:
    st.session_state["df"] = pd.read_csv(st.session_state["csv_file"])
    # Save the name as a string for server saving
    if not isinstance(st.session_state["csv_file"], str):
        st.session_state["csv_file"] = st.session_state["csv_file"].name
df = st.session_state["df"].dropna()

if "cleaned_text" not in df.columns:
    df["cleaned_text"] = df["textdocument"].map(clean_ocr)

output_fields = ["adjudicated", "accepted"]
for field in output_fields:
    if field not in df.columns:
        df[field] = False

def submit_final_annotations():
    df = st.session_state["df"]
    df = df[df["accepted"] == True]
    df.dropna(inplace=True)
    df = df[["guid", "timePoint", "scene_label", "cleaned_text", "silver_standard_annotation"]]
    df = df.rename(columns = {"silver_standard_annotation": "labels"})
    next_step_path = os.path.join("annotations/4-llm-complete", os.path.basename(st.session_state["csv_file"]))
    df.to_csv(next_step_path, index=False)
    os.remove(st.session_state["csv_file"])
    st.write("Annotations completed and submitted!")
    st.balloons()
    st.stop()

try:
    if st.session_state.get("jump") and int(st.session_state.get("jump")) < len(df) and int(st.session_state.get("jump")) >= 0:
        index = int(st.session_state.get("jump"))
    else:
        index = st.session_state.get("index", df.loc[df['adjudicated'] == False].index[0])
    st.session_state["index"] = index
    row = df.iloc[index]
except IndexError:
    st.header("All images adjudicated.")
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

st.header(f"Claude Adjudicator ({index}/{len(df)})", divider='gray')

sidebar = st.sidebar

# Skip instances where OCR was rejected (label already assigned)
if row.get("ocr_accepted", True) == False:
    st.session_state["index"] += 1
    st.rerun()

fpath = row["path"]
timepoint = row["timePoint"]
formatted_text = row["cleaned_text"]

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

def parse_silver_standard(anno):
    try:
        words = anno.split()
        split = [word.split("@") for word in words]
        phrases = []
        current_phrase = {}
        for word, tag in split:
            if tag == "O": continue
            b_i, role = tag[0], tag[1:]
            if b_i == "B":
                if current_phrase:
                    phrases.append(tuple(current_phrase.items())[0])
                    current_phrase = {}
                current_phrase[role] = word
            elif b_i == "I":
                current_phrase[role] += f" {word}"
        if current_phrase:
            phrases.append(tuple(current_phrase.items())[0])

        # Construct rfb dict
        rfb_dict = defaultdict(list)
        for tag, word in [phrase for phrase in phrases if "R" in phrase[0]]:
            role_index = tag.split(":")[1]
            fillers = [phrase[1] for phrase in phrases if phrase[0] == f"F:{role_index}"]
            rfb_dict[word] = fillers
        # Get leftover fillers
        for tag, word in [phrase for phrase in phrases if "F" in phrase[0]]:
            role_index = tag.split(":")[1]
            if not any([word in fillers for fillers in rfb_dict.values()]):
                rfb_dict[""].append(word)

        return rfb_dict
    except Exception as e:
        return {"error": "Unparsable string."}

def reject_callback():
    global df
    df.loc[index, "accepted"] = False
    st.session_state["df"] = df
    next_example()

def accept_callback():
    global df
    df.loc[index, "accepted"] = True
    st.session_state["df"] = df
    next_example()

def edit_callback():
    global df
    df.loc[index, "silver_standard_annotation"] = st.session_state["silver_standard"]
    st.session_state["df"] = df
    refresh_all()


silver_standard = row["silver_standard_annotation"]
silver_standard_tokenized = re.sub("@.*? |@.*$", " ", silver_standard).split()
formatted_text_tokenized = formatted_text.split()

if success:
    col1, col2 = st.columns(2)
    with col1:
        # Image panel
        st.image(image, channels="BGR")
        with col1.container(border=True):
            if silver_standard_tokenized != formatted_text_tokenized:
                st.write(f"#### :red[{formatted_text}]")
            else:
                st.write(f"#### {formatted_text}")
    with col2:
        with col2.container(border=True):
            jsonified = parse_silver_standard(silver_standard)
            st.text_input("Silver standard:", silver_standard, on_change=edit_callback, key="silver_standard")
            st.write(jsonified)
            # OCR text panel
        subcol1, subcol2 = st.columns(2)
        with subcol1:
            st.button("👎", key="reject", on_click=reject_callback, use_container_width=True)
        with subcol2:
            st.button("👍", key="accept", on_click=accept_callback, use_container_width=True)

else:
    st.write("Failed to retrieve frame from the specified timepoint.")


def next_example():
    global df, index
    df.loc[index, "adjudicated"] = True
    # df.loc[index, "ocr_accepted"] = not st.session_state["ocr_rejected"]
    df.to_csv(st.session_state["csv_file"], index=False)
    st.session_state["index"] = index = index + 1
    refresh_all()

def refresh_all():
    global df, index
    df.loc[index, "accepted"] = False
    df.loc[index, "adjudicated"] = False
    st.session_state["jump"] = None

def undo():
    global df, index
    if index > 0:
        refresh_all()
        st.session_state["index"] = index = index - 1
        df.loc[st.session_state["index"], "adjudicated"] = False
        refresh_all()
        df.to_csv(st.session_state["csv_file"], index=False)


with sidebar:
    st.button("Oops (Undo last annotation)", on_click=undo)

st.divider()

st.text_input("Jump to row", key="jump", placeholder="Enter row index")
st.write(df)