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

You can upload an annotation file from your local device to the streamlit uploader. Once you start annotating, a copy with all annotated changes will be stored in the llm-silver-anno directory on the server. If you need to come back and make later changes, you can use the same local file -- even if the local file is unannotated, it will reference the server copy and pick up from where you left off.

## Data format

Both `llm_adjudicator.py` and `review_ocr.py` expect input data in CSV format. Example files for both are stored in the `examples` directory. The apps expect files with the following columns:

### OCR Reviewer:
- guid
    - AAPB GUID of the source video
- timePoint
    - Frame number of the image
- scene_label
    - SWT-assigned scene label
- confidence
    - SWT confidence score
- textdocument
    - The OCR content
- path
    - Path to the source video
- ocr_accepted
    - (after annotation) whether the OCR results were accepted or labeled all "O"s (in NER terms)
- deleted
    - (after annotation) files are marked for deletion if the OCR is a strange edge case or the true frame type is not a credit or chyron
- annotated
    - (after annotation) whether the frame has been reviewed/annotated
- label_adjusted
    - (after annotation) whether the scene type was adjusted by the annotator

#### LLM Adjudicator
- guid
    - (carried over from OCR reviewer)
- timePoint
    - (carried over from OCR reviewer)
- scene_label
    - (carried over from OCR reviewer)
- confidence
    - (carried over from OCR reviewer)
- textdocument
    - (carried over from OCR reviewer)
- path
    - (carried over from OCR reviewer)
- ocr_accepted
    - (carried over from OCR reviewer)
- deleted
    - (carried over from OCR reviewer)
- frameType
    - (carried over from OCR reviewer)
- cleaned_text
    - the textdocument with any lines not containing alphanumeric characters removed (to clean results for training)
- silver_standard_annotation
    - The LLM output in indexed BIO format (pseudo NER). It should be in this format: 
    
        `Barber@BF:1 Conable@IF:1 Host@BR:1`

        Where matching roles and fillers are co-indexed
- adjudicated
    - (after adjudication) whether adjudication has been performed
- accepted
    - (after adjudication) whether silver standard annotations were accepted
