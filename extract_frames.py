import argparse
import re
from mmif import Mmif, View, AnnotationTypes, Document, DocumentTypes
from mmif.utils import video_document_helper as vdh
from PIL import Image

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mmif', help='path to mmif file')
    parser.add_argument('--images', help='path to image directory')

    args = parser.parse_args()

    mmif = Mmif(open(args.mmif).read())
    vd = mmif.get_documents_by_type(DocumentTypes.VideoDocument)[0]
    guid = re.search(r'cpb-aacip[-_]\d{3}-[0-9a-z]+', vd.properties.location).group(0)
    # video_name = vd.properties.location_path_resolved()
    view = mmif.get_views_for_document(vd.properties.id)[0]
    annotations = view.get_annotations(AnnotationTypes.TimeFrame)

    image_dir = args.images
    # Save images to image_dir in the format document_id.frame_number.png with leading zeros
    images = []
    for timeframe in annotations:
        frame_nums = vdh.sample_frames(timeframe.get_property('start'), timeframe.get_property('end'), 15)
        frames = vdh.extract_frames_as_images(vd, frame_nums)
        # Add frame_num, frame to images
        for frame_num, frame in zip(frame_nums, frames):
            images.append((frame_num, frame))

    for frame_num, frame in images:
        frame = Image.fromarray(frame)
        frame.save(f'{image_dir}/{guid}.{str(frame_num).zfill(4)}.png')
