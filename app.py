import streamlit as st
import pandas as pd

from model import run_metric_model

# ---------------------------------------------------
# PAGE TITLE
# ---------------------------------------------------

st.title("METRIC Dashboard")


# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------

uploaded_file = st.file_uploader(
    "Upload Excel or CSV File",
    type=["csv", "xlsx"]
)

# ---------------------------------------------------
# READ FILE
# ---------------------------------------------------

if uploaded_file is not None:

    # Read file
    if uploaded_file.name.endswith(".xlsx"):
        df_data = pd.read_excel(uploaded_file, sheet_name=None)

    st.success("Excel file loaded successfully")

    # Show available sheets
    st.write("Available sheets:")

    st.write(list(df_data.keys()))

    # Dropdown to select sheet
    selected_sheet = st.selectbox(
        "Select sheet",
        list(df_data.keys())
    )

    # Show selected sheet
    df = df_data[selected_sheet]

    st.header(f"Sheet: {selected_sheet}")

    # Convert problematic large integer columns to string
    df = df.astype(str)

    st.dataframe(df)

    # ---------------------------------------------------
    # RUN BUTTON
    # ---------------------------------------------------

    if st.button("Run METRIC Calculation"):

        # Run calculations from separate file
        results = run_metric_model(df_data)

        # ---------------------------------------------------
        # SHOW RESULTS
        # ---------------------------------------------------

        st.header("Results")

        st.write(f"#### Number of spare parts: {results['I']}")
        st.write(f"#### Number of locations: {results['J']}")
        st.write(f"#### Lead time: {results['O_j']}")
        st.write("#### Demand per hub")

        hub_df = pd.DataFrame(
            [
                [
                    i,
                    j,
                    demand,
                    results["s_ij"][(i, j)]
                ]
                for (i, j), demand in results["lambda_ij"].items()
            ],
            columns=["Material", "Hub", "Demand", "s_ij"]
        )

        hub_df["Cost per part"] = hub_df["Material"].map(results["cost"])

        # ONLY DEPOT EBO (j=0)
        hub_df["EBO (depot)"] = hub_df["Material"].map(results["EBO_i0"])

        st.dataframe(hub_df)