# LifePrism CustomData Folder

此文件夹用于存放程序扫描的外部文件。

## 目录结构

- `external_files/` - 用户自定义文件

## 使用说明

将需要程序扫描的文件放入 `external_files/` 目录即可。

## 路径获取

在应用中可以通过以下方式获取此文件夹路径：

```javascript
// 在渲染进程中
const customDataPath = await window.electronAPI.getCustomDataPath();
```
