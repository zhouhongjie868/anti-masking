# Anti Masking

该应用有一个页面，用户输入名字A与名字B的映射关系，应用修改OceanBase数据库(mysql模式)中的特定表C，将名字字段中名字A替换为名字B。要求架构尽量简单，部署与维护方便

## 依赖

- 使用本机python3 ，要求兼容3.10语法
- 使用 uv 作为包管理工具，创建对应虚拟环境

依赖包：streamlit mysql-connector-python，可以追加

### 安装依赖

```shell
# 激活虚拟环境
source .venv/bin/activate
# 安装/更新依赖
uv pip install -r requirements.txt
```

## 部署

docker 

## 要求

- README.md 等 markdown 文档使用中文
- html的页面元素使用中文
- 代码注释使用英文
- 执行python命令前，先检查是否切换到虚拟环境

## Roadmap

### 支持批量替换

新增批量导入功能，增加一个下载模块的按钮，点击下载按钮后下载一个 Excel 模板，Excel 有两列，分别是原客户名和替换后客户名。另有一个文件上传按钮，只能上传excel格式文件，文件上传后解析Excel，将需要替换的名字对列出来，给用户确认。用户确认后，批量替换表中对应字段的客户名。


### 记录替换日志