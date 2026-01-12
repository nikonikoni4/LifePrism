# developing...

正在开发中....
下面是暂时的使用方法

## 快速开始

1. [下载activitywatch（电脑端数据来源）](https://github.com/ActivityWatch/activitywatch.git)

2. clone 仓库

    ```bash
    git clone --recursive https://github.com/nikonikoni4/LifePrism.git
    ```

3. 配置环境

    ```bash
    cd LifePrism
    pip install -e .
    ```

    ```bash
    cd frontend
    npm install
    npm run dev
    ```

    ```bash
    cd lifeprism/server
    python main.py
    ```

5. 访问 http://localhost:3000/ 

6. 点击setting 查看当前地址是否存在着activitywacth的数据库
    - activitywacth地址："C:\Users\yourname\AppData\Local\activitywatch\activitywatch\aw-server\peewee-sqlite.v2.db"

7. 配置API
    - 目前只支持阿里云的API：https://cn.aliyun.com/

8. 配置分类
    - 点击category 添加新的分类

## Tokens 用量说明

LifePrism对于tokens的消耗特别小，下面是我使用了一个多月的情况，这里还包括我调试时产生的tokens消耗：
总共消耗：689.4k 按照阿里云qwen-plus的单价计算，约合0.6元

![alt text](/assets/image.png)