import streamlit as st
import pandas as pd

from model import run_metric_model
from model_VARI import run_metric_model_vari
from model_VARI_solo import run_metric_model_vari_solo

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
        results = run_metric_model_vari_solo(df_data)

        # ---------------------------------------------------
        # SHOW RESULTS
        # ---------------------------------------------------

        st.header("Results")

        st.write(f"#### Number of spare parts: {results['I']}")
        st.write(f"#### Number of locations: {results['J']}")
        st.write(f"#### Lead time: {results['O_j']}")
        st.write(f"#### total backorders: {results['total']}")
        st.write(f"#### total costs: {results['TotalCost']}")
        #st.write(f"#### total emergency costs: {results['emergencycost']}")

        st.metric(
            "Average Supply Availability",
            f"{sum(results['SupplyAvailability'].values()) / len(results['SupplyAvailability']):.2%}"
        )
        
        st.write("#### Demand per hub")

        hub_df = pd.DataFrame(
            [
                [
                    i,
                    j,
                    demand,
                    results["s_ij"][(i, j)],
                    results["mu_ij"].get((i, j), None),
                    results["EBO_ij"][(i, j)],
                    results["EBO_reduction"][(i, j)],
                    results["var_ij"][(i, j)],
                    #results["theta_ij"].get((i, j), None),
                ]
                for (i, j), demand in results["lambda_ij"].items()
            ],
            columns=["Material", "Hub", "Demand", "s_ij", "mu_ij", "EBO_ij", "reduction", "var_ij"]
        )

        hub_df["Cost per part"] = hub_df["Material"].map(results["cost"])

        hub_df["availability"] = hub_df["Material"].map(results["SupplyAvailability"])

        st.dataframe(hub_df)

