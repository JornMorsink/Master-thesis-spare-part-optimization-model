import streamlit as st
import pandas as pd

from model import run_metric_model
from model_VARI import run_metric_model_vari
from model_VARI_solo import run_metric_model_vari_solo
from model_VARI_new import run_metric_model_vari_new
from model_VARI_soloV2 import run_metric_model_vari_solo_V2
from model_VARI_convex import run_metric_model_vari_convex

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

    if uploaded_file.name.endswith(".xlsx"):
        df_data = pd.read_excel(uploaded_file, sheet_name=None)

    st.success("Excel file loaded successfully")

    st.write("Available sheets:")
    st.write(list(df_data.keys()))

    selected_sheet = st.selectbox(
        "Select sheet",
        list(df_data.keys())
    )

    df = df_data[selected_sheet]

    st.header(f"Sheet: {selected_sheet}")

    df = df.astype(str)

    st.dataframe(df)

    # ---------------------------------------------------
    # RUN BUTTON
    # ---------------------------------------------------

    if st.button("Run METRIC Calculation"):

        results = run_metric_model_vari_convex(df_data)

        # ---------------------------------------------------
        # GENERAL RESULTS
        # ---------------------------------------------------

        st.header("Results")

        st.write(f"#### Number of spare parts: {results['I']}")
        st.write(f"#### Number of locations: {results['J']}")
        st.write(f"#### Lead time: {results['O_j']}")
        st.write(f"#### Total backorders: {results['total']}")
        st.write(f"#### Total costs: {results['TotalCost']}")
        st.write(f"#### Total emergency costs: {results['emergencycost']}")
        st.write(f"#### Total EBO bases: {results['TotalEBO_bases']}")
        st.write(f"#### Average emergency: {results['emergency']}")

        st.metric(
            "Average Supply Availability",
            f"{sum(results['SupplyAvailability'].values()) / len(results['SupplyAvailability']):.2%}"
        )

        # ---------------------------------------------------
        # HUB RESULTS
        # ---------------------------------------------------

        st.header("Demand per hub")

        hub_df = pd.DataFrame(
            [
                [
                    i,
                    j,
                    demand,
                    results["s_ij"][(i, j)],
                    results["mu_ij"].get((i, j), None),
                    results["EBO_ij"][(i, j)],
                    results["EBO_reduction"].get((i, j), None),
                    results["var_ij"][(i, j)],
                    results["theta_ij"].get((i, j), None),
                ]
                for (i, j), demand in results["lambda_ij"].items()
            ],
            columns=[
                "Material",
                "Hub",
                "Demand",
                "s_ij",
                "mu_ij",
                "EBO_ij",
                "reduction",
                "var_ij",
                "theta_ij"
            ]
        )

        hub_df["Cost per part"] = hub_df["Material"].map(results["cost"])
        hub_df["availability"] = hub_df["Material"].map(results["SupplyAvailability"])
        hub_df["Group"] = hub_df["Material"].map(results["group_part"])
        hub_df["Weight"] = hub_df["Material"].map(results["weight_part"])

        st.dataframe(hub_df)

        # ---------------------------------------------------
        # CONVEXITY SUMMARY
        # ---------------------------------------------------

        st.header("Convexity / Starting Point Analysis")

        if "convexity_summary" in results:

            convexity_summary = results["convexity_summary"]

            st.write(
                "The table below shows the recommended starting stock level "
                "for each item and location based on where marginal waiting-time "
                "reductions become non-increasing."
            )

            st.dataframe(convexity_summary)

        else:
            st.warning("No convexity summary was returned by the model.")

        # ---------------------------------------------------
        # CONVEXITY CURVES
        # ---------------------------------------------------

        if "convexity_curves" in results:

            convexity_curves = results["convexity_curves"]

            st.subheader("Detailed convexity curves")

            # Select one item
            materials = sorted(convexity_curves["Item"].unique())

            selected_material = st.selectbox(
                "Select material for convexity analysis",
                materials
            )

            material_curve = convexity_curves[
                convexity_curves["Item"] == selected_material
            ]

            # Select location
            locations = material_curve["Location"].unique()

            selected_location = st.selectbox(
                "Select location",
                locations
            )

            selected_curve = material_curve[
                material_curve["Location"] == selected_location
            ].copy()

            st.dataframe(selected_curve)

            # ---------------------------------------------------
            # WAITING TIME GRAPH
            # ---------------------------------------------------

            st.subheader("Total waiting time by stock level")

            waiting_chart = (
                selected_curve[
                    ["Stock", "Total waiting time"]
                ]
                .set_index("Stock")
            )

            st.line_chart(waiting_chart)

            # ---------------------------------------------------
            # MARGINAL REDUCTION GRAPH
            # ---------------------------------------------------

            st.subheader("Marginal waiting-time reduction")

            marginal_chart = (
                selected_curve[
                    ["Stock", "Marginal waiting-time reduction"]
                ]
                .dropna()
                .set_index("Stock")
            )

            st.line_chart(marginal_chart)

            # ---------------------------------------------------
            # SECOND DIFFERENCE
            # ---------------------------------------------------

            st.subheader("Second difference")

            second_diff_chart = (
                selected_curve[
                    ["Stock", "Second difference"]
                ]
                .dropna()
                .set_index("Stock")
            )

            st.line_chart(second_diff_chart)

        else:
            st.warning("No convexity curves were returned by the model.")

