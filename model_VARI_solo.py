from scipy.stats import poisson, nbinom
import pandas as pd
import numpy as np
import math

def run_metric_model_vari_solo(df_data):

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
        0: 0.8,
        1: 0.2,
        2: 0.2,
        3: 0.2,
        4: 0.2,
        5: 0.2
    }

    #Transportation lead time data: 
    T_0 = 0.3      # depot repair time
    T_j = 0.01     # base repair time
    O_j = {
        0: T_0,
        1: 0.01,
        2: 0.01,
        3: 0.01,
        4: 0.01,
        5: 0.01
    } 

    # Lead time variance (YOU must calibrate these)
    Var_O_j = {
        0: 0,
        1: 0,
        2: 0,
        3: 0,
        4: 0,
        5: 0
    }

    r_j = {
        1: 0.2,
        2: 0.2,
        3: 0.2,
        4: 0.2,
        5: 0.2
    }

    variance_factor = 1

    Var_O_j = {j: variance_factor * value for j, value in Var_O_j.items()}
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
    L = [0, 1, 2, 3, 4, 5]

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

    for i in P:
        lambda_ij[(i, 0)] = sum(
            (1 - r_j[j]) * lambda_ij[(i, j)]
            for j in L
            if j != 0
        )
    # ---------------------------------------------------
    # REPAIR FRACTION FOR NUMERICAL TESTING
    # ---------------------------------------------------
    # q_i = fraction of demand at the bases that is supplied through the depot.
    # In your real situation, no repair fractions are used, so q_i = 1.
    # For numerical testing, you can change this value.

    q_i = {}

    for i in P:
        q_i[i] = 1.0
        
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


#-------------------------------------------------------------------
#5. INITIALIZE INVENTORY LEVELS + CALCULATE BACKORDERS FOR DEPOT
#-------------------------------------------------------------------

#Initializing the inventory levels and setting them to zero
    
    #making the stock level parameter
    s_ij = {}
    
    for i in P:

        for j in L:

            s_ij[(i, j)] = 0

    # ---------------------------------------------------
    # VALIDATION STOCK LEVELS
    # ---------------------------------------------------

    for i in P:

        s_ij[(i,0)] = 20   # depot stock

        for j in L:

            if j == 0:
                continue

            s_ij[(i,j)] = 5   # base stock

    
#calculate the Expected Back Orders with zero stock
    
    #making the mu parameter which represents the demand during lead time
    EBO_i0 = {}

    def ebo_exact(mu, s):

        if s == 0:
            return mu

        term1 = mu * (1 - poisson.cdf(s - 1, mu))
        term2 = s * (1 - poisson.cdf(s, mu))

        return max(0.0, term1 - term2)


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
        var_ij = {}
        EBO_i0_dynamic = {}
        V_BO_i0 = {}

        for i in P:

            # --------------------------
            # DEPOT PIPELINE
            # --------------------------
            mu_ij[(i, 0)] = lambda_ij[(i, 0)] * O_j[0]

            var_ij[(i, 0)] = demand_var_during_leadtime(
                lambda_ij[(i, 0)],
                lambda_ij[(i, 0)],
                O_j[0],
                Var_O_j[0]
            )
            
            EBO_i0_dynamic[i] = ebo_vari_metric(
                mu_ij[(i, 0)],
                var_ij[(i, 0)],
                s_ij[(i, 0)]
            )
            
            V_BO_i0[i] = var_bo(
                mu_ij[(i, 0)],
                s_ij[(i, 0)]
            )

            V_BO_s0 = V_BO_i0[i]

            for j in L:

                if j == 0:
                    continue

                if lambda_ij[(i, 0)] == 0:
                    mu_ij[(i, j)] = 0
                    var_ij[(i, j)] = 0
                    continue

                # --------------------------
                # REGULAR LEAD TIME
                # --------------------------

                f_depot_j = ((1 - r_j[j]) * lambda_ij[(i, j)]) / lambda_ij[(i, 0)]

                mu_ij[(i, j)] = (
                    lambda_ij[(i, j)] * r_j[j] * T_j
                    + lambda_ij[(i, j)] * (1 - r_j[j]) * O_j[j]
                    + f_depot_j * EBO_i0_dynamic[i]
                )


                var_ij[(i, j)] = (
                    lambda_ij[(i, j)] * r_j[j] * T_j
                    + lambda_ij[(i, j)] * (1 - r_j[j]) * O_j[j]
                    + f_depot_j * (1 - f_depot_j) * EBO_i0_dynamic[i]
                    + (f_depot_j ** 2) * V_BO_s0
                )

        return mu_ij, var_ij, V_BO_i0

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


    mu_ij, var_ij, V_BO_i0 = compute_mu_ij()
    EBO_ij = compute_EBO(mu_ij, var_ij)

    for i in P:
        EBO_i0[i] = EBO_ij[(i, 0)]


    #-------------------------------------------------------------------
#7. CALCULATE EXPECTED BACKORDERS REDUCTION
#-------------------------------------------------------------------
    DeltaEBO = {}

    #making a simple function that calculates the reduction
    def ebo_reduction(mu, var, s):

        current = ebo_vari_metric(mu, var, s)
        future = ebo_vari_metric(mu, var, s + 1)

        return max(0.0, current - future)

    for i in P:
        for j in L:
            DeltaEBO[(i, j)] = ebo_reduction(
                mu_ij[(i, j)],
                var_ij[(i, j)],
                s_ij[(i, j)]
            )
#-------------------------------------------------------------------
#9. OPTIMIZATION PROCEDURE
#-------------------------------------------------------------------

#Calculating the optimization of spare parts til budget is exhausted

    #define parameters for optimization
    
    Efficiency = {}
    TotalCost = 0

    #WHILE budget not exhausted:
    #if False:

        #mu_ij, var_ij = compute_mu_ij()
        #EBO_ij = compute_EBO(mu_ij, var_ij)
        
        #best_i = None
        #best_j = None
        #best_eff = -1
        
        #looping over all the distinct parts i
        #for i in P:

            #looping over all the bases j
            #for j in L:            

                #calculate the ebo reduction
                #DeltaEBO[(i, j)] = ebo_reduction(mu_ij[(i, j)], var_ij[(i, j)], s_ij[(i, j)])

                #calculate the efficiency:
                #Efficiency[(i, j)] = DeltaEBO[(i, j)] / cost_part[i]

                #if Efficiency[(i, j)] > best_eff:

                    #best_eff = Efficiency[(i, j)]
                    #best_i = i
                    #best_j = j

        #stop if the costs goes over the budget
        #if TotalCost + cost_part[best_i] > C:
            #break

        #Allocate one stock unit to the best place
        #s_ij[(best_i, best_j)] += 1

        #update the totalcost with the part added
        #TotalCost += cost_part[best_i]

        #mu_ij, var_ij = compute_mu_ij()
        #EBO_ij = compute_EBO(mu_ij, var_ij)

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
        "var_ij": var_ij,
        "V_BO_i0": V_BO_i0,
    }
    

    return results