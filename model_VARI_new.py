from scipy.stats import poisson, nbinom
import pandas as pd
import numpy as np
import math

def run_metric_model_vari_new(df_data):

#-------------------------------------------------------------------
#1. INITIALIZATION
#-------------------------------------------------------------------

#Load required libraries
    results = {}

#Initialize model parameters

    #budget constraint
    C = 426000

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
        1: 0.1111,          #this is virtual hub in Rijssen
        2: 0.7991,          #this is VUSA
        3: 0.0556,          #this is the regional hub in UK
        4: 0.0342           #this is the regional hub in UAE
    }

    #Transportation lead time data: 
    O_j = {  
        1: 0.0027, #this is virtual hub in Rijssen 
        2: 0.1346, #this is VUSA 
        3: 0.0110, #this is the regional hub in UK 
        4: 0.1346  #this is the regional hub in UAE 
    } 

    #Emergency shipment lead time data:
    E_j = {
        1: 0.00274,
        2: 0.01096,
        3: 0.00274,
        4: 0.01096
    }

    #costs of emergency shipment
    c_em = {
        1: 0, #this is virtual hub in Rijssen
        2: 50, #this is VUSA
        3: 25, #this is the regional hub in UK
        4: 75  #this is the regional hub in UAE 
    }

    # Lead time variance (YOU must calibrate these)
    Var_O_j = {
        0: 0.0077, 
        1: 0.000135, #this is virtual hub in Rijssen 
        2: 0.00673, #this is VUSA 
        3: 0.00055, #this is the regional hub in UK 
        4: 0.00673
    }

    Var_E_j = {
        1: 0.000137,
        2: 0.000548,
        3: 0.000137,
        4: 0.000548
    }

    variance_factor = 1

    Var_O_j = {j: variance_factor * value for j, value in Var_O_j.items()}
    Var_E_j = {j: variance_factor * value for j, value in Var_E_j.items()}
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


    # Assign urgency group to parts
    group_part = {}

    for _, row in cost_df.iterrows():
        i = row["Material description"]
        group_part[i] = row["Group (1 most urgent)"]

    def group_weight(group):
        if group == 1:
            return 1.50   # 50% more important
        elif group == 2:
            return 1.30   # 30% more important
        elif group == 3:
            return 1.15   # 15% more important
        elif group == 4:
            return 1.00   # normal importance
        else:
            return 1.00
    
    # ---------------------------------------------------
    # VARI-METRIC: DEMAND VARIANCE
    # ---------------------------------------------------

    # Poisson assumption:
    # Var(D) = E[D]
    var_lambda_part = {}

    for i in lambda_part:
        var_lambda_part[i] = lambda_part[i]


    def demand_var_during_leadtime(demand_mean, demand_var, lead_time_mean, lead_time_var):

        return (
            lead_time_mean * demand_var
            + (demand_mean ** 2) * lead_time_var
        )

#Assigning costs to the parts:
    
    #cost parameter
    cost_part = {}

    #for loop looping over all indivdual parts
    for _, row in cost_df.iterrows():

        #going over all the materials and assigning the cost to the right part
        i = row["Material description"]
        cost_part[i] = row["Purchase price"] / row["Purchase price per"]

    #Setting lead time for the depot
    O_i0 = {}

    #loop over all the materials and retrieve the corresponding lead time
    for _, row in cost_df.iterrows():
        i = row["Material description"]
        O_i0[i] = row["Lead time depot"]


#-------------------------------------------------------------------
#5. INITIALIZE INVENTORY LEVELS + CALCULATE BACKORDERS FOR DEPOT
#-------------------------------------------------------------------

#Initializing the inventory levels and setting them to zero
    depot_stock = [
        17, 21, 2, 2, 9, 4, 17, 37, 55, 26,
        10, 14, 76, 22, 4, 11, 12, 19, 5, 55,
        53, 50, 60, 83, 65, 1, 4, 12, 4, 54,
        18, 24, 10, 27, 92, 101, 1, 19, 12, 18,
        83, 45, 32, 22, 127, 62, 76, 56, 5, 43,
        26, 5, 6, 12, 5, 9, 81, 10, 73, 6, 4
    ]

    base2_stock = [
        3, 3, 2, 1, 20, 12, 0, 3, 7, 3,
        0, 1, 11, 8, 12, 0, 4, 0, 2, 36,
        65, 33, 60, 40, 7, 4, 8, 5, 8, 8,
        17, 8, 4, 8, 79, 6, 33, 9, 9, 9,
        7, 3, 2, 7, 5, 10, 9, 7, 5, 2,
        3, 9, 5, 17, 7, 4, 28, 12, 7, 5,
        4
    ]

    #making the stock level parameter
    s_ij = {}

    for i in P:
        for j in L:
            s_ij[(i, j)] = 0

    #for i, stock in zip(P, depot_stock):
    #    s_ij[(i, 0)] = stock

    #for i, stock in zip(P, base2_stock):
    #    s_ij[(i, 2)] = stock

    
#calculate the Expected Back Orders with zero stock
    
    #making the mu parameter which represents the demand during lead time
    mu_i0 = {}
    EBO_i0 = {}
    
    for i in P:
        mu_i0[i] = lambda_ij[(i, 0)] * O_i0[i]


    def ebo_exact(mu, s):

        if s == 0:
            return mu

        term1 = mu * (1 - poisson.cdf(s - 1, mu))
        term2 = s * (1 - poisson.cdf(s, mu))

        return max(0.0, term1 - term2)


    for i in P:
        EBO_i0[i] = ebo_exact(mu_i0[i], s_ij[(i, 0)])


    def ebo_vari_metric(mu, var, s):

        if mu <= 0:
            return 0.0

        if var <= mu:
            return ebo_exact(mu, s)

        p = 1 - mu / var
        r = mu ** 2 / (var - mu)

        F_s = nbinom.cdf(s, r, 1 - p)
        F_s_minus_1 = nbinom.cdf(s - 1, r + 1, 1 - p)

        ebo = (
            r * p * (1 - F_s_minus_1) / (1 - p)
            - s * (1 - F_s)
        )

        return max(0.0, ebo)

    # ---------------------------------------------------
    # VARI-METRIC: variance of depot backorders
    # ---------------------------------------------------
    def second_moment_bo(mu, s):

        if mu <= 0:
            return 0.0

        upper = int(mu + 10 * math.sqrt(mu + 1) + s + 10)

        total = 0.0

        for n in range(s + 1, upper + 1):

            total += ((n - s) ** 2) * poisson.pmf(n, mu)

        return total


    def var_bo(mu, s):

        ebo = ebo_exact(mu, s)
        ebo2 = second_moment_bo(mu, s)

        return max(0.0, ebo2 - ebo ** 2)


#-------------------------------------------------------------------
#6. CALCULATE PIPELINE STOCK + BACKORDERS FOR BASES
#-------------------------------------------------------------------

    #calculating the pipeline
    def compute_mu_ij():

        mu_ij = {}
        theta_ij = {}
        var_ij = {}
        EBO_i0_dynamic = {}

        for i in P:

            # --------------------------
            # DEPOT PIPELINE
            # --------------------------
            mu_ij[(i, 0)] = lambda_ij[(i, 0)] * O_i0[i]

            var_ij[(i, 0)] = demand_var_during_leadtime(
                lambda_ij[(i, 0)],
                lambda_ij[(i, 0)],
                O_i0[i],
                Var_O_j[0]
            )
            
            EBO_i0_dynamic[i] = ebo_vari_metric(
                mu_ij[(i, 0)],
                var_ij[(i, 0)],
                s_ij[(i, 0)]
            )
            
            V_BO_s0 = var_bo(
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
                    var_ij[(i, j)] = 0
                    theta_ij[(i, j)] = 0
                    continue

                # --------------------------
                # REGULAR LEAD TIME
                # --------------------------
                waiting_time = EBO_i0_dynamic[i] / lambda_ij[(i, 0)]

                regular_lead_time = O_j[j] + waiting_time

                # --------------------------
                # STOCKOUT PROBABILITY
                # --------------------------
                mu_regular = lambda_ij[(i, j)] * regular_lead_time

                base_stockout_prob = 1 - poisson.cdf(
                    s_ij[(i, j)],
                    mu_regular
                )

                # --------------------------
                # EMERGENCY FRACTION WITH SIMULATION-BASED CORRECTION
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

                var_reg = demand_var_during_leadtime(
                    lambda_reg,
                    lambda_reg,
                    regular_lead_time,
                    Var_O_j[j]
                )

                var_em = demand_var_during_leadtime(
                    lambda_em,
                    lambda_em,
                    E_j[j],
                    Var_E_j[j]
                )

                var_ij[(i, j)] = var_em + var_reg + (f_j[j] ** 2) * V_BO_s0

        return mu_ij, var_ij, theta_ij

#calculating the expected backorders for the bases j with the pipeline

    #making the parameter for the bases
    def compute_EBO(mu_ij, var_ij):

        EBO_ij = {}

        for i in P:
            for j in L:

                mu = mu_ij[(i, j)]
                var = var_ij[(i, j)]
                s = s_ij[(i, j)]

                EBO_ij[(i, j)] = ebo_vari_metric(mu, var, s)

        return EBO_ij


#-------------------------------------------------------------------
#7. CALCULATE EXPECTED BACKORDERS REDUCTION
#-------------------------------------------------------------------


    #making a simple function that calculates the reduction
    def ebo_reduction(mu, var, s):

        current = ebo_vari_metric(mu, var, s)
        future = ebo_vari_metric(mu, var, s + 1)

        return max(0.0, current - future)


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

        mu_ij, var_ij, theta_ij = compute_mu_ij()
        EBO_ij = compute_EBO(mu_ij, var_ij)
        
        best_i = None
        best_j = None
        best_eff = -1
        
        #looping over all the distinct parts i
        for i in P:

            #looping over all the bases j
            for j in L:            

                #calculate the ebo reduction
                DeltaEBO[(i, j)] = ebo_reduction(mu_ij[(i, j)], var_ij[(i, j)], s_ij[(i, j)])

                #calculate the efficiency:
                #normalized_cost = math.log1p(cost_part[i])
                urgency_weight = group_weight(group_part[i])

                if j != 0:
                    emergency_cost_penalty = (
                        theta_ij[(i, j)]
                        * lambda_ij[(i, j)]
                        * c_em[j]
                    )
                else:
                    emergency_cost_penalty = 0

                Efficiency[(i, j)] = (
                    DeltaEBO[(i, j)] 
                    * urgency_weight
                    / (cost_part[i] + emergency_cost_penalty)
                )

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

        mu_ij, var_ij, theta_ij = compute_mu_ij()
        EBO_ij = compute_EBO(mu_ij, var_ij)

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


    TotalEBO_bases = sum(
        EBO_ij[(i, j)]
        for i in P
        for j in L
        if j != 0
    )

    avg_theta = {}

    for j in L:

        if j == 0:
            continue

        avg_theta[j] = (
            sum(theta_ij[(i, j)] for i in P)
            / len(P)
        )
    
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
        "var_ij": var_ij,
        "TotalEBO_bases": TotalEBO_bases,
        "emergency": avg_theta,
        "group_part": group_part,
        "weight_part": {
            i: group_weight(group_part[i])
            for i in P
        },
    }

    return results