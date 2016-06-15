#!/usr/bin/env python
#

# import modules used here -- sys is a very standard one
from __future__ import print_function
import argparse
import csv
import logging
from collections import OrderedDict
from glob import glob
import os
import sys

import nibabel as nb
import json
import pandas as pd


# Gather our code in a main() function
from shutil import copy


def get_metadata_for_nifti(bids_root, path):

    sidecarJSON = path.replace(".nii.gz", ".json")

    pathComponents = os.path.split(sidecarJSON)
    filenameComponents = pathComponents[-1].split("_")
    sessionLevelComponentList = []
    subjectLevelComponentList = []
    topLevelComponentList = []
    ses = None;
    sub = None;

    for filenameComponent in filenameComponents:
        if filenameComponent[:3] != "run":
            sessionLevelComponentList.append(filenameComponent)
            if filenameComponent[:3] == "ses":
                ses = filenameComponent
            else:
                subjectLevelComponentList.append(filenameComponent)
                if filenameComponent[:3] == "sub":
                    sub = filenameComponent
                else:
                    topLevelComponentList.append(filenameComponent)

    topLevelJSON = os.path.join(bids_root, "_".join(topLevelComponentList))
    potentialJSONs = [topLevelJSON]

    subjectLevelJSON = os.path.join(bids_root, sub, "_".join(subjectLevelComponentList))
    potentialJSONs.append(subjectLevelJSON)

    if ses:
        sessionLevelJSON = os.path.join(bids_root, sub, ses, "_".join(sessionLevelComponentList))
        potentialJSONs.append(sessionLevelJSON)

    potentialJSONs.append(sidecarJSON)

    merged_param_dict = {}
    for json_file_path in potentialJSONs:
        if os.path.exists(json_file_path):
            param_dict = json.load(open(json_file_path, "r"))
            merged_param_dict.update(param_dict)

    return merged_param_dict


def dict_append(d, key, value):
    if key in d:
        d[key].append(value)
    else:
        d[key] = [value, ]


def run(args):

    print([line.split(" - ") for line in open(args.guid_mapping).read().split("\n") if line != ''])

    guid_mapping = dict([line.split(" - ") for line in open(args.guid_mapping).read().split("\n") if line != ''])

    suffix_to_scan_type = {"dwi": "MR diffusion",
                           "bold": "fMRI",
                           #""MR structural(MPRAGE)",
                           "T1w": "MR structural (T1)",
                           "PD": "MR structural (PD)",
                           #"MR structural(FSPGR)",
                           "T2w": "MR structural (T2)",
                           #PET;
                            #ASL;
                            #microscopy;
                            #MR structural(PD, T2);
                            #MR structural(B0 map);
                            #MR structural(B1 map);
                            #single - shell DTI;
                            #multi - shell DTI;
                           "epi": "Field Map",
                           "phase1": "Field Map",
                           "phase2": "Field Map",
                           "phasediff": "Field Map",
                           "magnitude1": "Field Map",
                           "magnitude2": "Field Map",
                           "fieldmap": "Field Map"
                           #X - Ray
                           }

    units_dict = {"mm": "Millimeters",
                  "sec": "Seconds",
                  "msec": "Milliseconds"}

    participants_df = pd.read_csv(os.path.join(args.bids_directory, "participants.tsv"), header=0, sep="\t")

    image03_dict = OrderedDict()
    for file in glob(os.path.join(args.bids_directory, "sub-*", "*", "sub-*.nii.gz")) + \
            glob(os.path.join(args.bids_directory, "sub-*", "ses-*", "*", "sub-*_ses-*.nii.gz")):

        metadata = get_metadata_for_nifti(args.bids_directory, file)

        bids_subject_id = os.path.split(file)[-1].split("_")[0][4:]
        dict_append(image03_dict, 'subjectkey', guid_mapping[bids_subject_id])
        dict_append(image03_dict, 'src_subject_id', bids_subject_id)

        sub = file.split("sub-")[-1].split("_")[0]
        if "ses-" in file:
            ses = file.split("ses-")[-1].split("_")[0]
            scans_file = (os.path.join(args.bids_directory, "sub-" + sub, "ses-" + ses, "sub-" + sub + "_ses-" + ses + "_scans.tsv"))
        else:
            scans_file = (os.path.join(args.bids_directory, "sub-" + sub, "sub-" + sub + "_scans.tsv"))

        if os.path.exists(scans_file):
            scans_df = pd.read_csv(scans_file, header=0, sep="\t")
        else:
            print("%s file not found - information about scan date required by NDA could not be found." % scans_file)
            sys.exit(-1)

        print(scans_df)
        for (_, row) in scans_df.iterrows():
            if file.endswith(row["filename"].replace("/", os.sep)):
                date = row.acq_time
                break

        sdate = date.split("-")
        ndar_date = sdate[1] + "/" + sdate[2].split("T")[0] + "/" + sdate[0]
        dict_append(image03_dict, 'interview_date', ndar_date)

        interview_age = int(round(list(participants_df[participants_df.participant_id == "sub-" + sub].age)[0], 0))
        dict_append(image03_dict, 'interview_age', interview_age)

        sex = list(participants_df[participants_df.participant_id == "sub-" + sub].sex)[0]
        dict_append(image03_dict, 'gender', sex)

        dict_append(image03_dict, 'image_file', file)

        suffix = file.split("_")[-1].split(".")[0]
        if suffix == "bold":
            description = suffix + " " + metadata["TaskName"]
        else:
            description = suffix
        dict_append(image03_dict, 'image_description', description)
        dict_append(image03_dict, 'scan_type', suffix_to_scan_type[suffix])
        dict_append(image03_dict, 'scan_object', "Live")
        dict_append(image03_dict, 'image_file_format', "NIFTI")
        dict_append(image03_dict, 'image_modality', "MRI")
        dict_append(image03_dict, 'transformation_performed', 'Yes')
        dict_append(image03_dict, 'transformation_type', 'BIDS2NDA')

        nii = nb.load(file)
        dict_append(image03_dict, 'image_num_dimensions', len(nii.shape))
        dict_append(image03_dict, 'image_extent1', nii.shape[0])
        dict_append(image03_dict, 'image_extent2', nii.shape[1])
        dict_append(image03_dict, 'image_extent3', nii.shape[2])
        if len(nii.shape) > 3:
            image_extent4 = nii.shape[3]
        else:
            image_extent4 = ""

        dict_append(image03_dict, 'image_extent4', image_extent4)
        if suffix == "bold":
            extent4_type = "time"
        elif suffix == "dwi":
            extent4_type = "diffusion weighting"
        else:
            extent4_type = ""
        dict_append(image03_dict, 'extent4_type', extent4_type)

        dict_append(image03_dict, 'image_resolution1', nii.header.get_zooms()[0])
        dict_append(image03_dict, 'image_resolution2', nii.header.get_zooms()[1])
        dict_append(image03_dict, 'image_resolution3', nii.header.get_zooms()[2])
        if len(nii.shape) > 3:
            image_resolution4 = nii.header.get_zooms()[3]
        else:
            image_resolution4 = ""
        dict_append(image03_dict, 'image_resolution4', image_resolution4)

        dict_append(image03_dict, 'image_unit1', units_dict[nii.header.get_xyzt_units()[0]])
        dict_append(image03_dict, 'image_unit2', units_dict[nii.header.get_xyzt_units()[0]])
        dict_append(image03_dict, 'image_unit3', units_dict[nii.header.get_xyzt_units()[0]])
        if len(nii.shape) > 3:
            image_unit4 = units_dict[nii.header.get_xyzt_units()[1]]
            if image_unit4 == "Milliseconds":
                TR = nii.header.get_zooms()[3]/1000.
            else:
                TR = nii.header.get_zooms()[3]
            dict_append(image03_dict, 'mri_repetition_time_pd', TR)
        else:
            image_unit4 = ""
            dict_append(image03_dict, 'mri_repetition_time_pd', metadata.get("RepetitionTime", 0))
        dict_append(image03_dict, 'image_unit4', image_unit4)

        if file.split(os.sep)[-1].split("_")[1].startswith("ses"):
            visit = file.split(os.sep)[-1].split("_")[1][4:]
        else:
            visit = ""

        dict_append(image03_dict, 'visit', visit)



    image03_df = pd.DataFrame(image03_dict)

    with open(os.path.join(args.output_directory, "image03.txt"), "w") as out_fp:
        out_fp.write('"image"\t"3"\n')
        image03_df.to_csv(out_fp, sep="\t", index=False, quoting=csv.QUOTE_ALL)

def main():
    class MyParser(argparse.ArgumentParser):
        def error(self, message):
            sys.stderr.write('error: %s\n' % message)
            self.print_help()
            sys.exit(2)

    parser = MyParser(
        description="BIDS to NDA converter.",
        fromfile_prefix_chars='@')
    # TODO Specify your real parameters here.
    parser.add_argument(
        "bids_directory",
        help="Location of the root of your BIDS compatible directory",
        metavar="BIDS_DIRECTORY")
    parser.add_argument(
        "guid_mapping",
        help="Path to a text file with participant_id to GUID mapping. You will need to use the "
             "GUID Tool (https://ndar.nih.gov/contribute.html) to generate GUIDs for your participants.",
        metavar="GUID_MAPPING")
    parser.add_argument(
        "output_directory",
        help="Directory where NDA files will be stored",
        metavar="OUTPUT_DIRECTORY")
    args = parser.parse_args()

    run(args)
    print("Metadata extraction complete.")


if __name__ == '__main__':
    main()
