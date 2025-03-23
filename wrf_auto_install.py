#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Project ：wrf_auto_install 
# File    ：wrf_auto_install.py
# IDE     ：PyCharm 
# Author  ：黄浩瑜
# Date    ：2025/3/21 下午1:39
import logging
import os
import sys
import subprocess
import requests
import tarfile
import argparse
from collections import defaultdict
from conf.common import Common
import tarfile
import zipfile
import gzip
import bz2
import lzma
import os
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# dep_list = []
dep_list = Common.dep_list
# 配置文件路径
CONFIG_DIR = Common.base_dir
URL_CONFIG = os.path.join(CONFIG_DIR, 'url_config.ini')
VER_CONFIG = os.path.join(CONFIG_DIR, 'version_config.ini')
NAME_CONFIG = os.path.join(CONFIG_DIR, 'dep_name_config.ini')
logging.info(f"{URL_CONFIG}")

# 显示帮助信息
def show_help():
	logging.info(f"Usage: {sys.argv[0]} [-p INSTALL_DIR] [-v WRF_VERSION] [-c COMPILER]")
	logging.info(f"Options:")
	logging.info(f"  -p  Installation directory")
	with open(VER_CONFIG, 'r') as f:
		versions = [line.split('=')[0].strip() for line in f if line.strip()]
	logging.info(f"  -v  WRF version (supported: {' '.join(versions)})")
	logging.info(f"  -c  Compiler type [intel|gcc] (default: intel)")
	sys.exit(0)


def check_version(WRF_VERSION, compat_map):
	try:
		# 检查版本支持
		if WRF_VERSION not in compat_map.keys():
			raise KeyError(f"Error: Unsupported WRF version {WRF_VERSION}. Available versions: {', '.join(compat_map.keys())}")
	except KeyError:
		logging.error(f"错误代码100, {WRF_VERSION} is not a valid WRF version")
		sys.exit(100)
# 下载组件
def download_file_with_wget(url, dest):
	try:
		subprocess.run(["wget", url, "-O", dest], check=True)
		logging.info(f"Downloaded successfully: {dest}")
	except subprocess.CalledProcessError as e:
		logging.info(f"Error: Download failed - {url} | {e}")
		sys.exit(1)


def extract_file(src_path, dest_dir):
	"""自动检测并解压文件到指定目录"""
	# 记录原始目录内容用于后续清理
	original_files = set(os.listdir(dest_dir))

	# 尝试用不同tar格式解压
	tar_formats = ['r:gz', 'r:bz2', 'r:xz', 'r']
	for fmt in tar_formats:
		try:
			with tarfile.open(src_path, fmt) as tar:
				tar.extractall(dest_dir)
				return True
		except tarfile.TarError:
			continue

	# 尝试解压ZIP
	try:
		with zipfile.ZipFile(src_path, 'r') as zipf:
			zipf.extractall(dest_dir)
			return True
	except zipfile.BadZipFile:
		pass

	# 处理单独压缩文件
	try:
		# 获取基础文件名（不带路径）
		base_name = os.path.basename(src_path)
		# 去除所有已知压缩扩展名
		for ext in ['.gz', '.bz2', '.xz', '.zip',
					'.tar.gz', '.tgz', '.tar.bz2',
					'.tbz2', '.tar.xz', '.txz', '.tar']:
			if base_name.lower().endswith(ext):
				base_name = base_name[:-len(ext)]
				break

		output_path = os.path.join(dest_dir, base_name)

		# 尝试不同压缩格式
		openers = [
			(gzip.open, 'rb'),
			(bz2.open, 'rb'),
			(lzma.open, 'rb')
		]

		for opener, mode in openers:
			try:
				with opener(src_path, mode) as f_in:
					with open(output_path, 'wb') as f_out:
						shutil.copyfileobj(f_in, f_out)
				return True
			except Exception:
				continue

	except Exception:
		pass

	# 如果所有方法都失败，回滚并报错
	new_files = set(os.listdir(dest_dir)) - original_files
	for f in new_files:
		f_path = os.path.join(dest_dir, f)
		if os.path.isfile(f_path):
			os.remove(f_path)
		else:
			shutil.rmtree(f_path)
	raise ValueError(f"无法解压文件：不支持的文件格式 '{src_path}'")


def normalize_extracted_dir(target_dir):
	"""整理解压目录结构，避免嵌套"""
	while True:
		entries = os.listdir(target_dir)
		# 如果只有一个目录且没有其他文件
		if len(entries) == 1 and os.path.isdir(os.path.join(target_dir, entries[0])):
			nested_dir = os.path.join(target_dir, entries[0])
			# 移动嵌套目录内容到父目录
			for item in os.listdir(nested_dir):
				shutil.move(
					os.path.join(nested_dir, item),
					os.path.join(target_dir, item)
				)
			os.rmdir(nested_dir)
		else:
			break


# 安装编译器
def install_compiler(URL_COMP_MAP, intel_file_path,INTEL_PATH,name_map, compiler_type, install_dir):
	if compiler_type == "intel":
		logging.info("Installing compiler: ")
		result = subprocess.run(["bash", "-c", f"source {os.path.join(install_dir, 'compiler', 'setvars.sh')} && ifort -v && icc -v"],capture_output=True, text=True)
		os.environ["CC"] = "icc"
		os.environ["CXX"] = "icpc"
		os.environ["FC"] = "ifort"
		os.environ['F90'] = "ifort"
		os.environ['F77'] = "ifort"
		os.environ["CFLAGS"] = "-O3 -fPIC"
		os.environ["CXXFLAGS"] = "-O3 -fPIC"
		if result.returncode == 0:
			logging.info("Command executed successfully.")
		else:
			logging.info(f"{compiler_type} compiler is not found.")

			installer_base = os.path.join(intel_file_path, name_map['intel-base'])
			installer_hpc = os.path.join(intel_file_path, name_map['intel-hpc'])
			if not os.path.exists(installer_base):
				download_file_with_wget(URL_COMP_MAP['intel-base'], installer_base)
				subprocess.run(["chmod", "+x", installer_base])
			if not os.path.exists(installer_hpc):
				download_file_with_wget(URL_COMP_MAP['intel-hpc'], installer_hpc)
				subprocess.run(["chmod", "+x", installer_hpc])

			# subprocess.run(
				# ["bash", "-c", f"{installer_base} -a --install-dir {INTEL_PATH} --silent --components intel.oneapi.lin.dpcpp-cpp-compiler --eula accept"])
			# subprocess.run(["bash", "-c", f"source {os.path.join(install_dir, 'compiler', 'setvars.sh')}"])
			subprocess.run(
				["bash", "-c", f"{installer_hpc} -a --install-dir {INTEL_PATH} --silent --components intel.oneapi.lin.mpi.devel:intel.oneapi.lin.ifort-compiler:intel.oneapi.lin.dpcpp-cpp-compiler-pro --eula accept"])
			subprocess.run(["bash", "-c", f"source {os.path.join(install_dir, 'compiler', 'setvars.sh')}"])
			os.environ["CC"] = "icc"
			os.environ["CXX"] = "icpc"
			os.environ["FC"] = "ifort"
			os.environ['F90'] = "ifort"
			os.environ['F77'] = "ifort"
			os.environ["CFLAGS"] = "-O3 -fPIC"
			os.environ["CXXFLAGS"] = "-O3 -fPIC"
	# elif compiler_type == "gcc":
	# 	subprocess.run(["sudo", "apt-get", "install", "-y", "gcc", "g++", "gfortran"])
	# 	os.environ["CC"] = "gcc"
	# 	os.environ["CXX"] = "g++"
	# 	os.environ["FC"] = "gfortran"
def log_command_result(result):
	if result.returncode != 0:
		logging.info("Error occurred during execution:")
		logging.info("STDOUT: %s", result.stdout)
		logging.info("STDERR: %s", result.stderr)
	else:
		logging.info("Command executed successfully.")
		logging.info("STDOUT: %s", result.stdout)

# 安装依赖
def install_dependencies(URL_DEP_MAP, mpinum, DEP_DIR, INTEL_PATH,compat_map, install_dir):

	target_path = os.path.join(INTEL_PATH, "mpi/latest")
	if not os.path.exists(target_path):
		logging.info(f"Error: Path {target_path} does not exist.")
	elif not os.path.exists(os.path.join(DEP_DIR, 'mpi')):
		logging.info(f"Target path {target_path} exists, creating symbolic link...")
		subprocess.run(
			["bash", "-c",
			 f"source {CONFIG_DIR}/set_env.sh && ln -sf {target_path} {DEP_DIR}/mpi"]
		)
	else:
		logging.info(f"Target path {target_path} is already exists, continue")
	for dep in dep_list:
		logging.info(f"Download: {dep}.")
		if dep in compat_map.keys():
			version = compat_map[dep]
		url_pattern = URL_DEP_MAP.get(f"{dep}")
		if url_pattern:
			url = url_pattern.replace("%v", version)
			src_file = os.path.join(install_dir, "src", f"{dep}-{version}.tar.gz")
			install_dir_dep = os.path.join(install_dir, "deps")

			if os.path.isdir(os.path.join(install_dir_dep,dep)):
				logging.info(f"Dependency {dep}-{version} already installed.")
				continue

			if not os.path.exists(src_file):
				download_file_with_wget(url, src_file)

			logging.info(f"Compiling {dep}-{version}...")
			src_dir = os.path.join(install_dir, "src")
			# 计算目标目录名称
			src_file_basename = os.path.basename(src_file)
			package_base = src_file_basename
			# 去除所有常见压缩扩展名
			for ext in ['.tar.gz', '.tgz', '.tar.bz2', '.tbz2',
						'.tar.xz', '.txz', '.zip', '.gz',
						'.bz2', '.xz', '.tar']:
				if package_base.lower().endswith(ext):
					package_base = package_base[:-len(ext)]
					break

			target_dir = os.path.join(src_dir, package_base)
			os.makedirs(target_dir, exist_ok=True)

			try:
				extract_file(src_file, target_dir)
				# 整理目录结构
				normalize_extracted_dir(target_dir)
			except Exception as e:
				shutil.rmtree(target_dir, ignore_errors=True)
				raise
			logging.info(f'Enter dir to {target_dir}')
			os.chdir(target_dir)
			if 'netcdf' in dep:
				result = subprocess.run(
					["bash", "-c",
					 f"source {CONFIG_DIR}/set_env.sh && chmod +x configure && ./configure --prefix={install_dir_dep} CPPFLAGS=-I{install_dir_dep}/include LDFLAGS=-L{install_dir_dep}/lib --disable-dap && make -j{mpinum} && make check || true && make install"],
					capture_output=True,  # 捕获标准输出和标准错误
					text=True  # 使输出为字符串而非字节
				)
			elif 'hdf5' in dep:
				result = subprocess.run(
					["bash", "-c",
					 f"source {CONFIG_DIR}/set_env.sh && chmod +x configure && ./configure --prefix={install_dir_dep} --enable-fortran && make -j{mpinum} && make check && make install"],
					capture_output=True,  # 捕获标准输出和标准错误
					text=True  # 使输出为字符串而非字节
				)
			else:
				result = subprocess.run(
					["bash", "-c",
					 f"source {CONFIG_DIR}/set_env.sh && chmod +x configure && ./configure --prefix={install_dir_dep} && make -j{mpinum} && make check && make install"],
					capture_output=True,  # 捕获标准输出和标准错误
					text=True  # 使输出为字符串而非字节
				)
			if result.returncode != 0:
				logging.info("Error occurred during execution:")
				logging.info("STDOUT:", result.stdout)
				logging.info("STDERR:", result.stderr)
			else:
				logging.info("Command executed successfully.")
				# logging.info("STDOUT:", result.stdout)
# 编译WRF
def compile_wrf(install_dir, wrf_version, compiler_type, URL_WRF_MAP):
	wrf_src = os.path.join(install_dir, "src", f"WRF-{wrf_version}")
	wrf_tar = os.path.join(install_dir, "src", "WRF.tar.gz")
	if not os.path.isdir(wrf_src):
		wrf_url = URL_WRF_MAP['wrf']
		download_file_with_wget(wrf_url, os.path.join(install_dir, "src", "WRF.tar.gz"))
		# 目标目录名称

		os.makedirs(wrf_src, exist_ok=True)
		try:
			extract_file(wrf_tar, wrf_src)
			# 整理目录结构
			normalize_extracted_dir(wrf_src)
		except Exception as e:
			shutil.rmtree(wrf_src, ignore_errors=True)
			raise
	###编译wrf
	os.chdir(wrf_src)
	try:
		subprocess.run(["clean", "-a"])
	except:
		wrf_set_sh = os.path.join(CONFIG_DIR, 'src', 'wrf_version_set', f'wrf_{wrf_version}.sh')
		subprocess.run(["bash", "-c",f"source {CONFIG_DIR}/set_env.sh && chmod +x {wrf_set_sh} && bash {wrf_set_sh}"])
		logging.info("Select compilation options:")
		if compiler_type == "intel":
			subprocess.run(
				["bash", "-c",
				 f"source {CONFIG_DIR}/set_env.sh && chmod +x configure && ./configure"],input="15 1\n",
				capture_output=True,  # 捕获标准输出和标准错误
				text=True  # 使输出为字符串而非字节
			)

		# elif compiler_type == "gcc":
		# 	subprocess.run(["./configure"], input="34 1\n", text=True)

	subprocess.run(["bash", "-c",
				 f"source {CONFIG_DIR}/set_env.sh && ./compile em_real >& wrfcom.log"])
	required_files = ["wrf.exe", "real.exe", "tc.exe", "ndown.exe"]
	missing_files = [file for file in required_files if not os.path.exists(os.path.join(wrf_src, "main", file))]

	if missing_files:
		logging.info("Error: WRF compilation failed.")
		sys.exit(1)


def compile_wps(install_dir, wps_version, compiler_type, URL_WRF_MAP):
	wps_src = os.path.join(install_dir, "src", f"WPS-{wps_version}")
	wps_tar = os.path.join(install_dir, "src", "WPS.tar.gz")
	if not os.path.isdir(wps_src):
		wrf_url = URL_WRF_MAP['wps']
		download_file_with_wget(wrf_url, os.path.join(install_dir, "src", "WPS.tar.gz"))
		# 目标目录名称

		os.makedirs(wps_src, exist_ok=True)
		try:
			extract_file(wps_tar, wps_src)
			# 整理目录结构
			normalize_extracted_dir(wps_src)
		except Exception as e:
			shutil.rmtree(wps_src, ignore_errors=True)
			raise
	###编译wrf
	os.chdir(wps_src)
	try:
		subprocess.run(["clean", "-a"])
	except:
		logging.info("Select compilation options:")
		if compiler_type == "intel":
			subprocess.run(
				["bash", "-c",
				 f"source {CONFIG_DIR}/set_env.sh && chmod +x configure && ./configure"], input="19 \n",
				capture_output=True,  # 捕获标准输出和标准错误
				text=True  # 使输出为字符串而非字节
			)
			wps_set_sh = os.path.join(CONFIG_DIR, 'src', 'wps_version_set', f'wps_{wps_version}.sh')
			subprocess.run(["bash", "-c",f"source {CONFIG_DIR}/set_env.sh && chmod +x {wps_set_sh} && bash {wps_set_sh}"])
	subprocess.run(["bash", "-c",
	                f"source {CONFIG_DIR}/set_env.sh && ./compile  >& wpscom.log"])
	required_files = ["geogrid.exe", "ungrib.exe", "metgrid.exe"]
	missing_files = [file for file in required_files if not os.path.exists(os.path.join(wps_src, "main", file))]
	if missing_files:
		logging.info("Error: WPS compilation failed.")
		sys.exit(1)
# 生成环境文件
# def generate_env(WRF_VERSION, install_dir, compiler_type):
# 	env_file = os.path.join(install_dir, "env_set.sh")
# 	with open(env_file, 'w') as f:
# 		f.write(f'export WRF_BASE="{install_dir}"\n')
# 		f.write(f'export PATH="${{WRF_BASE}}/deps/netcdf/bin:$PATH"\n')
# 		f.write(f'export NETCDF="${{WRF_BASE}}/deps/netcdf"\n')
# 		f.write(f'export JASPERLIB="${{WRF_BASE}}/deps/jasper/lib"\n')
# 		f.write(f'export JASPERINC="${{WRF_BASE}}/deps/jasper/include"\n')
# 		f.write(f'export WRF_DIR="${{WRF_BASE}}/WRF-{WRF_VERSION}"\n')
# 		f.write(f'export WPS_DIR="${{WRF_BASE}}/WPS-{WRF_VERSION}"\n')
#
# 		if compiler_type == "intel":
# 			f.write(f'source "${{WRF_BASE}}/compiler/setvars.sh"\n')
# 			f.write(f'export CC=icc CXX=icpc FC=ifort\n')


def parse_config_file(ver_config, wrf_version):
	"""
	解析配置文件并根据 WRF_VERSION 替换 NAME 中的占位符。

	参数:
	- ver_config: 配置文件路径
	- wrf_version: 当前使用的 WRF 版本号

	返回:
	- dict: 包含 compatibility 配置和替换后的 name 配置
	"""
	compat_map = {}
	name_map = {}

	try:
		with open(ver_config, 'r') as f:
			section = None

			for line in f:
				line = line.strip()

				if line.startswith("[compatibility]"):
					section = "compatibility"
				elif line.startswith("[NAME]"):
					section = "name"

				if section == "compatibility" and "=" in line:
					parse_compatibility_line(line, compat_map)
					check_version(wrf_version, compat_map)
				if section == "name" and "=" in line:
					parse_name_line(line, compat_map, wrf_version, name_map)

	except FileNotFoundError:
		logging.info(f"Error: The file '{ver_config}' was not found.")
	except Exception as e:
		logging.info(f"Error: An unexpected error occurred - {e}")

	return compat_map, name_map

def parse_url_config(ver_config, wrf_version, wps_version, compat_map):
	"""
	解析 URL 配置文件，并根据 WRF_VERSION 替换 URL 中的占位符。

	参数:
	- ver_config: 配置文件路径
	- wrf_version: 当前使用的 WRF 版本号
	- compat_map: 存储版本和依赖关系的字典

	返回:
	- tuple: 包含 URL_COMP_MAP 和 URL_DEP_MAP 的字典
	"""
	URL_DEP_MAP = {}
	URL_COMP_MAP = {}
	URL_WRF_MAP = {}
	try:
		with open(ver_config, 'r') as f:
			for line in f:
				if "=" in line and not line.startswith("#"):
					key, value = line.split("=")
					key = key.strip()
					value = value.strip()
					if 'wrf' in key:
						URL_WRF_MAP[key] = replace_version_placeholder(value, wrf_version)
					if 'wps' in key:
						URL_WRF_MAP[key] = replace_version_placeholder(value, wps_version)
					# 根据 'intel' 来决定是更新 URL_COMP_MAP 还是 URL_DEP_MAP
					version_number = compat_map.get(wrf_version, {}).get(key, None)
					if version_number:
						if 'intel' in key:
							URL_COMP_MAP[key] = replace_version_placeholder(value, version_number)
						else:
							URL_DEP_MAP[key] = replace_version_placeholder(value, version_number)
					else:
						logging.info(f"Error: Key '{key}' not found in compatibility map for version {wrf_version}.")


	except FileNotFoundError:
		logging.info(f"Error: The file '{ver_config}' was not found.")
	except Exception as e:
		logging.info(f"Error: An unexpected error occurred - {e}")

	return URL_COMP_MAP, URL_DEP_MAP, URL_WRF_MAP
def parse_compatibility_line(line, compat_map):
	"""
	解析 compatibility 部分的每一行并更新 compat_map。

	参数:
	- line: 当前解析的 line
	- compat_map: 存储版本和依赖关系的字典
	"""
	version, deps = line.split("=")
	deps = deps.split()
	version_dep = {}
	for dep in deps:
		name, number = dep.split(":")
		version_dep[name] = number
	compat_map[version.strip()] = version_dep


def parse_name_line(line, compat_map, wrf_version, name_map):
	"""
	解析 name 部分的每一行并替换占位符 %v。

	参数:
	- line: 当前解析的 line
	- compat_map: 存储版本和依赖关系的字典
	- wrf_version: 当前使用的 WRF 版本号
	- name_map: 存储替换后的 name 配置的字典
	"""
	name_key, name_values = line.split("=")
	name_values = name_values.split()

	for name_value in name_values:
		name, number = name_value.split(":")
		if name in compat_map.get(wrf_version, {}):
			name_map[name] = replace_version_placeholder(number, compat_map[wrf_version][name])
		else:
			logging.info(f"Error: name '{name}' not found in compatibility map for version {wrf_version}.")


def replace_version_placeholder(value, version_number):
	"""
	替换字符串中的占位符 %v 为实际版本号。

	参数:
	- value: 包含占位符的字符串
	- version_number: 要替换的版本号

	返回:
	- str: 替换后的字符串
	"""
	return value.replace('%v', version_number)
# 主函数
def main():
	try:
		parser = argparse.ArgumentParser(description="Install WRF with given options.")
		parser.add_argument("-p", "--install_dir",  help="Installation directory, must be absolute path")
		parser.add_argument("-wrf", "--wrf_version", default='3.9', help="WRF version")
		parser.add_argument("-wps", "--wps_version", default='3.9', help="WPS version")
		parser.add_argument("-c", "--compiler", default='intel', choices=["intel"], help="Compiler type, only use intel")
		parser.add_argument("-n", "--mpinum", default=4, help="")
		# parser.add_argument("-h", "--help", action="help", help="Show this help message and exit")

		args = parser.parse_args()
		WRF_VERSION = args.wrf_version
		WPS_VERSION = args.wps_version
		INSTALL_DIR = args.install_dir
		COMPILER_TYPE = args.compiler
		MPINUM = args.mpinum
		logging.info(f"Installing WRF version: {WRF_VERSION}\n Compiler type: {COMPILER_TYPE}\n Installation directory: {INSTALL_DIR}")
		# WRF_VERSION = '3.9'
		# WPS_VERSION = '3.9'
		# INSTALL_DIR = '/root/WRF/wrf_install'
		# COMPILER_TYPE = 'intel'
		# MPINUM = 4
		intel_file_path = Common.intel_file_path
		INTEL_PATH = os.path.join(INSTALL_DIR, 'compiler')
		DEP_DIR = os.path.join(INSTALL_DIR, 'deps')
		os.environ['INTEL_PATH'] = INTEL_PATH
		os.environ['DEP_DIR'] = DEP_DIR
		os.environ['INSTALL_PATH'] = INSTALL_DIR
		os.environ['WRF_V'] = f"WRF-{WRF_VERSION}"
		os.environ['WPS_V'] = f"WPS-{WPS_VERSION}"
		# 读取版本配置
		compat_map, name_map = parse_config_file(VER_CONFIG, WRF_VERSION)
		URL_COMP_MAP, URL_DEP_MAP ,URL_WRF_MAP = parse_url_config(URL_CONFIG, WRF_VERSION,WPS_VERSION, compat_map)

		# 初始化目录结构
		os.makedirs(os.path.join(INSTALL_DIR, "src"), exist_ok=True)
		os.makedirs(os.path.join(INSTALL_DIR, "compiler"), exist_ok=True)
		os.makedirs(os.path.join(INSTALL_DIR, "deps"), exist_ok=True)
		os.makedirs(os.path.join(INSTALL_DIR, "logs"), exist_ok=True)

		# 安装过程
		logging.info(f"Start installing WRF v{WRF_VERSION} ({COMPILER_TYPE} compiler)")
		logging.info(f"Installation directory: {INSTALL_DIR}")
		logging.info(f"The following dependencies will be installed: {compat_map[WRF_VERSION]}")
		logging.info(f"Start install compiler.")
		install_compiler(URL_COMP_MAP, intel_file_path, INTEL_PATH,name_map, COMPILER_TYPE, INSTALL_DIR)
		logging.info(f"Start install dependencies.")
		install_dependencies(URL_DEP_MAP, MPINUM, DEP_DIR, INTEL_PATH,compat_map[WRF_VERSION], INSTALL_DIR)
		logging.info(f"Start install WRF v{WRF_VERSION} ({COMPILER_TYPE} compiler).")
		compile_wrf(INSTALL_DIR, WRF_VERSION, COMPILER_TYPE, URL_WRF_MAP)
		logging.info(f"Start install WPS v{WPS_VERSION} ({COMPILER_TYPE} compiler).")
		compile_wps(INSTALL_DIR, WPS_VERSION, COMPILER_TYPE, URL_WRF_MAP)

		# generate_env(WRF_VERSION,INSTALL_DIR, COMPILER_TYPE)

		logging.info(f"\nInstallation completed successfully! Activate environment with:")
		logging.info(f"source {os.path.join(INSTALL_DIR, 'env_set.sh')}")
	except Exception as e:
		logging.info(f"Error: An unexpected error occurred - {e}")
		raise e

if __name__ == "__main__":
	main()
