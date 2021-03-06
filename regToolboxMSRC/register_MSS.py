#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: nhp
"""

import os
import time
import datetime
from regToolboxMSRC.utils.reg_utils import register_elx_n, transform_mc_image_sitk, check_im_size_fiji, reg_image_preprocess, parameter_load
import SimpleITK as sitk


def register_MSS(source_fp,
                 source_res,
                 target_fp,
                 target_res,
                 source_mask_fp,
                 target_mask_fp,
                 wd,
                 source_img_type,
                 target_img_type,
                 reg_model,
                 project_name,
                 intermediate_output=False,
                 bounding_box_source=True,
                 bounding_box_target=True,
                 pass_in_project_name=False,
                 pass_in=None):
    """This function performs linear then non-linear registration between 2
    images from serial tissue sections.

    Parameters
    ----------
    source_fp : str
        String file path to source image
    source_res : float
        Image resolution of source image, specified in microns / pixel
    target_fp : str
        String file path to first target image
    target_res : float
        Image resolution of first target image image, specified in microns / pixel
    source_mask_fp : str or SimpleITK.Image()
        String file path to binary mask for source image or SimpleITK.Image()
        Using a mask image from memory is helpful in some registration routines
        where there are multiple registrations and the mask must be transformed
        to continue.
    target_mask_fp : str or SimpleITK.Image()
        String file path to binary mask for target image or SimpleITK.Image()
    wd : str
        String directory path to where outputs will go
    source_img_type : str
        string of either 'RGB_l' or 'AF' for source image
        'RGB_l' specifices an RGB image with a light background,
        like brightfield microscopy.
        'AF' specifices a multilayer fluorescence image or RGB image with
        a dark background.
    target_img_type : str
        string of either 'RGB_l' or 'AF' for first target image
    reg_model1 : str or file path to Sitk.ParameterMap()
        The elastix parameter file for the initial registration between source
        image and target image
    project_name : str
        String prepended to file outputs
    return_image : boolean
        Whether or not to return the from IMS_registrations.
        This is required when there is an initial rigid transformation followed
        by a non-linear transformation on the previously aligned image.
        It is defaulted internally to the appropriate setting.
    intermediate_output : boolean
        Whether or not to write the intermediate initial registration image
        or only the final non-linears.
    bounding_box : boolean
        Whether to use the mask as a bounding_box to crop the area of interest
        This has been useful when registering a small image to a very large one
        where the registration initializes poor.
        This setting will find the transformation on the crop, then paste the
        registered image back to the original dimensions of the target image.
    pass_in_project_name : boolean
        This parameter is used to pass in the project name from the reg_tlbx_gui
    pass_in : str
        Time stamped name fragment inherited from the GUI

    Returns
    -------
        The function writes the transformation files and images in the specified
        working directory.
    """
    #set up output information
    if pass_in_project_name == False:
        ts = datetime.datetime.fromtimestamp(
            time.time()).strftime('%Y%m%d_%H_%M_%S_')
        os.chdir(wd)
        os.makedirs(os.path.join(os.getcwd(), ts + project_name + "_images"))
        opdir = ts + project_name + "_images"
        pass_in = ts + project_name

    else:
        os.chdir(wd)
        os.makedirs(os.path.join(os.getcwd(), pass_in + "_images"))
        opdir = pass_in + "_images"

    #load registration parameters based on input
    reg_param1 = parameter_load(reg_model)
    print('Running MSS Registration...')
    print(project_name + ': registration hyperparameters loaded')

    #load images for registration:
    source = reg_image_preprocess(
        source_fp,
        source_res,
        img_type=source_img_type,
        mask_fp=source_mask_fp,
        bounding_box=bounding_box_source)

    print(project_name + ": source image loaded")

    target = reg_image_preprocess(
        target_fp,
        target_res,
        img_type=target_img_type,
        mask_fp=target_mask_fp,
        bounding_box=bounding_box_target)

    print(project_name + ": target 1 image loaded")

    #registration initial
    src_tgt_tform_init, init_img = register_elx_n(
        source,
        target,
        reg_param1,
        output_dir=pass_in + "_tforms_src_tgt_init",
        output_fn=pass_in + "_init_src_tgt_init.txt",
        return_image=True,
        intermediate_transform=True)

    #transform intermediate result and save output
    os.chdir(wd)

    if intermediate_output == True:
        tformed_im = transform_mc_image_sitk(
            source_fp, src_tgt_tform_init, source_res, override_tform=False)

        sitk.WriteImage(tformed_im,
                        os.path.join(os.getcwd(), opdir,
                                     project_name + "_src_tgt_init.tif"), True)

    #load non-linear registration parameter
    reg_param_nl = parameter_load('nl')

    ##register using nl transformation
    # #add masking continuation(TODO)
    # if source_mask_fp != None:
    #     source_mask_fp = transform_mc_image_sitk(
    #         source_mask_fp,
    #         src_tgt_tform_init,
    #         source_res,
    #         from_file=True,
    #         is_binary_mask=True,
    #         override_tform=False)

    source = reg_image_preprocess(
        init_img,
        target_res,
        img_type='in_memory',
        mask_fp=source_mask_fp,
        bounding_box=False)

    src_tgt_tform_nl = register_elx_n(
        source,
        target,
        reg_param_nl,
        output_dir=pass_in + "_tforms_src_tgt_nl",
        output_fn=pass_in + "init_src_tgt_nl.txt",
        return_image=False,
        logging=True,
        intermediate_transform=False)

    ##source to tgt2
    tformed_im = transform_mc_image_sitk(
        source_fp, src_tgt_tform_init, source_res, override_tform=False)

    tformed_im = transform_mc_image_sitk(
        tformed_im,
        src_tgt_tform_nl,
        source_res,
        from_file=False,
        override_tform=False)

    if check_im_size_fiji(tformed_im) == True:
        sitk.WriteImage(tformed_im,
                        os.path.join(os.getcwd(), opdir,
                                     project_name + "_src_tgt_nl.mha"), True)
    else:
        sitk.WriteImage(tformed_im,
                        os.path.join(os.getcwd(), opdir,
                                     project_name + "_src_tgt_nl.tif"), True)

    return


if __name__ == '__main__':
    import yaml
    import sys
    with open(sys.argv[1]) as f:
        # use safe_load instead load
        dataMap = yaml.safe_load(f)

    register_MSS(
        dataMap['source_fp'],
        dataMap['source_res'],  #source image
        dataMap['target_fp'],
        dataMap['target_res'],  #target image
        dataMap['source_mask_fp'],
        dataMap['target_mask_fp'],  #masks
        dataMap['wd'],  #output directory
        dataMap['source_img_type'],
        dataMap['target_img_type'],  #image type info 'RGB_l' or 'AF'
        dataMap['reg_model'],  #initial transformation model
        dataMap['project_name'],
        intermediate_output=dataMap['intermediate_output'],
        bounding_box_source=dataMap['bounding_box_source'],
        bounding_box_target=dataMap['bounding_box_target'])
