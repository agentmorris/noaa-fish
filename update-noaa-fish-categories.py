#
# update-noaa-fish-categories.py
#
# The original LILA dataset used a single "animal" category; metadata added
# later differentiated between fish/crab/fish-or-crab/unknown.  This script
# takes that new metadata and writes an updated dataset .json file.
#

#%% Imports and constants

import os

input_coco_file = os.path.expanduser('~/data/noaa-fish/noaa_estuary_fish.json')
new_annotations_file = os.path.expanduser('~/data/noaa-fish/updated_noaa_estuary_fish.json')
output_file = os.path.expanduser('~/data/noaa-fish/noaa_estuary_fish-2023.08.19.json')
image_folder = os.path.expanduser('~/data/noaa-fish/JPEGImages')
preview_folder = os.path.expanduser('~/tmp/noaa-fish-preview')

assert os.path.isfile(input_coco_file)
assert os.path.isfile(new_annotations_file)
assert os.path.isdir(image_folder)


#%% Read input data

import json

with open(input_coco_file,'r') as f:
    d = json.load(f)
    
with open(new_annotations_file,'r') as f:
    new_annotations = json.load(f)

print('Read original metadata for {} images, new metadata for {} images'.format(
    len(d['images']),len(new_annotations['images'])))


#%% Verify that both .json files refer to the same image files

assert len(d['images']) == len(new_annotations['images'])
                     
original_images = set([im['file_name'] for im in d['images']])
for im in new_annotations['images']:
    assert im['file_name'] in original_images


#%% Map IDs to images and annotations
    
from collections import defaultdict

original_id_to_image = {im['id']:im for im in d['images']}
original_id_to_annotations = defaultdict(list)

# ann = d['annotations'][0]
for ann in d['annotations']:
    assert len(ann.keys()) in (4,5)
    if 'bbox' in ann:        
        # Only the "animal" category should have a bounding box
        assert ann['category_id'] == 1
    original_id_to_annotations[ann['image_id']].append(ann)
    
# Every image should be annotated (possibly as empty)
assert len(original_id_to_image) == len(original_id_to_annotations)


#%% Do some cleanup of the original annotations

# Specifically, remove redundant empty annotations

image_ids_with_redundant_empty_annotations = []
redundant_annotation_ids_to_delete = []

for image_id in original_id_to_annotations.keys():
    
    annotations_this_image = original_id_to_annotations[image_id]
    category_ids_this_image = set()
    
    for ann in annotations_this_image:
        category_ids_this_image.add(ann['category_id'])
        
    # Each image should be either empty or non-empty
    assert len(category_ids_this_image) == 1
    
    # There were a few cases where images were annotated as empty with more than
    # one annotation (this is redundant)
    if 0 in category_ids_this_image:
        if len(annotations_this_image) > 1:
            image_ids_with_redundant_empty_annotations.append(image_id)
            
            assert len(annotations_this_image) == 2            
            redundant_annotation_ids_to_delete.append(annotations_this_image[1]['id'])

print('Removing {} redundant annotations from {} images'.format(
    len(redundant_annotation_ids_to_delete),
    len(image_ids_with_redundant_empty_annotations)))

redundant_annotation_ids_to_delete = set(redundant_annotation_ids_to_delete)

annotations_to_keep = []
for ann in d['annotations']:
    if ann['id'] not in redundant_annotation_ids_to_delete:
        annotations_to_keep.append(ann)
    
print('Keeping {} of {} annotations'.format(len(annotations_to_keep),
                                            len(d['annotations'])))

d['annotations'] = annotations_to_keep


#%% Re-build the annotation map

original_id_to_annotations = defaultdict(list)

for ann in d['annotations']:
    original_id_to_annotations[ann['image_id']].append(ann)
    
# Every image should be annotated (possibly as empty)
assert len(original_id_to_image) == len(original_id_to_annotations)


#%% Merge the new annotations in

habitat_types = set()
visibility_types = set()
animal_types = set()

new_category_name_to_id = \
{
    'empty':0,
    'fish':1,
    'crab':2,
    'fish_or_crab':3,
    'unknown':4
}

habitat_types = set(['clam','eelgrass','other','oyster_off_bottom','oyster_on_bottom','sediment'])
visibility_levels = set(['low','medium','high'])

# new_im = new_annotations['images'][0]
for new_im in new_annotations['images']:
    
    original_im = original_id_to_image[new_im['id']]
    assert new_im['file_name'] == original_im['file_name']
    
    assert isinstance(new_im['filter'],bool)
    original_im['filter'] = new_im['filter']
    
    assert isinstance(new_im['standardized_habitat_type'],str)
    original_im['habitat_type'] = new_im['standardized_habitat_type'].lower().replace(' ','_')
    assert original_im['habitat_type'] in habitat_types
    
    assert isinstance(new_im['visibility'],str)
    original_im['visibility'] = new_im['visibility'].lower()
    assert original_im['visibility'] in visibility_levels

    animal_type = None
    if 'animal_type' in new_im:
        animal_type = new_im['animal_type']
        if animal_type == 'both':
            animal_type = 'fish_or_crab'
        assert animal_type in new_category_name_to_id.keys()
        
    annotations_this_image = original_id_to_annotations[original_im['id']]
    
    # If there is no "animal_type" field for this image, make sure it's annotated as empty
    if 'animal_type' not in new_im:
        assert len(new_im.keys()) == 8
        assert len(annotations_this_image) == 1 and annotations_this_image[0]['category_id'] == 0
    else:        
        assert len(new_im.keys()) == 9
        # If there is an "animal_type" field for this image, make sure it's annotated as an animal
        for ann in annotations_this_image:
            assert ann['category_id'] == 1
            ann['category_id'] = new_category_name_to_id[animal_type]
            
# ...for each image


#%% Update category and info

new_categories = []
for category_name in new_category_name_to_id:
    new_categories.append({'name':category_name,
                           'id':new_category_name_to_id[category_name]})

d['categories'] = new_categories
d['info']['version'] = '202.08.19.00'


#%% Write the new .json file

with open(output_file,'w') as f:
    json.dump(d,f,indent=1)
    

#%% Validate .json file

from data_management.databases import integrity_check_json_db

options = integrity_check_json_db.IntegrityCheckOptions()
options.baseDir = image_folder
options.bCheckImageSizes = False
options.bCheckImageExistence = True
options.bFindUnusedImages = True

sorted_categories, data, error_info = integrity_check_json_db.integrity_check_json_db(output_file, options)


#%% Preview labels

from md_visualization import visualize_db

viz_options = visualize_db.DbVizOptions()
viz_options.num_to_visualize = 2000
viz_options.trim_to_images_with_bboxes = False
viz_options.add_search_links = False
viz_options.sort_by_filename = False
viz_options.parallelize_rendering = True
viz_options.include_filename_links = False
viz_options.include_image_links = True
viz_options.viz_size = (1100, -1)
html_output_file, image_db = visualize_db.process_images(db_path=output_file,
                                                         output_dir=preview_folder,
                                                         image_base_dir=image_folder,
                                                         options=viz_options)

from md_utils import path_utils
path_utils.open_file(html_output_file)


#%% Zip output file

from md_utils.path_utils import zip_file

zip_file(output_file, verbose=True)
assert os.path.isfile(output_file + '.zip')


#%% Scrap

if False:
    
    pass

    #%%
    
    target_id = 'SD42_370_8_15_2018_5_73.29.jpg'
    
    with open(new_annotations_file,'r') as f:
        new_annotations = json.load(f)

    # im = new_annotations['images'][0]
    target_im = None
    for im in new_annotations['images']:
        if target_id in im['id']:
            target_im = im
            break
    assert target_im is not None
    
    
    #%%
    