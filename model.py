from scipy.stats import poisson
import pandas as pd
import numpy as np
import math

def run_metric_model(df_data):

#-------------------------------------------------------------------
#1. INITIALIZATION
#-------------------------------------------------------------------

#Load required libraries
    results = {}

#Initialize model parameters

    #budget constraint
    C = 85000

#-------------------------------------------------------------------
#2. LOAD INPUT DATA
#-------------------------------------------------------------------

#Read spare part master data:
    cost_df = df_data["Total inventory costs"]

#Load right sheet:
    demand_df = df_data["Total inventory costs"]

#demad fractions for locations j
    f_j = {
        0: 1,               #this is VSM
        1: 0.7991,          #this is virtual hub in Rijssen
        2: 0.1111,          #this is VUSA
        3: 0.0556,          #this is the regional hub in UK
        4: 0.0342           #this is the regional hub in UAE
    }

    #Transportation lead time data: 
    O_j = { 
        0: 0.0385, 
        1: 0.0027, #this is virtual hub in Rijssen 
        2: 0.1346, #this is VUSA 
        3: 0.0110, #this is the regional hub in UK 
        4: 0.1346  #this is the regional hub in UAE 
    } 

    #Emergency shipment lead time data:
    E_j = {
        1: 0.0027,
        2: 0.0027,
        3: 0.0027,
        4: 0.0027
    }

    #costs of emergency shipment
    c_em = {
        1: 0, #this is virtual hub in Rijssen
        2: 5, #this is VUSA
        3: 5, #this is the regional hub in UK
        4: 5  #this is the regional hub in UAE 
    }

    # Lead time variance (YOU must calibrate these)
    Var_O_j = {
        0: 0.0001,
        1: 0.00005,
        2: 0.0002,
        3: 0.0001,
        4: 0.0002
    }

    Var_E_j = {
        1: 0.00002,
        2: 0.00002,
        3: 0.00002,
        4: 0.00002
    }

#-------------------------------------------------------------------
# 3. DEFINE SETS
#-------------------------------------------------------------------

#define the set of materials

    # Load EBO sheet
    part_df = df_data["Total inventory costs"]

    # Remove spaces from column names
    part_df.columns = part_df.columns.str.strip()

    # Remove empty rows
    part_df = part_df.dropna(subset=["Material description"])

    # Define spare part set
    P = part_df["Material description"].tolist()

    # Number of spare parts
    I = len(P)

#define location set:

    #define locations
    L = [0, 1, 2, 3, 4]

    #number of locations
    J = len(L)

#-------------------------------------------------------------------
#4. PREPROCESSING
#-------------------------------------------------------------------

#Assigning demand to the parts:

    #demand parameter lambda
    lambda_part = {}   

    #for loop looping over all indivdual parts
    for _, row in demand_df.iterrows():

        #going over all the materials and assigning the demand to the right part
        i = row["Material description"]
        lambda_part[i] = row["# of occurances in sales data"]

    #make lambda for each part and location
    lambda_ij = {}

    #loop over all the parts
    for i in lambda_part:
        #loop over all the locations
        for j in L:
            
            #cacluate the demand per location and per part
            lambda_ij[(i, j)] = lambda_part[i] * f_j[j]

    # ---------------------------------------------------
    # VARI-METRIC: DEMAND VARIANCE
    # ---------------------------------------------------

    # Poisson assumption:
    # Var(D) = E[D]
    var_lambda_part = {}

    for i in lambda_part:
        var_lambda_part[i] = lambda_part[i]


    def demand_var_during_leadtime(i, j, lead_time_mean, lead_time_var):

        E_D = lambda_ij[(i, j)]
        Var_D = var_lambda_part[i]

        return (
            lead_time_mean * Var_D
            + (E_D ** 2) * lead_time_var
        )

#Assigning costs to the parts:
    
    #cost parameter
    cost_part = {}

    #for loop looping over all indivdual parts
    for _, row in cost_df.iterrows():

        #going over all the materials and assigning the cost to the right part
        i = row["Material description"]
        cost_part[i] = row["Purchase price"] / row["Purchase price per"]


#-------------------------------------------------------------------
#5. INITIALIZE INVENTORY LEVELS + CALCULATE BACKORDERS FOR DEPOT
#-------------------------------------------------------------------

#Initializing the inventory levels and setting them to zero
    
    #making the stock level parameter
    s_ij = {}
    
    #looping over all the disinct parts i
    for i in P:

        #looping over all the bases j
        for j in L:

            #setting stock to zero
            s_ij[(i, j)] = 0

    
#calculate the Expected Back Orders with zero stock
    
    #making the mu parameter which represents the demand during lead time
    mu_i0 = {}
    EBO_i0 = {}
    
    for i in P:
        mu_i0[i] = lambda_ij[(i, 0)] * O_j[0]


    def ebo_exact(mu, s):

        if s == 0:
            return mu

        term1 = mu * (1 - poisson.cdf(s - 1, mu))
        term2 = s * (1 - poisson.cdf(s, mu))

        return max(0.0, term1 - term2)


    for i in P:
        EBO_i0[i] = ebo_exact(mu_i0[i], s_ij[(i, 0)])


#-------------------------------------------------------------------
#6. CALCULATE PIPELINE STOCK + BACKORDERS FOR BASES
#-------------------------------------------------------------------

    #calculating the pipeline
    def compute_mu_ij():

        mu_ij = {}
        theta_ij = {}
        EBO_i0_dynamic = {}

        for i in P:

            # --------------------------
            # DEPOT PIPELINE
            # --------------------------
            mu_ij[(i, 0)] = lambda_ij[(i, 0)] * O_j[0]

            EBO_i0_dynamic[i] = ebo_exact(
                mu_ij[(i, 0)],
                s_ij[(i, 0)]
            )

            if lambda_ij[(i, 0)] > 0:
                depot_fill_rate = max(
                    0,
                    1 - EBO_i0_dynamic[i] / lambda_ij[(i, 0)]
                )
            else:
                depot_fill_rate = 0

            for j in L:

                if j == 0:
                    continue

                if lambda_ij[(i, 0)] == 0:
                    mu_ij[(i, j)] = 0
                    theta_ij[(i, j)] = 0
                    continue

                # --------------------------
                # REGULAR LEAD TIME
                # --------------------------
                waiting_time = EBO_i0_dynamic[i] / lambda_ij[(i, 0)]

                regular_lead_time = O_j[j] + waiting_time

                mu_regular = lambda_ij[(i, j)] * regular_lead_time

                # --------------------------
                # STOCKOUT PROBABILITY
                # --------------------------
                base_stockout_prob = 1 - poisson.cdf(
                    s_ij[(i, j)],
                    mu_regular
                )

                # --------------------------
                # EMERGENCY FRACTION (OZKAN θ)
                # --------------------------
                theta_ij[(i, j)] = base_stockout_prob * depot_fill_rate

                # --------------------------
                # SPLIT DEMAND FLOWS
                # --------------------------
                lambda_em = theta_ij[(i, j)] * lambda_ij[(i, j)]
                lambda_reg = (1 - theta_ij[(i, j)]) * lambda_ij[(i, j)]

                # --------------------------
                # SEPARATE PIPELINES
                # --------------------------
                mu_em = lambda_em * E_j[j]
                mu_reg = lambda_reg * regular_lead_time

                # --------------------------
                # TOTAL EFFECTIVE PIPELINE
                # --------------------------
                mu_ij[(i, j)] = mu_em + mu_reg

        return mu_ij, theta_ij

#calculating the expected backorders for the bases j with the pipeline

    #making the parameter for the bases
    def compute_EBO(mu_ij):

        EBO_ij = {}

        for i in P:
            for j in L:

                EBO_ij[(i, j)] = ebo_exact(mu_ij[(i, j)], s_ij[(i, j)])

        return EBO_ij


#-------------------------------------------------------------------
#7. CALCULATE EXPECTED BACKORDERS REDUCTION
#-------------------------------------------------------------------

#calculating the expected backorders reductions
    
    #making a simple function that calculates the reduction
    def ebo_reduction(mu, s):

        reduction = (
            ebo_exact(mu, s)
            - ebo_exact(mu, s + 1)
        )

        return max(0.0, reduction)


#-------------------------------------------------------------------
#9. OPTIMIZATION PROCEDURE
#-------------------------------------------------------------------

#Calculating the optimization of spare parts til budget is exhausted

    #define parameters for optimization
    DeltaEBO = {}
    Efficiency = {}
    TotalCost = 0

    #WHILE budget not exhausted:
    while True:

        mu_ij, theta_ij = compute_mu_ij()
        EBO_ij = compute_EBO(mu_ij)
        
        best_i = None
        best_j = None
        best_eff = -1
        
        #looping over all the distinct parts i
        for i in P:

            #looping over all the bases j
            for j in L:            

                #calculate the ebo reduction
                DeltaEBO[(i, j)] = ebo_reduction(mu_ij[(i, j)], s_ij[(i, j)])

                #calculate the efficiency:
                Efficiency[(i, j)] = DeltaEBO[(i, j)] / cost_part[i]

                if Efficiency[(i, j)] > best_eff:

                    best_eff = Efficiency[(i, j)]
                    best_i = i
                    best_j = j

        #stop if the costs goes over the budget
        if TotalCost + cost_part[best_i] > C:
            break

        #Allocate one stock unit to the best place
        s_ij[(best_i, best_j)] += 1

        #update the totalcost with the part added
        TotalCost += cost_part[best_i]

        #calculate the backorders for the updated part
        EBO_ij[(best_i, best_j)] = ebo_exact(
            mu_ij[(best_i, best_j)],
            s_ij[(best_i, best_j)]
        )

        mu_ij, theta_ij = compute_mu_ij()
        EBO_ij = compute_EBO(mu_ij)

# ---------------------------------------------------
# FILL RATE (FINAL STATE)
# ---------------------------------------------------

    SupplyAvailability = {}

    for i in P:

        total_ebo = 0

        for j in L:

            if j == 0:
                continue  # exclude depot

            total_ebo += EBO_ij[(i, j)]


        SupplyAvailability[i] = 1 - total_ebo


#-------------------------------------------------------------------
#10. OBJECTIVE FUNCTION
#-------------------------------------------------------------------

    TotalEBO = 0

    for i in P:

        for j in L:


            TotalEBO += EBO_ij[(i,j)]


    TotalEmergencyCost = 0

    for i in P:
        for j in L:

            if j == 0:
                continue

            TotalEmergencyCost += (
                theta_ij[(i,j)]
                * lambda_ij[(i,j)]
                * c_em[j]
            )

    # ---------------------------------------------------
    # RESULTS
    # ---------------------------------------------------

    results = {
        "I": I,
        "J": J,
        "demand": lambda_part,
        "lambda_ij": lambda_ij,
        "O_j": O_j,
        "cost": cost_part,
        "s_ij": s_ij,
        "EBO_i0": EBO_i0,
        "mu_ij": mu_ij,
        "EBO_ij": EBO_ij,
        "EBO_reduction": DeltaEBO,
        "total": TotalEBO,
        "TotalCost": TotalCost,
        "SupplyAvailability": SupplyAvailability,
        "theta_ij": theta_ij,
        "emergencycost": TotalEmergencyCost,
    }

    return results