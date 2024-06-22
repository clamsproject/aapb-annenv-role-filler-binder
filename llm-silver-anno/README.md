# LLM-based annotation

This directory contains the tools for LLM-based RFB annotation. The workflow is as follows:

1. - Get a batch of OCR annotations from video frames that you want to use for training data.
    - Run the batch through the `scenes-with-text` app to get scene labels, and only keep `credits` and `chyrons`
    - Using the streamlit annotation environment `review_ocr.py`, correct misclassifications and throw out OCR results that are too poor
2.  - Feed OCR results into a cloud-based LLM (Claude-3 Haiku was used for the current annotation batch) to get sequence-labelled "silver standard" annotations.
    - Using the streamlit adjudication environment `llm_adjudicator.py`, either accept, correct, or reject the LLM's annotations
3. Feed the corrected annotations to the RFB model

## Running the annotation environments

Both annotation environments can be run using `streamlit run <filename>`. Since the apps gather frames from AAPB GUIDs and timepoints, **they must be run from a lab server if you do not have the videos saved locally!** Running them from your local device will cause an error.

## Annotation format

RFB annotations are BIO-formmated (Beginning/inside/outside), where role tags are co-indexed with filler tags. In practice, this looks like:

`Indianapolis@O CLARENCE@BF:1 PAGE@IF:1 Chitago@BR:1 Tribune@IR:1`

In this case, the role "Chitago Tribune" is co-indexed with its corresponding filler "CLARENCE PAGE". OCR mistakes are not corrected, and irrelevant words ("Indianapolis") are tagged "O" with no index.


## Workflow / example

This directory contains an example input file in `examples/ex.csv`. This file contains columns `guid`, `timePoint`, `scene_label`, `confidence`, and `textdocument` -- and is meant to represent a ready-to-annotate file that has been generated using SWT.

This section will walk through the workflow steps using this example file; the same steps will apply to any file with the same format.

### 1. Get the filepaths for each video (skip if `path` column already present in data)

This can be done using the `get_paths.py` util script. Before running, make sure your device can access a machine running the [AAPB datahousing server](https://github.com/clamsproject/aapb-brandeis-datahousing) via HTTP. Then, run:

```
python utils/get_paths.py --input_file examples/ex.csv --output_file anno.csv --url http://example.com:12345
```

The --url param should be the full URL where the datahousing server can be accessed, including port.

(Note: in this example, we will be using `anno.csv` as the filename. However, any filename will work -- just substitute `anno.csv` for your file in subsequent instructions)

### 2. Perform OCR annotation

Run the OCR annotation environment with:

```
streamlit run ocr_reviewer.py
```

Accessing the environment at the specified URL, you can then upload your `anno.csv` file one of two ways:

- Upload the file using the streamlit file uploader. This will create a copy of the file in the `annotations/1-ocr-in-progress` directory, which will store the completed annotations
- Place the file in the `annotations/1-ocr-in-progress`, then enter your filename (`anno.csv`) in the text box.

If you need to return to partially completed annotations, just enter the filename in the text box to continue annotating.

See the *Guidelines* section for instructions on annotation. Once completed, press "Submit Annotations" to remove extraneous columns, delete rejected rows, and format file for future annotations. This will move `anno.csv` from `1-ocr-in-progress` to `2-ocr-complete`, indicating that it is ready for the next step in the pipeline.

### 3. Use Claude to get "silver standard" annotations

This can be done using the `llm_annotate.py` util script. Before running this, make sure you have an [Anthropic API key](https://docs.anthropic.com/en/api/getting-started) saved under the `ANTHROPIC_API_KEY` environment variable by modifying `.env`.

Now, run:

```
python utils/llm_annotate.py --input_file annotations/2-ocr-complete/anno.csv
```

This will use the Claude API to add "silver standard" LLM annotations to the file. The file will then be moved to `3-llm-in-progress` to indicate it is ready for adjudication.

### 4. Perform LLM adjudication

"Adjudicate" the LLM annotations by accepting, rejecting, or correcting. Start up the server by running:

```
python llm_adjudicator.py
```

Begin annotating your file by entering the filename in the text box (`anno.csv`). See *Guidelines* for more information. When you are finished annotating, hit "Submit Annotations." This will perform cleanup on the file and move it to the `4-llm-complete` subdirectory.

The completed file will have the following columns:

| Field | Description |
|-------|-------------|
| guid | AAPB GUID of the source video  |
| timePoint | Frame number of the image  |
| scene_label | SWT-assigned scene label |
| cleaned_text | OCR text cleaned by removing rows without alphabetical characters and discarding newlines. |
| labels | Final BIO-labelled annotations |



## Guidelines

### OCR Reviewer:

The OCR Reviewer allows for a few annotation options for each image:

- **Swap scene type** between credit and chyron if the scene has been misclassified by SWT.
- **Reject OCR** if the OCR results are so poor in quality that they would be useless as input to an RFB model. This is equivalent to sequence-tagging the text as a series of "O"s, i.e. no viable RFB results found.
- **Delete** if the true scene type is not credit or chyron, or if the OCR results are an edge case that necessitate throwing them out from the batch entirely (this should not happen very often).
- **Submit** if all needed changes have been made, or if the results were correct initially.

### LLM Adjudicator:

The LLM adjudicator is comparitively more simple, with options to accept or reject the LLM's annotations. The user can also edit the BIO-formatted annotations directly -- after editing, select accept ("👍") to submit the changes. The tags will be automatically parsed to JSON format for real-time preview.