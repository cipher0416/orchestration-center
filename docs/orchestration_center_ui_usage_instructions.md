# 编排中心前端UI用户指南

## 前提条件
1. 启动注册中心服务：UI界面展示的所有Agent信息均是从注册中心获取的（具体操作见注册中心的用户指南或快速入门）
2. 启动编排中心服务： 编排中心前端UI与编排中心后台有交互，所以也需要启动（具体操作见编排中心的快速入门）
### 环境要求
- Node.js 20.19

## 启动方式
### 方式一：
进入{安装目录}/workflow-designer目录下，执行`npm install --force`命令
等待所有依赖下载完成，执行`npm run dev`

如果想查看demo，需要额外启动samples目录下的`start_agents_server.py`脚本(注册中心默认没有注册Agent，该脚本时向注册中心注册了几个Agent并启动对应的Agent)
进入到项目{安装目录}，执行命令
```bash
python -m samples.start_agents_server
```
如果是linux环境，建议给执行命令前加上 `nohup`,防止linux终端窗口长时间无操作退出后导致的服务停止，命令如下：
```bash
nohup python -m samples.start_agents_server > samples.log 2>&1 &
```
### 方式二：
进入项目目录下的`bin`文件夹
```bash
cd {安装目录}/orchestration-center/bin
``` 
执行脚本文件（该脚本文件会自动启动前端服务和samples下的脚本）：
```bash
./start_samples.sh
```
### 访问应用
上述步骤启动成功后，可以通过下面的方式进行访问。
1. 打开浏览器访问 http://localhost:3003
2. 使用工作流设计器创建和编辑流程图
3. 通过 API 接口管理 PSOP 工作流

## 界面功能介绍
进入编排中心界面后，首先点击界面右上角的齿轮状图标，修改ip为编排中心实际的安装环境ip，修改端口为编排中心实际监听的端口，保存即可。
![photo](images/photo6.jpeg)
### Agent库：

左侧展示所有Agent，可以通过Agent名称或者功能进行搜索；点击某个Agent，右侧展示该Agent详情
![photo](images/photo1.jpeg)

### 编排中心：

左侧展示目前所有的psop，上方可以通过名称进行搜索，点击左侧某个psop后，右侧会展示该psop详情。
![photo](images/photo2.jpeg)

点击左侧上方那个"+",右侧会展示编排psop的几种方式，目前有三种：
![photo](images/photo3.jpeg)

第一种：导入pdf格式文件生成对应的psop
第二种：手动编排
可以通过拖动下方的Agent卡片到画布上，然后连线，点击连线，可以设置跳转条件
![photo](images/photo4.jpeg)
第三种：输入一段自然语言，后台会根据用户的输入和目前所有的Agent自动取编排

### 工作流执行
上方输入框先输入用户意图，点击右侧的“检索工作流”按钮，如果检索到，左侧会显示该posp，中间部门会显示该psop对应的工作流，点击左侧psop右侧的“▶”按钮，页面右侧会实时显示工作流的执行过程。
![photo](images/photo5.jpeg)






