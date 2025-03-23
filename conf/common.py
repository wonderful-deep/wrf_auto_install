#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Project ：wrf_auto_install 
# File    ：common.py
# IDE     ：PyCharm 
# Author  ：黄浩瑜
# Date    ：2025/3/21 下午1:40
import os


class Common(object):
	base_dir =os.path.dirname(os.path.abspath(__name__))
	intel_file_path = os.path.join(base_dir, 'src','intel')
	dep_list = ['zlib', 'libpng', 'jasper', 'netcdf-c', 'netcdf-fortran']
	# dep_list = []