日期：2026-1-31 19：29
任务：依据前端页面重构前后端的goal相关内容
**要求**：

1. 涉及到goal category todo，plandocs等内容都是用id为唯一标识，这是因为名称很容易被修改，不容易维护
2. 若goalsV2与前端冲突，以后端为准，修改新前端，减少后端代码修改量，后端多余字段可以删除，前端新增字段后端需要补充。这个是因为除了service可能还有其他地方使用，若直接修改很容易出现bug

**后端的架构**：当前重构依旧是依据后端的架构，

	1. 在lifeprism\config\database.py完成数据表的配置 
	1. 在lifeprism\server\providers创建数据提供类，继承LWBaseDataProvider实现，使用LWBaseDataProvider中的db类成员实现数据库操作  
	1. 在schemas中编写前后端数据沟通的schemas 
	1. 在service创建单一service实例，采用懒加载方式lifeprism\utils\lazy_singleton.py。

## 拟进行修改的计划

### 数据层
#### 数据表

#### API schemas

### service层

#### provider设计

#### service单例设计

#### API url