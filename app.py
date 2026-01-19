import streamlit as st
import mysql.connector
import toml

st.title("Anti Masking")

# Load configuration
try:
    config = toml.load("config.toml")
    db_config = config.get("database", {})
except FileNotFoundError:
    st.error("Config file `config.toml` not found. Please create it.")
    st.stop()


st.write("客户名称替换")
name_a = st.text_input("原客户名")
name_b = st.text_input("替换后的客户名")

if st.button("替换"):
    db_host = db_config.get("host")
    db_port = db_config.get("port")
    db_user = db_config.get("user")
    db_password = db_config.get("password")
    db_name = db_config.get("database")
    db_table = db_config.get("table")
    db_column = db_config.get("column")

    if not all(
        [db_host, db_port, db_user, db_name, db_table, db_column, name_a, name_b]
    ):
        st.error(
            "Please fill in all database details in `config.toml` and name mappings in the UI."
        )
    else:
        try:
            conn = mysql.connector.connect(
                host=db_host,
                port=int(db_port),
                user=db_user,
                password=db_password,
                database=db_name,
            )
            cursor = conn.cursor()

            query = f"UPDATE {db_table} SET {db_column} = %s WHERE {db_column} = %s"
            cursor.execute(query, (name_b, name_a))
            conn.commit()

            st.success(
                f"Successfully replaced {cursor.rowcount} occurrences of '{name_a}' with '{name_b}'."
            )

        except mysql.connector.Error as err:
            st.error(f"Error: {err}")
        finally:
            if "conn" in locals() and conn.is_connected():
                cursor.close()
                conn.close()
