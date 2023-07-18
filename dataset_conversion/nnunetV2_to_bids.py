"""
Converts nnUNetv2 dataset format to the BIDS-structured dataset. Full details about
the format can be found here: https://github.com/MIC-DKFZ/nnUNet/blob/master/documentation/dataset_format.md

Théo Mathieu
"""

import argparse
import numpy as np
import shutil
import pathlib
from pathlib import Path
import datetime
import json
import os
import nibabel as nib


def get_parser():
    # parse command line arguments
    parser = argparse.ArgumentParser(description='Convert BIDS-structured dataset to nnUNetV2 database format.')
    parser.add_argument('--path-data', required=True, help='Path to nnUNet dataset. Example: ~/data/dataset')
    parser.add_argument('--path-out', required=True, help='Path to output directory. Example: ~/data/dataset-bids')
    parser.add_argument('--suffix', required=True, help='Suffix of the label file Example: sub-003_T2w_SUFFIX.nii.gz')
    parser.add_argument('--copy', '-cp', type=bool, default=False,
                        help='Making symlink (False) or copying (True) the files in the Bids dataset. '
                             'This option only affects the image file, the label file is copied regardless of the '
                             ' option, default = False. Example for symlink: ø, Example for copy: --copy')
    return parser


def separate_labels(label_file, original_label, dataset_label, label_new_dir, dataset_name):
    """
    Function to make one nifti file for each possible voxel value

    Args:
        label_file (str): Path to the label file '...label-'
        original_label (str): Path to the label file in the nnUNetV2 dataset
        dataset_label (str): Labels keys from the dataset.json file
        label_new_dir (str): Folder for the label file in Bids format
        dataset_name (str): nnUNetV2 dataset name
    """
    # (this issue: https://github.com/ivadomed/data-conversion/pull/15#issuecomment-1599351103)
    value_label = {v: k for k, v in dataset_label.items()}
    nifti_file = nib.load(original_label)
    data = nifti_file.get_fdata()
    for value in value_label.keys():
        if value != 0:
            seg_name = value_label[value]
            voxel_val = np.zeros_like(data, dtype=np.int16)
            if type(value) == list:
                for sub_val in value:
                    voxel_val[data == sub_val] = 1
            else:
                voxel_val[data == value] = 1
            voxel_img = nib.Nifti1Image(voxel_val, nifti_file.affine, nifti_file.header)
            path_to_label = os.path.join(label_new_dir, f"{label_file}-{seg_name}_seg.nii.gz")
            nib.save(voxel_img, path_to_label)
            json_name = f"{label_file}-{seg_name}_seg.json"
            write_json(os.path.join(label_new_dir, json_name), dataset_name)
    path_to_label = os.path.join(label_new_dir, f"{label_file}-softseg.nii.gz")
    shutil.copy2(original_label, path_to_label)
    json_name = f"{label_file}-softseg.json"
    write_json(os.path.join(label_new_dir, json_name), dataset_name)


def write_json(filename, dataset_name):
    """
    Save a json file with the label image created

    Args:
        filename (str): Json filename (with path)
        dataset_name (str): Name of the dataset
    """
    data = {
        "Author": f"nnUNetV2_to_bids.py from nnUNet dataset {dataset_name}",
        "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Reviewer": "NAME",
        "Review_Date": "YYYY-MM-DD, HH:MM:SS"
    }

    # Write the data to the JSON file
    with open(filename, "w") as file:
        json.dump(data, file, indent=4)

def get_subject_info(file_name, contrast_dict):
    """
    Get different information about the current subject

    Args:
        file_name (str): Filename corresponding to the subject image
        contrast_dict (dict): Dictionary, key channel_names from dataset.json

    Returns:
        sub_names (str): Name of the subject. Example: sub-milan002
        ses (str): ses name
        bids_nb (str): subject number in the BIDS dataset
        info[2] (str): Contrast value in BIDS format. Example 0001
        contrast (str): Image contrast (T2w, T1, ...)

    """
    name = file_name.split(".")[0]
    info = name.split("_")
    bids_nb = info[-2]
    contrast = info[-1]
    if len(info) == 4:
        ses = info.pop(1)
    else:
        ses = None
    sub_name = "_".join(info[:-2])
    contrast = contrast.lstrip('0')
    if contrast == '':
        contrast = '0'
    contrast_bids = contrast_dict[contrast]
    return sub_name, ses, bids_nb, contrast, contrast_bids


def main():
    parser = get_parser()
    args = parser.parse_args()
    copy = args.copy
    suffix =args.suffix
    root = Path(os.path.abspath(os.path.expanduser(args.path_data)))
    path_out = Path(os.path.abspath(os.path.expanduser(args.path_out)))
    with open(os.path.join(root, "dataset.json"), 'r') as json_file:
        dataset_info = json.load(json_file)
    for folder in [("imagesTr", "labelsTr"), ("imagesTs", "labelsTs")]:
        for image_file in os.listdir(f"{root}/{folder[0]}/"):
            if not image_file.startswith('.'):
                sub_name, ses, bids_nb, bids_contrast, contrast = get_subject_info(image_file,
                                                                                   dataset_info["channel_names"])
                if ses: # Multiple Session per subject
                    image_new_dir = os.path.join(path_out, sub_name, ses, 'anat')
                    label_new_dir = os.path.join(path_out, 'derivatives/labels', sub_name, ses, 'anat')
                    pathlib.Path(image_new_dir).mkdir(parents=True, exist_ok=True)
                    pathlib.Path(label_new_dir).mkdir(parents=True, exist_ok=True)
                    bids_image_name = f"{sub_name}_{ses}_{contrast}.nii.gz"
                    label_name = f"{sub_name}_{ses}_{bids_nb}.nii.gz"
                    label_file = os.path.join(root, folder[1], label_name)
                    separate_labels(f"{sub_name}_{ses}_{contrast}_{suffix}", label_file, dataset_info["labels"], label_new_dir,
                                    str(root).split('/')[-1])
                else:
                    image_new_dir = os.path.join(path_out, sub_name, 'anat')
                    label_new_dir = os.path.join(path_out, 'derivatives/labels', sub_name, 'anat')
                    pathlib.Path(image_new_dir).mkdir(parents=True, exist_ok=True)
                    pathlib.Path(label_new_dir).mkdir(parents=True, exist_ok=True)
                    bids_image_name = f"{sub_name}_{contrast}.nii.gz"
                    label_name = f"{sub_name}_{bids_nb}.nii.gz"
                    label_file = os.path.join(root, folder[1], label_name)
                    separate_labels(f"{sub_name}_{contrast}_{suffix}", label_file, dataset_info["labels"], label_new_dir,
                                    str(root).split('/')[-1])
                image_file = os.path.join(root, folder[0], image_file)
                if copy:
                    shutil.copy2(os.path.abspath(image_file), os.path.join(image_new_dir, bids_image_name))
                else:
                    os.symlink(os.path.abspath(image_file), os.path.join(image_new_dir, bids_image_name))


if __name__ == '__main__':
    main()
