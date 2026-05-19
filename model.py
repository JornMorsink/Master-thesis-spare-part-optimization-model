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
    C = 100000 
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
#5. INITIALIZE INVENTORY LEVELS
#-------------------------------------------------------------------

#Initializing the inventory levels and setting them to zero
    
    #making the stock level parameter
    s_ij = {}
    
    #looping over all the parts and locations that exist
    for (i, j) in lambda_ij.keys():

        #setting stock to zero
        s_ij[i, j] = 0


#Initialize costs and EBO:
    
    #setting the total inventory costs equal to the budget maximum
    Total_inventory_Cost = C
    
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

        return term1 - term2


    for i in P:
        EBO_i0[i] = ebo_exact(mu_i0[i], 0)
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
        "EBO_i0": EBO_i0
    }
#-------------------------------------------------------------------
#6. CALCULATE PIPELINE STOCK
#-------------------------------------------------------------------

#FOR each item i:
#    FOR each location j:

#        Calculate pipeline mean:
#            μij = λij × Oj

#        Estimate pipeline quantity:
#            Xj ~ Poisson(μij)

#    END FOR
#END FOR

#-------------------------------------------------------------------
#7. CALCULATE EXPECTED BACKORDERS
#-------------------------------------------------------------------

#FOR each item i:
#    FOR each location j:

#        Compute expected backorders:

#        EBOij = Expected value of:
#                 MAX(Xj - sij, 0)

#        Calculate regular backorders:
#            EBOregij

#        Calculate emergency backorders:
#            EBOemij

#        Total backorders:
#            EBOtotij = EBOregij + EBOemij

#    END FOR
#END FOR

#-------------------------------------------------------------------
#8. OBJECTIVE FUNCTION
#-------------------------------------------------------------------

#Objective:
#    Minimize total expected backorders

#MINIMIZE:

#    TotalEBO =
#    SUM over i
#        SUM over j
#            EBOij(sij)

#Subject to:
#    inventory constraints
#    budget constraints
#    integrality constraints

#-------------------------------------------------------------------
#9. CONSTRAINTS
#-------------------------------------------------------------------

#9.1 Non-negativity and integrality

#FOR all i,j:

#    sij >= 0

#    sij must be integer

#END FOR

#--------------------------------------------------

#9.2 Budget constraint

#TotalCost =
#SUM over i:
#    ci ×
#    SUM over j:
#        sij

#Constraint:
#    TotalCost <= C

#--------------------------------------------------

#9.3 Backorder consistency

#FOR all i,j:

#    EBOtotij =
#        EBOregij +
#        EBOemij

#END FOR

#--------------------------------------------------

#9.4 Depot demand consistency

#FOR each item i:

#    mi0 =
#    SUM over regional hubs j:
#        mij

#END FOR

#-------------------------------------------------------------------
#10. OPTIMIZATION PROCEDURE
#-------------------------------------------------------------------

#WHILE budget not exhausted:

#    FOR each item i:
#        FOR each location j:

#            Temporarily increase stock:
#                sij = sij + 1

#            Recalculate:
#                EBOij_new

#            Compute marginal improvement:

#                DeltaEBO =
#                    EBO_old - EBO_new

#            Compute marginal efficiency:

#                Efficiency =
#                    DeltaEBO / ci

#            Store efficiency value

#            Restore previous stock level

#        END FOR
#    END FOR

#    Select item-location pair with:
#        highest marginal efficiency

#    Permanently allocate one spare part

#    Update:
#        stock levels
#        total cost
#        expected backorders

#END WHILE

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