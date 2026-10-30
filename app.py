import streamlit as st
import pandas as pd
from model import run_metric_model
from model_VARI import run_metric_model_vari
from model_VARI_solo import run_metric_model_vari_solo
from model_VARI_new import run_metric_model_vari_new
from Final_model import run_metric_model_final
from model_VARI_soloV2 import run_metric_model_vari_solo_V2
from model_VARI_convex import run_metric_model_vari_convex
from model_current_sit import run_metric_model_current_sit
# ---------------------------------------------------
# PAGE TITLE
# ---------------------------------------------------
st.title("METRIC Dashboard")
# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["csv", "xlsx"])
# ---------------------------------------------------
# READ FILE
# ---------------------------------------------------
if uploaded_file is not None:
    if uploaded_file.name.endswith(".xlsx"):
        df_data = pd.read_excel(uploaded_file, sheet_name=None)
        st.success("Excel file loaded successfully")
        st.write("Available sheets:")
        st.write(list(df_data.keys()))
        selected_sheet = st.selectbox("Select sheet", list(df_data.keys()))
        df = df_data[selected_sheet]
        st.header(f"Sheet: {selected_sheet}")
        st.dataframe(df.astype(str))
    else:
        st.warning("The selected model requires an Excel workbook with the 'Total inventory costs' sheet.")
        st.stop()
    # ---------------------------------------------------
    # RUN BUTTON
    # ---------------------------------------------------
    if st.button("Run METRIC Calculation"):
        results = run_metric_model_final(df_data)
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
        st.write(f"#### Average waiting time (years): {results['AverageWaitingTime']:.6f}")
        st.write(f"#### Average waiting time (days): {results['AverageWaitingTime_days']:.6f}")
        # Total demand-weighted waiting days per year across customer-serving bases.
        total_waiting_days = sum(
            results["lambda_ij"][(i, j)] * results["WaitingTime_ij"].get((i, j), 0.0) * 365
            for (i, j) in results["lambda_ij"] if j != 0
        )
        st.write(f"#### Total waiting time (waiting days/year): {total_waiting_days:.6f}")
        total_fill_rate = results.get("TotalAverageFillRate")
        st.write(f"#### Total Average Fill Rate: {total_fill_rate:.3%}"
                 if total_fill_rate is not None else "#### Total Average Fill Rate: N/A")
        # ---------------------------------------------------
        # RESULTS PER BASE
        # ---------------------------------------------------
        st.header("Results per base")
        location_names = {
            0: "VSM",
            1: "Virtual hub (NL)",
            2: "VUSA",
            3: "Regional hub (UK)",
            4: "Regional hub (UAE)"
        }
        base_results = []
        for j in range(results["J"]):
            total_ebo_base = sum(
                results["EBO_ij"][(i, j)]
                for i in results["demand"].keys()
            )
            system_availability = results["SystemAvailability_j"].get(j)
            average_fill_rate = results["AverageFillRate_j"].get(j)
            demand_base = sum(
                results["lambda_ij"][(i, j)]
                for i in results["demand"]
            )
            waiting_time_base = (sum(
                results["lambda_ij"][(i, j)] *
                results["WaitingTime_ij"].get((i, j), 0.0)
                for i in results["demand"]) / demand_base * 365
                if j != 0 and demand_base > 0 else None
            )
            total_waiting_time_base = (sum(
                results["lambda_ij"][(i, j)] *
                results["WaitingTime_ij"].get((i, j), 0.0) * 365
                for i in results["demand"])
                if j != 0 else None
            )
            base_results.append(
                {"Hub": j,
                 "Location": location_names[j],
                 "Total EBO": total_ebo_base,
                 "System Availability": system_availability,
                 "Average Fill Rate": average_fill_rate,
                 "Average Waiting Time (days)": waiting_time_base,
                 "Total Waiting Time (days/year)": total_waiting_time_base}
            )
        base_results_df = pd.DataFrame(base_results)
        st.dataframe(base_results_df.style.format({
            "Total EBO": "{:.6f}",
            "System Availability": "{:.3%}",
            "Average Fill Rate": "{:.3%}",
            "Average Waiting Time (days)": "{:.6f}",
            "Total Waiting Time (days/year)": "{:.6f}"}, na_rep="N/A")
        )
        for _, row in base_results_df.iterrows():
            st.subheader(row["Location"])
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total EBO", f"{row['Total EBO']:.6f}")
            col2.metric(
                "System Availability", f"{row['System Availability']:.3%}"
                if pd.notna(row["System Availability"]) else "N/A"
            )
            col3.metric(
                "Average Fill Rate", f"{row['Average Fill Rate']:.3%}"
                if pd.notna(row["Average Fill Rate"]) else "N/A"
            )
            col4.metric(
                "Average Waiting Time (days)", f"{row['Average Waiting Time (days)']:.6f}"
                if pd.notna(row["Average Waiting Time (days)"]) else "N/A"
            )
            col5.metric(
                "Total Waiting Time (days/year)", f"{row['Total Waiting Time (days/year)']:.6f}"
                if pd.notna(row["Total Waiting Time (days/year)"]) else "N/A"
            )
        # ---------------------------------------------------
        # HUB RESULTS
        # ---------------------------------------------------
        st.header("Demand per hub")
        hub_df = pd.DataFrame([[
            i, j,
            demand,
            results["s_ij"][(i, j)],
            results["mu_ij"].get((i, j)),
            results["EBO_ij"][(i, j)],
            results["WaitingTime_ij"].get((i, j)),
            results["WaitingTime_reduction"].get((i, j)),
            results["theta_ij"].get((i, j)),
            results["FillRate_ij"].get((i, j))] for (i, j),
            demand in results["lambda_ij"].items()], columns=[
                "Material",
                "Hub",
                "Demand",
                "s_ij",
                "mu_ij",
                "EBO_ij",
                "Waiting Time (years)",
                "Waiting Time Reduction",
                "theta_ij",
                "Fill Rate"
        ])
        hub_df["Waiting Time (days)"] = hub_df["Waiting Time (years)"] * 365
        hub_df["Total Waiting Time (days/year)"] = hub_df["Demand"] * hub_df["Waiting Time (days)"]
        hub_df["Cost per part"] = hub_df["Material"].map(results["cost"])
        hub_df["Z_i"] = hub_df["Material"].map(results["Z_i"])
        hub_df["Group"] = hub_df["Material"].map(results["group_part"])
        hub_df["Weight"] = hub_df["Material"].map(results["weight_part"])
        st.dataframe(hub_df.style.format({
            "Demand": "{:.3f}",
            "mu_ij": "{:.6f}",
            "EBO_ij": "{:.6f}",
            "Waiting Time (years)": "{:.6f}",
            "Waiting Time (days)": "{:.6f}",
            "Total Waiting Time (days/year)": "{:.6f}",
            "Waiting Time Reduction": "{:.6f}",
            "theta_ij": "{:.6f}",
            "Fill Rate": "{:.3%}"}, na_rep="N/A")
        )
