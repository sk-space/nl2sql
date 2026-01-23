import streamlit as st
from logger import get_logger, setup_file_logging
import requests
import pandas as pd

st.set_page_config(layout="wide")
setup_file_logging("server.log")
logger = get_logger(__name__)

base_url = "http://localhost:8001/api"

st.title("Welcome, NL2SQL")


left, right = st.columns([3, 2], gap="large")

with left:
    query = st.text_input("Enter your query", key="query")
    if st.button("Submit"):
        if not query.strip():
            st.error("Please enter a query.")
        else:
            endpoint = f"{base_url}/query"
            payload = {"query": query}

            try:
                resp = requests.post(endpoint, json=payload, timeout=15)
                resp.raise_for_status()

                data = resp.json()
                sql = data.get("sql")
                logger.info(f"SQL: {sql}")
                st.subheader("Generated SQL")
                st.code(sql or "No SQL generated.")

                if sql:
                    endpoint = f"{base_url}/execute-sql"
                    try:
                        result_resp = requests.post(endpoint, json={"query": sql}, timeout=15)
                        result_resp.raise_for_status()
                        result_json = result_resp.json()
                    except requests.RequestException as e:
                        logger.exception("execute-sql request failed")
                        st.error(f"SQL execution request failed: {e}")
                    except ValueError:
                        logger.exception("execute-sql returned non-JSON")
                        st.error("SQL execution response was not valid JSON.")
                    else:
                        logger.info("execute-sql success=%s", result_json.get("success"))

                        if not result_json.get("success", False):
                            st.error("SQL execution failed.")
                            st.json(result_json)
                        else:
                            rows = result_json.get("data") or []
                            cols = result_json.get("columns") or []

                            if not isinstance(rows, list):
                                rows = [rows]

                            df = pd.DataFrame(rows)

                            if cols:
                                ordered = [c for c in cols if c in df.columns]
                                if ordered:
                                    df = df.reindex(columns=ordered)

                            st.subheader("Query Result")
                            st.dataframe(df, use_container_width=True)
            except requests.RequestException as e:
                logger.exception("Request failed")
                st.error(f"Request failed: {e}")
            except ValueError:
                st.error("Response was not valid JSON.")

with right:
    st.header("Database Schema")
    # if st.button("Load Schema"):
    endpoint = f"{base_url}/schema"
    try:
        resp = requests.get(endpoint, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        schema = data.get("schema", "No schema available.")
        st.text_area("Schema", value=schema, height=800)
    except requests.RequestException as e:
        logger.exception("Schema request failed")
        st.error(f"Schema request failed: {e}")
    except ValueError:
        logger.exception("Schema returned non-JSON")
        st.error("Schema response was not valid JSON.")