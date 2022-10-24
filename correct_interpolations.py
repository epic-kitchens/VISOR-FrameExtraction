#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: Ahmad Dar Khalil - University of Bristol
Date: 24/oct/2022
"""

import json
import glob
import os
import sys
from tqdm import tqdm
import argparse
import secrets

def parse_args():
    parser = argparse.ArgumentParser(description='Interpolation correction script')
    parser.add_argument('--input_dir', type=str, default='VISOR/Interpolations-DenseAnnotations/train', help='path to the interpolation JSONs')
    parser.add_argument('--output_dir', type=str, default='VISOR/Interpolations-DenseAnnotations/train', help='path to save the corrected interpolation JSONs')
    return parser.parse_args()

def correct_interpolations(in_folder, out_folder, specific_json_list=[]):
    os.makedirs(out_folder, exist_ok=True)

    for infile in tqdm(sorted(glob.glob(in_folder + '/*.json'))):
        if specific_json_list == [] or ('_'.join(os.path.basename(infile).split('_')[:2]) in specific_json_list):
            new_json = {"info": {"Dataset Name": "VISOR", "Release Date": "Aug 2022", "URL": "https://epic-kitchens.github.io/VISOR", "details": "In each mask, type=0: automatically generated mask, type=1: filtered ground truth. All annotations generated in 854x480 resolution"}, "video_annotations":[]}
            new_data = []
            f = open(infile)
            # returns JSON object as a dictionary
            data = json.load(f)
            data = sorted(data["video_annotations"], key=lambda k: k['image']['image_path'])
            
            adjusted_interpolation_start_frame = {}
            for datapoint in data:
                image = datapoint['image']['name']
                interpolation = datapoint['image']['interpolation']
                    
                if image[0] == 'P':

                    start_frame = datapoint['image']['interpolation_start_frame']
                    end_frame  = datapoint['image']['interpolation_end_frame']
                    
                    current_frame_index = int(image.split('_')[-1][:-4])
                    start_frame_index = int(start_frame.split('_')[-1][:-4])
                    #end_frame_index = int(end_frame.split('_')[-1][:-4])
                    
                    if interpolation in adjusted_interpolation_start_frame.keys():
                        datapoint['image']['interpolation_start_frame']  = adjusted_interpolation_start_frame[interpolation]
                        start_frame = datapoint['image']['interpolation_start_frame']

                    else:
                        datapoint['image']['interpolation_start_frame']  = image
                        start_frame = image
                        adjusted_interpolation_start_frame = {}
                        adjusted_interpolation_start_frame[interpolation] = image
                        if datapoint['image']['interpolation_start_frame'] == datapoint['image']['name']:
                            for object in datapoint["annotations"]:
                                object["type"] = 1

                    if start_frame[0] != 'P':
                        datapoint['image']['interpolation_start_frame'] = '_'.join(start_frame.split('_')[1:])#
                        #print(start_frame ,'=>',datapoint['image']['interpolation_start_frame'])
                        if datapoint['image']['interpolation_start_frame'] == datapoint['image']['name']:
                            for object in datapoint["annotations"]:
                                object["type"] = 1

                    if end_frame[0] != 'P':
                        
                        datapoint['image']['interpolation_end_frame'] = '_'.join(end_frame.split('_')[1:])
                        print(end_frame ,'=>',datapoint['image']['interpolation_end_frame'])
                        sys.exit(0)
                        if datapoint['image']['interpolation_end_frame'] == datapoint['image']['name']:
                            for object in datapoint["annotations"]:
                                object["type"] = 1
                    new_data.append(datapoint)

            file  = open(infile.replace(in_folder,out_folder),'w')
            new_json['video_annotations'] = new_data
            out_data = json.dumps(new_json)
            file.write(str(out_data))
            file.close()
    
def add_mssing_sparse_annotations(interpolations_dir,sparse_json_names):

    for json_file in tqdm(sparse_json_names) :
        if os.path.exists(os.path.join(interpolations_dir,json_file+'_interpolations.json')):
            new_json = {"info": {"Dataset Name": "VISOR", "Release Date": "Aug 2022", "URL": "https://epic-kitchens.github.io/VISOR", "details": "In each mask, type=0: automatically generated mask, type=1: filtered ground truth. All annotations generated in 854x480 resolution"}, "video_annotations":[]}
            new_data = []
            f = open(os.path.join(interpolations_dir,json_file+'_interpolations.json'))
            data = json.load(f)
            data = sorted(data["video_annotations"], key=lambda k: k['image']['image_path'])
            start_end_frames = {'start':{},'end':{}}
            
            for datapoint in data:
                new_datapoint = {}
                new_datapoint['image'] = {}
                new_datapoint['annotations'] = []
                
                if (datapoint["annotations"] and datapoint["annotations"][0]["type"] == 1) or  (datapoint['image']['name'] == datapoint['image']['interpolation_start_frame']) or (datapoint['image']['name'] == datapoint['image']['interpolation_end_frame']):
                    image = datapoint['image']['name']
                    sparse_image_object = find_object_by_frame(json_file,image.replace('png','jpg'))
                    
                    if sparse_image_object == None:
                        entity_names = []
                        for object in datapoint["annotations"]:
                            object['type'] = 0
                            entity_names.append(object['name'])
                        
                        #find the closest sparse frame
                        sparse_close_image = find_object_by_close_frame(json_file,image.replace('png','jpg'))
                        if sparse_close_image == None:
                            print('No sparse images found!!!!')
                            sys.exit(1)
                        
                       
                        new_datapoint['image'] = datapoint['image'].copy()
                        new_datapoint['image']['name'] = sparse_close_image['image']['name'].replace('.jpg','.png')
                        new_datapoint['image']['image_path'] =  sparse_close_image['image']['image_path'].replace('.jpg','.png')
                        
                        if sparse_close_image['image']['name']< datapoint['image']['name']:
                            start_end_frames['start'][datapoint['image']['interpolation']] = new_datapoint['image']['name']
                        elif sparse_close_image['image']['name'] >  datapoint['image']['name']:
                            start_end_frames['end'][datapoint['image']['interpolation']] = new_datapoint['image']['name']                    
                        
                        for object in sparse_close_image["annotations"]:
                            if object['name'] in entity_names:
                                object['type'] = 1
                                object['key'] = secrets.token_hex(16)
                                for unwanted_key in object.keys() - datapoint["annotations"][0].keys():
                                    del object[unwanted_key]
                                new_datapoint['annotations'].append(object)
                                
                        new_data.append(new_datapoint)      
                        
                        
                new_data.append(datapoint)
            
            #then fix all start and end frames for the interpolations
            new_data_edited = []
            for datapoint in new_data:
                if datapoint['image']['interpolation'] in start_end_frames['start']:
                    datapoint['image']['interpolation_start_frame'] = start_end_frames['start'][datapoint['image']['interpolation'] ]
                if datapoint['image']['interpolation'] in start_end_frames['end']:
                    datapoint['image']['interpolation_end_frame'] = start_end_frames['end'][datapoint['image']['interpolation'] ]
                new_data_edited.append(datapoint)
            
            file  = open(os.path.join(interpolations_dir,json_file+'_interpolations.json'),'w')
            new_json['video_annotations'] = sorted(new_data_edited, key=lambda k: k['image']['image_path'])
            out_data = json.dumps(new_json)
            file.write(str(out_data))
            file.close()
        

def find_object_by_close_frame(json_object,image_name):
    f = open(os.path.join(json_object+'.json'))
    data = json.load(f)
    data = sorted(data["video_annotations"], key=lambda k: k['image']['image_path'])
    for datapoint in data:
        image = datapoint['image']['name']
        lookup_image = image_name
    
        current_frame_index = int(image.split('_')[-1][:-4])
        lookup_image_index = int(lookup_image.split('_')[-1][:-4])
        
        if abs(current_frame_index - lookup_image_index) <= 2:
            return datapoint
    return None

def find_object_by_frame(json_object,image_name):
    f = open(os.path.join(json_object+'.json'))
    data = json.load(f)
    data = sorted(data["video_annotations"], key=lambda k: k['image']['image_path'])
    for datapoint in data:
        if image_name == datapoint['image']['name']:
            return datapoint
    return None
        
if __name__ == '__main__':
    args = parse_args()
    print('Correcting the interpolations')
    correct_interpolations(args.input_dir,args.output_dir) #fix all possible errors in all videos
    print('Adding any missing sparse frames')
    add_mssing_sparse_annotations(args.output_dir,['P02_01', 'P03_14']) #add some missing sparse masks into these 2 videos
    print('Doing the final checks')
    correct_interpolations(args.output_dir,args.output_dir,specific_json_list = ['P02_01', 'P03_14'])#fix those videos after adding the missing frames
    