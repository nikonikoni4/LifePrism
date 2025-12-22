---
trigger: model_decision
description: 编写server文件夹下的函数时启用
---

在编写server模块下的函数时，
1.在services文件夹下的脚本内的函数，不能编写参数默认值
2.所有与category color相关的内容都使用lifewatch\server\providers\category_color_provider.py内的color_manager
3.service层不能直接对数据库进行操作，只能通过provider内的server_lw_data_provider实现与数据库的操作
4.所有与类别相关操作除了专门修改名称以外的）都应该以类别id为准