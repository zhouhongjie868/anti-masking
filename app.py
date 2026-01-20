import streamlit as st
import mysql.connector
import toml
import pandas as pd
import io


def single_replacement(db_config):


    """


    UI and logic for single name replacement.


    """


    st.header("单个替换")


    id_val = st.text_input("ID")


    name_a = st.text_input("原客户名")


    name_b = st.text_input("替换后的客户名")





    if st.button("执行单个替换"):


        db_host = db_config.get("host")


        db_port = db_config.get("port")


        db_user = db_config.get("user")


        db_password = db_config.get("password")


        db_name = db_config.get("database")


        db_table = db_config.get("table")


        db_column = db_config.get("column")


        id_column = db_config.get("id_column")





        if not all([db_host, db_port, db_user, db_name, db_table, db_column, name_b]):


            st.error("请在 `config.toml` 中填写所有数据库详细信息，并在UI中填写替换后的客户名。")


        elif not id_val and not name_a:


            st.error("ID 和原客户名必须至少填写一个。")


        else:


            conn = None


            try:


                conn = mysql.connector.connect(


                    host=db_host,


                    port=int(db_port),


                    user=db_user,


                    password=db_password,


                    database=db_name,


                )


                cursor = conn.cursor()





                where_clause = ""


                params = []





                if id_val:


                    where_clause = f"{id_column} = %s"


                    params.append(id_val)


                else:


                    where_clause = f"{db_column} = %s"


                    params.append(name_a)





                query = f"UPDATE {db_table} SET {db_column} = %s WHERE {where_clause}"


                params.insert(0, name_b)


                


                cursor.execute(query, tuple(params))


                conn.commit()


                st.success(f"成功更新了 {cursor.rowcount} 条记录。")


            except mysql.connector.Error as err:


                handle_db_error(err)


            finally:


                if conn and conn.is_connected():


                    cursor.close()


                    conn.close()


def batch_replacement(db_config):


    """


    UI and logic for batch name replacement.


    """


    st.header("批量替换")


    st.write("下载Excel模板，填写后上传以进行批量替换。")





    id_column_name = db_config.get("id_column", "ID")


    template_df = pd.DataFrame({id_column_name: ["示例ID1", "示例ID2"], "原客户名": ["示例客户A", "示例客户B"], "替换后客户名": ["新客户A", "新客户B"]})


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


                db_host = db_config.get("host")


                db_port = db_config.get("port")


                db_user = db_config.get("user")


                db_password = db_config.get("password")


                db_name = db_config.get("database")


                db_table = db_config.get("table")


                db_column = db_config.get("column")


                id_column = db_config.get("id_column")





                if not all([db_host, db_port, db_user, db_name, db_table, db_column, id_column]):


                    st.error("请在 `config.toml` 中填写所有数据库详细信息。")


                elif edited_df.empty:


                    st.warning("上传的Excel文件为空或编辑后无数据。")


                elif (id_column_name not in edited_df.columns and "原客户名" not in edited_df.columns) or "替换后客户名" not in edited_df.columns:


                    st.error(f"Excel文件必须包含 '{id_column_name}' 或 '原客户名' 列，以及 '替换后客户名' 列。")


                else:


                    conn = None


                    try:


                        conn = mysql.connector.connect(


                            host=db_host,


                            port=int(db_port),


                            user=db_user,


                            password=db_password,


                            database=db_name,


                        )


                        cursor = conn.cursor()


                        total_replaced_count = 0


                        st.write("开始批量替换...")


                        progress_bar = st.progress(0)


                        


                        for i, row in edited_df.iterrows():


                            new_name = row.get("替换后客户名")


                            id_val = row.get(id_column_name)


                            old_name = row.get("原客户名")





                            if pd.isna(new_name) or (pd.isna(id_val) and pd.isna(old_name)):


                                st.warning(f"跳过无效行: ID={id_val}, 原客户名={old_name}, 替换后客户名={new_name}")


                                continue





                            where_clause = ""


                            params = []


                            


                            if pd.notna(id_val):


                                where_clause = f"{id_column} = %s"


                                params.append(str(id_val))


                            elif pd.notna(old_name):


                                where_clause = f"{db_column} = %s"


                                params.append(old_name)


                            else:


                                continue # Should be caught by the earlier check, but as a safeguard





                            query = f"UPDATE {db_table} SET {db_column} = %s WHERE {where_clause}"


                            params.insert(0, new_name)





                            cursor.execute(query, tuple(params))


                            conn.commit()


                            total_replaced_count += cursor.rowcount


                            


                            progress_bar.progress((i + 1) / len(edited_df))


                            


                        st.success(f"批量替换完成！共替换了 {total_replaced_count} 条记录。")


                    except mysql.connector.Error as err:


                        handle_db_error(err)


                    except Exception as e:


                        st.error(f"发生未知错误: {e}")


                    finally:


                        if conn and conn.is_connected():


                            cursor.close()


                            conn.close()


        except Exception as e:


            st.error(f"读取Excel文件失败: {e}")


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


def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(layout="wide")
    local_css("style.css")

    st.title("Anti Masking")

    # Load configuration from config.toml
    try:
        config = toml.load("config.toml")
        db_config = config.get("database", {})
    except FileNotFoundError:
        st.error("配置文件 `config.toml` 未找到。请创建它。")
        st.stop()

    # Sidebar for navigation
    st.sidebar.title("导航")
    selection = st.sidebar.radio("选择操作模式", ["单个替换", "批量替换"])

    # Display selected page
    if selection == "单个替换":
        single_replacement(db_config)
    elif selection == "批量替换":
        batch_replacement(db_config)


if __name__ == "__main__":
    main()
