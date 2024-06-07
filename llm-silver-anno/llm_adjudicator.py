import streamlit as st
import pandas as pd
import cv2
import os
from collections import defaultdict

st.set_page_config(page_title="LLM Adjudicator", layout="wide")

# -- SESSION STATE --

if "csv_file" not in st.session_state:
    uploaded_file = st.file_uploader("Upload CSV file", type=["csv"], key="filepath")
    if uploaded_file is not None:
        if os.path.exists(uploaded_file.name):
            st.session_state["csv_file"] = uploaded_file.name
        else:
            st.session_state["csv_file"] = uploaded_file
        st.rerun()
    st.stop()

if "df" not in st.session_state:
    st.session_state["df"] = pd.read_csv(st.session_state["csv_file"])
    # Save the name as a string for server saving
    if not isinstance(st.session_state["csv_file"], str):
        st.session_state["csv_file"] = st.session_state["csv_file"].name
df = st.session_state["df"]

try:
    if st.session_state.get("jump") and int(st.session_state.get("jump")) < len(df) and int(st.session_state.get("jump")) >= 0:
        index = int(st.session_state.get("jump"))
    else:
        index = st.session_state.get("index", df.loc[df['adjudicated'] == False].index[0])
    st.session_state["index"] = index
except IndexError:
    st.header("All images adjudicated!")
    st.balloons()
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

row = df.iloc[index]
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
        return {"error": "Unparsable string. Please reject."}

def reject_callback():
    global df
    df.loc[index, "accepted"] = False
    next_example()

def accept_callback():
    global df
    df.loc[index, "accepted"] = True
    next_example()

def edit_callback():
    global df
    df.loc[index, "silver_standard_annotation"] = st.session_state["silver_standard"]


silver_standard = row["silver_standard_annotation"]

if success:
    col1, col2 = st.columns(2)
    with col1:
        # Image panel
        st.image(image, channels="BGR")
        with col1.container(border=True):
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