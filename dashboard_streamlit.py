import streamlit as st

st.write("TESTE BASICO FUNCIONANDO")

try:
    import pandas as pd
    st.write("Pandas OK")
except Exception as e:
    st.error(f"Pandas erro: {e}")

try:
    import gspread
    st.write("Gspread OK")
except Exception as e:
    st.error(f"Gspread erro: {e}")

try:
    if 'GOOGLE_CREDENTIALS' in st.secrets:
        st.write("Secrets OK")
    else:
        st.write("Secrets FALTANDO")
except Exception as e:
    st.error(f"Secrets erro: {e}")
