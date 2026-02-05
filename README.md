# Anti Masking Application

## 环境搭建

本项目使用 Python 3.11 及 `uv` 作为包管理工具。

1.  **安装 `uv`:**
    如果您的系统尚未安装 `uv`，可以通过 pip 进行安装：
    ```bash
    pip install uv
    ```

2.  **创建并激活虚拟环境:**
    在项目根目录下，执行以下命令创建并激活名为 `.venv` 的虚拟环境：
    ```bash
    python3 -m uv venv .venv
    source .venv/bin/activate
    ```

3.  **安装依赖:**
    激活虚拟环境后，安装 `requirements.txt` 中列出的所有依赖：
    ```bash
    uv pip install -r requirements.txt
    ```

## 配置

在运行应用之前，需要创建一个 `config.toml` 文件来配置数据库连接。可以将 `config.example.toml` 复制一份并重命名为 `config.toml`，然后修改其中的配置项。目标库用于更新客户名，主库用于写入日志与回退记录。

```toml
[environments.dev.target_database]
host = "127.0.0.1"
port = 3306
user = "root"
password = ""
database = "test"
table = "your_table"
column = "your_column"
id_column = "your_id_column"

[environments.dev.main_database]
host = "127.0.0.1"
port = 3306
user = "root"
password = ""
database = "anti_masking_main"
log_table = "masking_replace_log"
log_detail_table = "masking_replace_log_detail"
```

### 日志表结构（请先在数据库中创建）

```sql
CREATE TABLE masking_replace_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id VARCHAR(64) UNIQUE,
  env_name VARCHAR(64),
  operator VARCHAR(64),
  mode VARCHAR(16),
  created_at DATETIME,
  total_rows INT,
  status VARCHAR(16)
);

CREATE TABLE masking_replace_log_detail (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  batch_id VARCHAR(64),
  row_id VARCHAR(128),
  old_name TEXT,
  new_name TEXT,
  updated_at DATETIME,
  INDEX idx_batch_id (batch_id)
);
```

## 部署与运行

### 使用 Docker

1.  **构建 Docker 镜像:**
    在项目根目录下，执行以下命令来构建 Docker 镜像：
    ```bash
    docker build -t anti-masking .
    ```

2.  **运行 Docker 容器:**
    构建成功后，执行以下命令来运行 Docker 容器。请确保将 `config.toml` 文件挂载到容器中，并使用 `-d` 标志使其在后台运行。
    ```bash
    docker run -d -p 8501:8501 -v $(pwd)/config.toml:/app/config.toml anti-masking
    ```
    要查看容器日志，可以使用 `docker logs <container_id_or_name>`。要停止容器，可以使用 `docker stop <container_id_or_name>`。
    应用程序将在 `http://localhost:8501` 上可用。

### 本地运行 (Python)

1.  **激活虚拟环境:**
    ```bash
    source .venv/bin/activate
    ```

2.  **安装依赖 (如果尚未安装):**
    ```bash
    uv pip install -r requirements.txt
    ```

3.  **运行 Streamlit 应用:**
    ```bash
    streamlit run app.py
    ```
    应用程序将在 `http://localhost:8501` 上可用。
