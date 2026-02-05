import streamlit as st
import mysql.connector
import toml
import pandas as pd
import io
import datetime
import secrets


def _safe_ident(name):
    """
    Basic safeguard to avoid backticks in identifiers.
    """
    if not name:
        return ""
    return name.replace("`", "")


def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_batch_id():
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{ts}-{secrets.token_hex(4)}"


def _insert_batch_log(cursor, log_table, batch_id, env_name, operator, mode):
    query = (
        f"INSERT INTO `{log_table}` "
        "(batch_id, env_name, operator, mode, created_at, total_rows, status) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    cursor.execute(
        query, (batch_id, env_name, operator, mode, _now_str(), 0, "failed")
    )


def _update_batch_log(cursor, log_table, batch_id, total_rows, status):
    query = (
        f"UPDATE `{log_table}` SET total_rows = %s, status = %s WHERE batch_id = %s"
    )
    cursor.execute(query, (total_rows, status, batch_id))


def _insert_detail_logs(cursor, log_detail_table, batch_id, details):
    if not details:
        return
    query = (
        f"INSERT INTO `{log_detail_table}` "
        "(batch_id, row_id, old_name, new_name, updated_at) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    cursor.executemany(query, details)


def _require_log_config(db_config):
    return db_config.get("log_table"), db_config.get("log_detail_table")


def _split_db_config(env_db_config):
    """
    Return (target_db, main_db).
    Supports legacy [database] by using it for both.
    """
    target_db = env_db_config.get("target_database")
    main_db = env_db_config.get("main_database")
    legacy_db = env_db_config.get("database")
    if not target_db and not main_db and legacy_db:
        return legacy_db, legacy_db
    return target_db or {}, main_db or {}


def single_replacement(env_db_config, env_name, operator):
    """
    UI and logic for single name replacement.
    """
    st.set_page_config(page_title="Anti Masking")
    st.header(f"单个替换 - {env_name}")
    id_val = st.text_input("ID(ecif客户号，集团号，商户号等)")
    name_a = st.text_input("原客户名")
    name_b = st.text_input("替换后的客户名")

    if st.button("执行单个替换"):
        target_db, main_db = _split_db_config(env_db_config)
        target_host = target_db.get("host")
        target_port = target_db.get("port")
        target_user = target_db.get("user")
        target_password = target_db.get("password")
        target_name = target_db.get("database")
        target_table = target_db.get("table")
        target_column = target_db.get("column")
        target_id_column = target_db.get("id_column")

        main_host = main_db.get("host")
        main_port = main_db.get("port")
        main_user = main_db.get("user")
        main_password = main_db.get("password")
        main_name = main_db.get("database")
        log_table, log_detail_table = _require_log_config(main_db)

        if not all(
            [
                target_host,
                target_port,
                target_user,
                target_name,
                target_table,
                target_column,
                name_b,
            ]
        ):
            st.error("请在 `config.toml` 中填写目标库的完整信息，并在UI中填写替换后的客户名。")
        elif not all([target_id_column]):
            st.error("请在 `config.toml` 中配置目标库的 `id_column`。")
        elif not all([main_host, main_port, main_user, main_name]):
            st.error("请在 `config.toml` 中填写主库的完整信息。")
        elif not all([log_table, log_detail_table]):
            st.error("请在 `config.toml` 中配置主库日志表 `log_table` 和 `log_detail_table`。")
        elif not operator:
            st.error("操作人不能为空，请在侧边栏填写。")
        elif not id_val and not name_a:
            st.error("ID 和原客户名必须至少填写一个。")
        else:
            conn_target = None
            conn_main = None
            try:
                conn_main = mysql.connector.connect(
                    host=main_host,
                    port=int(main_port),
                    user=main_user,
                    password=main_password,
                    database=main_name,
                )
                conn_target = mysql.connector.connect(
                    host=target_host,
                    port=int(target_port),
                    user=target_user,
                    password=target_password,
                    database=target_name,
                )

                cursor_main = conn_main.cursor()
                cursor_target = conn_target.cursor()
                where_clause = ""
                params = []
                safe_table = _safe_ident(target_table)
                safe_column = _safe_ident(target_column)
                safe_id_column = _safe_ident(target_id_column)
                safe_log_table = _safe_ident(log_table)
                safe_log_detail_table = _safe_ident(log_detail_table)

                if id_val:
                    where_clause = f"`{safe_id_column}` = %s"
                    params.append(id_val)
                else:
                    where_clause = f"`{safe_column}` = %s"
                    params.append(name_a)

                batch_id = _new_batch_id()
                _insert_batch_log(
                    cursor_main, safe_log_table, batch_id, env_name, operator, "single"
                )
                conn_main.commit()

                select_query = (
                    f"SELECT `{safe_id_column}`, `{safe_column}` "
                    f"FROM `{safe_table}` WHERE {where_clause}"
                )
                cursor_target.execute(select_query, tuple(params))
                rows = cursor_target.fetchall()
                details = [
                    (batch_id, str(row[0]), row[1], name_b, _now_str()) for row in rows
                ]
                _insert_detail_logs(
                    cursor_main, safe_log_detail_table, batch_id, details
                )
                conn_main.commit()

                query = (
                    f"UPDATE `{safe_table}` SET `{safe_column}` = %s WHERE {where_clause}"
                )
                params.insert(0, name_b)

                cursor_target.execute(query, tuple(params))
                conn_target.commit()

                _update_batch_log(
                    cursor_main, safe_log_table, batch_id, len(rows), "done"
                )
                conn_main.commit()

                if len(rows) == 0:
                    st.warning("未匹配到任何记录，已记录本次操作。")
                else:
                    st.success(f"成功更新了 {cursor_target.rowcount} 条记录。")

            except mysql.connector.Error as err:
                try:
                    if conn_main and conn_main.is_connected():
                        cursor_main = conn_main.cursor()
                        _update_batch_log(
                            cursor_main, safe_log_table, batch_id, 0, "failed"
                        )
                        conn_main.commit()
                except Exception:
                    pass
                handle_db_error(err)
            finally:
                if conn_target and conn_target.is_connected():
                    cursor_target.close()
                    conn_target.close()
                if conn_main and conn_main.is_connected():
                    cursor_main.close()
                    conn_main.close()


def batch_replacement(env_db_config, env_name, operator):
    """
    UI and logic for batch name replacement.
    """
    st.header(f"批量替换 - {env_name}")
    st.write("下载Excel模板，填写后上传以进行批量替换。")

    target_db, main_db = _split_db_config(env_db_config)
    id_column_name = target_db.get("id_column", "ID")
    template_df = pd.DataFrame(
        {
            id_column_name: ["示例ID1", "示例ID2"],
            "原客户名": ["示例客户A", "示例客户B"],
            "替换后客户名": ["新客户A", "新客户B"],
        }
    )
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        template_df.to_excel(writer, index=False, sheet_name="客户名替换")
    excel_buffer.seek(0)

    st.download_button(
        label="下载Excel模板",
        data=excel_buffer,
        file_name="客户名替换模板.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    uploaded_file = st.file_uploader("上传Excel文件", type=["xlsx"])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file, dtype={id_column_name: str})
            st.subheader("请确认要替换的客户名列表")
            st.write("您可以编辑表格中的内容。")
            edited_df = st.data_editor(df, num_rows="dynamic")

            if st.button("执行批量替换"):
                target_host = target_db.get("host")
                target_port = target_db.get("port")
                target_user = target_db.get("user")
                target_password = target_db.get("password")
                target_name = target_db.get("database")
                target_table = target_db.get("table")
                target_column = target_db.get("column")
                target_id_column = target_db.get("id_column")

                main_host = main_db.get("host")
                main_port = main_db.get("port")
                main_user = main_db.get("user")
                main_password = main_db.get("password")
                main_name = main_db.get("database")
                log_table, log_detail_table = _require_log_config(main_db)

                if not all(
                    [
                        target_host,
                        target_port,
                        target_user,
                        target_name,
                        target_table,
                        target_column,
                        target_id_column,
                    ]
                ):
                    st.error("请在 `config.toml` 中填写目标库的完整信息。")
                elif not all([main_host, main_port, main_user, main_name]):
                    st.error("请在 `config.toml` 中填写主库的完整信息。")
                elif not all([log_table, log_detail_table]):
                    st.error("请在 `config.toml` 中配置主库日志表 `log_table` 和 `log_detail_table`。")
                elif not operator:
                    st.error("操作人不能为空，请在侧边栏填写。")
                elif edited_df.empty:
                    st.warning("上传的Excel文件为空或编辑后无数据。")
                elif (
                    id_column_name not in edited_df.columns
                    and "原客户名" not in edited_df.columns
                ) or "替换后客户名" not in edited_df.columns:
                    st.error(
                        f"Excel文件必须包含 '{id_column_name}' 或 '原客户名' 列，以及 '替换后客户名' 列。"
                    )
                else:
                    conn_target = None
                    conn_main = None
                    try:
                        conn_main = mysql.connector.connect(
                            host=main_host,
                            port=int(main_port),
                            user=main_user,
                            password=main_password,
                            database=main_name,
                        )
                        conn_target = mysql.connector.connect(
                            host=target_host,
                            port=int(target_port),
                            user=target_user,
                            password=target_password,
                            database=target_name,
                        )
                        cursor_main = conn_main.cursor()
                        cursor_target = conn_target.cursor()
                        total_replaced_count = 0
                        st.write("开始批量替换...")
                        progress_bar = st.progress(0)
                        safe_table = _safe_ident(target_table)
                        safe_column = _safe_ident(target_column)
                        safe_id_column = _safe_ident(target_id_column)
                        safe_log_table = _safe_ident(log_table)
                        safe_log_detail_table = _safe_ident(log_detail_table)

                        batch_id = _new_batch_id()
                        _insert_batch_log(
                            cursor_main,
                            safe_log_table,
                            batch_id,
                            env_name,
                            operator,
                            "batch",
                        )
                        conn_main.commit()
                        total_logged_rows = 0

                        for i, row in edited_df.iterrows():
                            new_name = row.get("替换后客户名")
                            id_val = row.get(id_column_name)
                            old_name = row.get("原客户名")

                            if pd.isna(new_name) or (
                                pd.isna(id_val) and pd.isna(old_name)
                            ):
                                st.warning(
                                    f"跳过无效行: ID={id_val}, 原客户名={old_name}, 替换后客户名={new_name}"
                                )
                                continue

                            where_clause = ""
                            params = []

                            if pd.notna(id_val):
                                where_clause = f"`{safe_id_column}` = %s"
                                params.append(str(id_val))
                            elif pd.notna(old_name):
                                where_clause = f"`{safe_column}` = %s"
                                params.append(old_name)
                            else:
                                continue

                            select_query = (
                                f"SELECT `{safe_id_column}`, `{safe_column}` "
                                f"FROM `{safe_table}` WHERE {where_clause}"
                            )
                            cursor_target.execute(select_query, tuple(params))
                            rows = cursor_target.fetchall()
                            details = [
                                (batch_id, str(r[0]), r[1], new_name, _now_str())
                                for r in rows
                            ]
                            _insert_detail_logs(
                                cursor_main, safe_log_detail_table, batch_id, details
                            )
                            conn_main.commit()
                            total_logged_rows += len(rows)

                            query = (
                                f"UPDATE `{safe_table}` SET `{safe_column}` = %s "
                                f"WHERE {where_clause}"
                            )
                            params.insert(0, new_name)

                            cursor_target.execute(query, tuple(params))
                            conn_target.commit()
                            total_replaced_count += cursor_target.rowcount

                            progress_bar.progress((i + 1) / len(edited_df))

                        _update_batch_log(
                            cursor_main,
                            safe_log_table,
                            batch_id,
                            total_logged_rows,
                            "done",
                        )
                        conn_main.commit()

                        st.success(
                            f"批量替换完成！共替换了 {total_replaced_count} 条记录。"
                        )
                    except mysql.connector.Error as err:
                        try:
                            if conn_main and conn_main.is_connected():
                                cursor_main = conn_main.cursor()
                                _update_batch_log(
                                    cursor_main, safe_log_table, batch_id, 0, "failed"
                                )
                                conn_main.commit()
                        except Exception:
                            pass
                        handle_db_error(err)
                    except Exception as e:
                        st.error(f"发生未知错误: {e}")
                    finally:
                        if conn_target and conn_target.is_connected():
                            cursor_target.close()
                            conn_target.close()
                        if conn_main and conn_main.is_connected():
                            cursor_main.close()
                            conn_main.close()
        except Exception as e:
            st.error(f"读取Excel文件失败: {e}")


def rollback_records(env_db_config, env_name):
    """
    UI and logic for rollback by batch.
    """
    st.header(f"回退记录 - {env_name}")
    target_db, main_db = _split_db_config(env_db_config)
    target_host = target_db.get("host")
    target_port = target_db.get("port")
    target_user = target_db.get("user")
    target_password = target_db.get("password")
    target_name = target_db.get("database")
    target_table = target_db.get("table")
    target_column = target_db.get("column")
    target_id_column = target_db.get("id_column")

    main_host = main_db.get("host")
    main_port = main_db.get("port")
    main_user = main_db.get("user")
    main_password = main_db.get("password")
    main_name = main_db.get("database")
    log_table, log_detail_table = _require_log_config(main_db)

    if not all(
        [
            target_host,
            target_port,
            target_user,
            target_name,
            target_table,
            target_column,
            target_id_column,
        ]
    ):
        st.error("请在 `config.toml` 中填写目标库的完整信息。")
        return
    if not all([main_host, main_port, main_user, main_name]):
        st.error("请在 `config.toml` 中填写主库的完整信息。")
        return
    if not all([log_table, log_detail_table]):
        st.error("请在 `config.toml` 中配置主库日志表 `log_table` 和 `log_detail_table`。")
        return

    conn_target = None
    conn_main = None
    try:
        conn_main = mysql.connector.connect(
            host=main_host,
            port=int(main_port),
            user=main_user,
            password=main_password,
            database=main_name,
        )
        conn_target = mysql.connector.connect(
            host=target_host,
            port=int(target_port),
            user=target_user,
            password=target_password,
            database=target_name,
        )
        cursor_main = conn_main.cursor()
        cursor_target = conn_target.cursor()
        safe_log_table = _safe_ident(log_table)
        safe_log_detail_table = _safe_ident(log_detail_table)
        safe_table = _safe_ident(target_table)
        safe_column = _safe_ident(target_column)
        safe_id_column = _safe_ident(target_id_column)

        cursor_main.execute(
            f"SELECT batch_id, operator, mode, created_at, total_rows, status "
            f"FROM `{safe_log_table}` ORDER BY created_at DESC LIMIT 50"
        )
        batches = cursor_main.fetchall()
        if not batches:
            st.info("暂无日志记录。")
            return

        batch_df = pd.DataFrame(
            batches,
            columns=[
                "batch_id",
                "operator",
                "mode",
                "created_at",
                "total_rows",
                "status",
            ],
        )
        st.subheader("最近操作批次")
        st.dataframe(batch_df, use_container_width=True)

        batch_ids = batch_df["batch_id"].tolist()
        selected_batch = st.selectbox("选择要回退的批次", batch_ids, index=0)

        cursor_main.execute(
            f"SELECT row_id, old_name, new_name, updated_at "
            f"FROM `{safe_log_detail_table}` WHERE batch_id = %s",
            (selected_batch,),
        )
        details = cursor_main.fetchall()
        detail_df = pd.DataFrame(
            details, columns=["row_id", "old_name", "new_name", "updated_at"]
        )
        st.subheader("批次明细")
        st.dataframe(detail_df, use_container_width=True)

        batch_row = batch_df[batch_df["batch_id"] == selected_batch].iloc[0]
        can_rollback = batch_row["status"] == "done" and batch_row["total_rows"] > 0
        if not can_rollback:
            st.info("该批次不可回退（可能已回退、失败或无更新）。")

        if st.button("一键回退", disabled=not can_rollback):
            success_count = 0
            fail_count = 0
            for row_id, old_name, _new_name, _updated_at in details:
                cursor_target.execute(
                    f"UPDATE `{safe_table}` SET `{safe_column}` = %s "
                    f"WHERE `{safe_id_column}` = %s",
                    (old_name, row_id),
                )
                conn_target.commit()
                if cursor_target.rowcount > 0:
                    success_count += 1
                else:
                    fail_count += 1

            cursor_main.execute(
                f"UPDATE `{safe_log_table}` SET status = %s WHERE batch_id = %s",
                ("rollback", selected_batch),
            )
            conn_main.commit()
            st.success(
                f"回退完成：成功 {success_count} 条，失败 {fail_count} 条。"
            )

    except mysql.connector.Error as err:
        handle_db_error(err)
    except Exception as e:
        st.error(f"发生未知错误: {e}")
    finally:
        if conn_target and conn_target.is_connected():
            cursor_target.close()
            conn_target.close()
        if conn_main and conn_main.is_connected():
            cursor_main.close()
            conn_main.close()


def handle_db_error(err):
    """
    Handle database errors and display appropriate messages.
    """
    st.error(f"数据库操作错误: {err}")
    if err.errno == 2013:
        st.warning(
            "无法连接到MySQL服务器。请检查 `config.toml` 中的 `host` 和 `port` 设置。"
            "如果您在Docker容器中运行此应用，请确保 `host` 不是 `localhost` 或 `127.0.0.1`。"
            "在这种情况下，您可能需要使用 `host.docker.internal` (适用于Docker Desktop) 或数据库容器的IP地址。"
        )


def local_css(file_name):
    """
    Load a local CSS file.
    """
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def _load_db_config():
    """
    Load database config(s) from config.toml.
    Supports:
      - legacy [database]
      - [environments.<name>.database]
      - [environments.<name>.target_database] + [environments.<name>.main_database]
    Returns: (env_names, env_to_db_config)
    """
    config = toml.load("config.toml")

    if "environments" in config:
        envs = config.get("environments", {})
        env_to_db = {}
        for name, env_cfg in envs.items():
            env_to_db[name] = {
                "database": env_cfg.get("database", {}),
                "target_database": env_cfg.get("target_database", {}),
                "main_database": env_cfg.get("main_database", {}),
            }
        env_names = list(env_to_db.keys())
        return env_names, env_to_db

    # Backward compatible single environment
    return ["default"], {"default": {"database": config.get("database", {})}}


def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(layout="wide")
    local_css("style.css")

    st.title("Anti Masking")

    # Load configuration from config.toml
    try:
        env_names, env_to_db = _load_db_config()
    except FileNotFoundError:
        st.error("配置文件 `config.toml` 未找到。请创建它。")
        st.stop()
    except Exception as e:
        st.error(f"读取配置文件失败: {e}")
        st.stop()

    # Sidebar for navigation
    st.sidebar.title("导航")
    if not env_names:
        st.error("未在 `config.toml` 中找到任何可用环境。")
        st.stop()

    selected_env = st.sidebar.selectbox("选择环境", env_names, index=0)
    db_config = env_to_db.get(selected_env, {})
    operator = st.sidebar.text_input("操作人")

    selection = st.sidebar.radio("选择操作模式", ["单个替换", "批量替换", "回退记录"])

    # Display selected page
    if selection == "单个替换":
        single_replacement(db_config, selected_env, operator)
    elif selection == "批量替换":
        batch_replacement(db_config, selected_env, operator)
    elif selection == "回退记录":
        rollback_records(db_config, selected_env)


if __name__ == "__main__":
    main()
