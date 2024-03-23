import re
import subprocess
import sys
import requests
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, TypedDict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class AndroidDevice(TypedDict):
    device_name: str
    ro_prop: Dict[str, Any]

class RoPropConfig(object):
    config:Dict[str, Any] = {}

    def __init__(self) -> None:
        pass

    def read(self, text: str):
        for item in text.strip().split('\n'):
            item = item.strip()
            if item.startswith(('#',)) or not item:
                continue

            item_key, item_val = item.split('=')
            self.setItem(item_key, item_val)
        
    def setItem(self, key: str, val:Any):
        config = self.config

        keys = key.split('.')
        latest_key = keys.pop()

        for key in keys:
            if key not in config:
                config[key] = {}

            config = config[key]
        
        if isinstance(config, dict):
            config[latest_key] = val

class AndroidDeviceEventHandle(FileSystemEventHandler):

    def on_moved(self, event):
        """当一个文件或者目录被重命名时"""
        print(f"{event.src_path} 被重命名为 {event.dst_path}")

    def on_created(self, event):
        """当一个文件或者目录被创建时"""
        print(f"{event.src_path}被创建了")

    def on_deleted(self, event):
        """当一个文件或者目录被删除时"""
        print(f"{event.src_path}被删除了")

    def on_modified(self, event):
        """当一个文件或者目录被修改时"""
        print(f"{event.src_path}被修改了")
    
    def on_opened(self, event):
        """当一个文件或者目录被打开时"""
        print(f"{event.src_path}被修改了")
    
    def on_closed(self, event):
        """当一个文件或者目录被关闭时"""
        print(f"{event.src_path}被修改了")
    
    def on_any_event(self, event):
        print(event)
    

class AdbUtil(object):

    lang:str = 'zh-cn'
    version: str = 'latest'
    debug_bridge_version: str = ''
    controlBin: str
    dowload_urls = {
        'windows': 'https://dl.google.com/android/repository/platform-tools-{}-windows.zip',
        'linux': 'https://dl.google.com/android/repository/platform-tools-{}-linux.zip',
        'mac':'https://dl.google.com/android/repository/platform-tools-{}-darwin.zip',
    }
    work_dir: Path
    sdk_dir: Path
    device_mapping_dir: Path

    def __init__(self) -> None:
        self.work_dir = Path(__file__).parent
        self.sdk_dir = self.work_dir.joinpath('platform-tools')
        if not self.sdk_dir.exists():
            self.download(self.version)
        self.checkVersion()
        self.device_mapping_dir = self.work_dir.joinpath('android_device')
        if not self.device_mapping_dir.exists():
            self.device_mapping_dir.mkdir()
        self.watch_observer = Observer()

    def download(self,version: str, refresh: bool = False):
        if refresh:
            self.sdk_dir.rmdir()
        
        if self.sdk_dir.exists():
            return
        
        version = version if version.startswith('latest') else f'r{self.version}'
        sdk_url = self.dowload_urls[self.systemType].format(version)
        res = requests.get(sdk_url, params={'hl': self.lang})
        if res.status_code != 200:
            print(res, res.text)
            return
        
        with zipfile.ZipFile(BytesIO(res.content)) as zipF:
            zipF.extractall(self.work_dir)
    
    def devices(self):
        devices_res = self.adb_run('devices')
        devices_res = devices_res.split('\n')
        if len(devices_res) <= 1:
            return []
        
        for device in devices_res[1:]:
            print('android设备:',device)
            res = self.adb_run('shell cat /system/build.prop')
            ro = RoPropConfig()
            ro.read(res)
            # print(res)
            # print(ro.config)
            self.walkDir('/')


    def adb_run(self, command: str):
        print('执行命令:', command)
        process = subprocess.Popen('adb {}'.format(command),shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.sdk_dir)
        output, error = process.communicate()
        if process.returncode != 0:
            raise Exception('adb command error:',error.decode('utf-8').strip())

        return output.decode('utf-8').strip()
    
    def shell_run(self, command: str):
        print('执行命令:', command)
        process = subprocess.Popen('adb shell "{}"'.format(command),shell=True,stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.sdk_dir)
        output, error = process.communicate()
        if process.returncode != 0:
            raise Exception('adb command error:',error.decode('utf-8').strip())

        return output.decode('utf-8').strip()

    def checkVersion(self):
        res = self.adb_run('version')
        res = res.split('\n')
        versionReg = re.compile(r'\d+\.\d+\.\d+')
        bridge_res = versionReg.findall(res[0])
        if bridge_res:
            self.debug_bridge_version = bridge_res[0]
        version_res = versionReg.findall(res[1])
        if version_res:
            self.version = version_res[0]
        
    @property
    def systemType(self):
        if sys.platform.startswith('linux'):
            return 'linux'
        elif sys.platform.startswith('win'):
            return 'windows'
        elif sys.platform.startswith('darwin'):
            return 'mac'
        else:
            return sys.platform

    def walkDir(self, path: str | Path):
        res = self.shell_run(f'ls -p {str(path)}')
        res = res.split('\r\n')
        for itemPath in res:
            itemPath = itemPath.strip()
            if itemPath.startswith(('.','..')) or itemPath.endswith(('.','..')):
                continue

            self.mapping(self.device_mapping_dir.joinpath(itemPath), itemPath, itemPath.endswith('/'))
    
    def mapping(self, localPath: Path, remotePath: str, isDir: bool = False):
        if not localPath.exists():
            if isDir:
                localPath.mkdir()
            else:
                with open(localPath.absolute(), 'w') as f:
                    f.write('')

    def watch(self):
        self.watch_observer.schedule(AndroidDeviceEventHandle(), self.device_mapping_dir, True)
        self.watch_observer.start()

        self.watch_observer.join()

if __name__ == '__main__':
    test = AdbUtil()
    test.watch()