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
    C = 86000
    #holding cost rate
    h = 0.2 


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
        0: 0.0038,
        1: 0.0027,          #this is virtual hub in Rijssen
        2: 0.1346,          #this is VUSA
        3: 0.0110,          #this is the regional hub in UK
        4: 0.1346           #this is the regional hub in UAE
    }

#Read emergency shipment data:
    #    - emergency shipment cost cemj
    #    - emergency shipment fraction θij

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
            lambda_ij[(i, j)] = math.ceil(lambda_part[i] * f_j[j])


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

#calculating the pipeline for the bases j

    #making the parameter for the pipeline
    mu_ij = {}

    #looping over all the disinct parts i
    for i in P:

        #looping over all the bases j
        for j in L:

            #pipeline for the depot is equal to demand times lead time
            if j == 0:

                mu_ij[(i, j)] = mu_i0[i]
            
            #pipeline for the bases is different calculation
            else: 

                #if demand is zero, pipeline is also zero
                if lambda_ij[(i, 0)] == 0:
                    
                    mu_ij[(i, j)] = 0

                #if the demand is not zero, there is possibility of pipeline stock
                else:

                    mu_ij[(i, j)] = (lambda_ij[(i, j)] * O_j[j]) + ((lambda_ij[(i, j)] * EBO_i0[i]) / lambda_ij[(i, 0)])

#calculating the expected backorders for the bases j with the pipeline

    #making the parameter for the bases
    EBO_ij = {}

    #looping over all the disinct parts i
    for i in P:

        #looping over all the bases j
        for j in L:

            if j == 0:

                EBO_ij[(i, j)] = EBO_i0[i]

            else:

                #this is that
                EBO_ij[(i, j)] = ebo_exact(mu_ij[(i, j)], s_ij[(i, j)])


#-------------------------------------------------------------------
#7. CALCULATE EXPECTED BACKORDERS REDUCTION
#-------------------------------------------------------------------

#calculating the expected backorders reductions
    
    #making a simple function that calculates the reduction
    def ebo_reduction(mu, s):
    
        return ebo_exact(mu, s) - ebo_exact(mu, s + 1)

#-------------------------------------------------------------------
#8. CONSTRAINTS
#-------------------------------------------------------------------

#9.1 Non-negativity and integrality

    #looping over all the disinct parts i
    for i in P:

        #looping over all the bases j
        for j in L:

            # ensure integer
            s_ij[(i, j)] = int(s_ij[(i, j)])

            # ensure non-negative
            s_ij[(i, j)] = max(0, s_ij[(i, j)])


#9.2 Budget constraint

    #setting totalcost to zero
    TotalCost = 0

    #looping over all the distinct parts i
    for i in P:

        #looping over all the bases j
        for j in L:

            TotalCost += s_ij[(i, j)] * cost_part[i]


#-------------------------------------------------------------------
#9. OPTIMIZATION PROCEDURE
#-------------------------------------------------------------------

#Calculating the optimization of spare parts til budget is exhausted

    #define parameters for optimization
    DeltaEBO = {}
    Efficiency = {}

    #WHILE budget not exhausted:
    while True:

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


        SupplyAvailability[i] = 1- total_ebo

#-------------------------------------------------------------------
#10. OBJECTIVE FUNCTION
#-------------------------------------------------------------------

    TotalEBO = 0

    for i in P:

        for j in L:

            TotalEBO += EBO_ij[(i, j)]


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
    }


#-------------------------------------------------------------------
#11. EMERGENCY SHIPMENT LOGIC
#-------------------------------------------------------------------

#FOR each item i:
#    FOR each location j:

#        IF stockout occurs THEN

#            Trigger emergency shipment

#            Apply:
#                emergency shipment cost cemj

#           Reduce machine downtime

#        END IF

#    END FOR
#END FOR

#-------------------------------------------------------------------
#12. CRITICALITY WEIGHTING
#-------------------------------------------------------------------

#FOR each item i:

#    Adjust objective contribution:

#        WeightedEBO =
#            EBOij × wci

#    Higher criticality items receive:
#        higher optimization priority

#END FOR

#-------------------------------------------------------------------
#13. OUTPUT RESULTS
#-------------------------------------------------------------------

#Generate optimal stock allocation:
#    sij*

#Generate expected backorders:
#    EBOij

#Generate total inventory cost

#Generate service level indicators

#Generate emergency shipment statistics

#Generate utilization metrics

#-------------------------------------------------------------------
#14. EXPORT RESULTS
#-------------------------------------------------------------------

#Export results to:
#    Excel
#    CSV
#    Dashboard tables

#Generate visualizations:
#    - stock per hub
#    - expected backorders
#    - inventory investment
#    - criticality heatmaps

    return results