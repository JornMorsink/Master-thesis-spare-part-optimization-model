from scipy.stats import poisson

import pandas as pd



def run_metric_model_final(df_data):

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

        4: 0.0342          #this is the regional hub in UAE

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

        2: 99.45, #this is VUSA

        3: 59.09, #this is the regional hub in UK

        4: 223.68  #this is the regional hub in UAE 

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

    # Number of occurrences of each spare part in one machine.
    # The Excel column must be named Z_i.
    if "Z_i" not in part_df.columns:
        raise ValueError("Missing required column 'Z_i' in 'Total inventory costs'.")
    z_values = pd.to_numeric(part_df["Z_i"], errors="coerce")
    if z_values.isna().any() or (z_values <= 0).any() or (z_values % 1 != 0).any():
        raise ValueError("All Z_i values must be positive whole numbers.")
    Z_i = dict(zip(P, z_values.astype(int)))

    # Installed machines supported by each base (NOT the central depot).
    # Check these counts against the installed-base data before using results.
    N_j = {1: 26, 2: 187, 3: 13, 4: 8}


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

            return 1.15  # 15% more important

        elif group == 4:

            return 1.00   # normal importance

        else:

            return 1.00

    # ---------------------------------------------------


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

    # ---------------------------------------------------

    # INITIAL INVENTORY LEVELS

    # ---------------------------------------------------

    # Starting values obtained from the convexity analysis.

    # Location indices:

    # 0 = VSM

    # 1 = Virtual hub (NL)

    # 2 = VUSA

    # 3 = UK hub

    # 4 = UAE hub

    starting_values = [

        [0, 0, 0,  0, 0],   # Item 1

        [0, 0, 1,  0, 0],   # Item 2

        [0, 0, 0,  0, 0],   # Item 3

        [0, 0, 0,  0, 0],   # Item 4

        [0, 0, 0,  0, 0],   # Item 5

        [0, 0, 0,  0, 0],   # Item 6

        [0, 0, 15, 0, 0],   # Item 7

        [0, 0, 0,  0, 0],   # Item 8

        [0, 0, 0,  0, 0],   # Item 9

        [0, 0, 5,  0, 0],   # Item 10

        [0, 0, 0,  0, 0],   # Item 11

        [0, 0, 6,  0, 0],   # Item 12

        [0, 0, 1,  0, 0],   # Item 13

        [0, 0, 6,  0, 0],   # Item 14

        [0, 0, 0,  0, 0],   # Item 15

        [0, 0, 24, 0, 0],   # Item 16

        [0, 0, 0,  0, 0],   # Item 17

        [0, 0, 0,  0, 0],   # Item 18

        [0, 0, 0,  0, 0],   # Item 19

        [0, 0, 0,  0, 0],   # Item 20

        [0, 0, 26, 0, 0],   # Item 21

        [0, 0, 22, 0, 0],   # Item 22

        [0, 0, 17, 0, 0],   # Item 23

        [0, 0, 10, 0, 0],   # Item 24

        [0, 0, 10, 0, 0],   # Item 25

        [0, 0, 9,  0, 0],   # Item 26

        [0, 0, 9,  0, 0],   # Item 27

        [0, 0, 9,  0, 0],   # Item 28

        [0, 0, 9,  0, 0],   # Item 29

        [0, 0, 8,  0, 0],   # Item 30

        [0, 0, 7,  0, 0],   # Item 31

        [0, 0, 6,  0, 0],   # Item 32

        [0, 0, 3,  0, 0],   # Item 33

        [0, 0, 2,  0, 0],   # Item 34

        [0, 0, 0,  0, 0],   # Item 35

        [0, 1, 0,  0, 2],   # Item 36

        [0, 0, 0,  0, 0],   # Item 37

        [0, 0, 0,  0, 0],   # Item 38

        [0, 0, 1,  0, 0],   # Item 39

        [0, 0, 1,  0, 0],   # Item 40

        [0, 0, 1,  0, 0],   # Item 41

        [0, 0, 0,  0, 0],   # Item 42

        [0, 0, 0,  0, 0],   # Item 43

        [0, 0, 0,  0, 0],   # Item 44

        [0, 0, 0,  0, 0],   # Item 45

        [0, 0, 4,  0, 0],   # Item 46

        [0, 0, 4,  0, 0],   # Item 47

        [0, 0, 6,  0, 0],   # Item 48

        [0, 0, 11, 0, 0],   # Item 49

        [0, 0, 13, 0, 0],   # Item 50

        [0, 0, 5,  0, 0],   # Item 51

        [0, 0, 4,  0, 0],   # Item 52

        [0, 0, 1,  0, 0],   # Item 53

        [0, 0, 3,  0, 0],   # Item 54

        [0, 0, 3,  0, 0],   # Item 55

        [0, 0, 3,  0, 0],   # Item 56

        [0, 0, 2,  0, 0],   # Item 57

        [0, 0, 2,  0, 0],   # Item 58

        [0, 0, 2,  0, 0],   # Item 59

        [0, 0, 2,  0, 0],   # Item 60

        [0, 0, 2,  0, 0],   # Item 61

        [0, 0, 1,  0, 0],   # Item 62

    ]

    # Check that the number of starting-value rows matches

    # the number of spare parts in the input file.

    if len(starting_values) != len(P):

        raise ValueError(

            f"Expected {len(starting_values)} items from starting values, "

            f"but found {len(P)} items in the input data."

        )

    # Initialize inventory levels

    s_ij = {}

    for item_index, i in enumerate(P):

        for j in L:

            s_ij[(i, j)] = starting_values[item_index][j]

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



#-------------------------------------------------------------------

#6. CALCULATE PIPELINE STOCK + BACKORDERS FOR BASES

#-------------------------------------------------------------------

    # Calculate Poisson pipeline means and emergency shipment fractions.
    def compute_mu_ij():
        mu_ij = {}
        theta_ij = {}

        for i in P:
            mu_ij[(i, 0)] = lambda_ij[(i, 0)] * O_i0[i]
            depot_ebo = ebo_exact(mu_ij[(i, 0)], s_ij[(i, 0)])

            if lambda_ij[(i, 0)] > 0:
                depot_fill_rate = max(0, 1 - depot_ebo / lambda_ij[(i, 0)])
            else:
                depot_fill_rate = 0

            for j in L:
                if j == 0:
                    continue

                if lambda_ij[(i, 0)] == 0:
                    mu_ij[(i, j)] = 0
                    theta_ij[(i, j)] = 0
                    continue

                # Regular replenishment lead time includes expected depot waiting.
                waiting_time = depot_ebo / lambda_ij[(i, 0)]
                regular_lead_time = O_j[j] + waiting_time

                # Base stockout probability and emergency fraction.
                mu_regular = lambda_ij[(i, j)] * regular_lead_time
                base_stockout_prob = 1 - poisson.cdf(s_ij[(i, j)], mu_regular)
                theta_ij[(i, j)] = base_stockout_prob * depot_fill_rate

                # Split demand into regular and emergency pipelines.
                lambda_em = theta_ij[(i, j)] * lambda_ij[(i, j)]
                lambda_reg = (1 - theta_ij[(i, j)]) * lambda_ij[(i, j)]
                mu_em = lambda_em * E_j[j]
                mu_reg = lambda_reg * regular_lead_time
                mu_ij[(i, j)] = mu_em + mu_reg

        return mu_ij, theta_ij

    # Exact Poisson EBO for depot and bases.
    def compute_EBO(mu_ij):
        EBO_ij = {}
        for i in P:
            for j in L:
                EBO_ij[(i, j)] = ebo_exact(mu_ij[(i, j)], s_ij[(i, j)])
        return EBO_ij

#7. CALCULATE EXPECTED BACKORDERS REDUCTION

#-------------------------------------------------------------------

    #making a simple function that calculates the reduction

    def ebo_reduction(mu, s):
        current = ebo_exact(mu, s)
        future = ebo_exact(mu, s + 1)
        return max(0.0, current - future)

#9. OPTIMIZATION PROCEDURE

#-------------------------------------------------------------------

#Calculating the optimization of spare parts til budget is exhausted

    #define parameters for optimization

    DeltaEBO = {}

    Efficiency = {}

    # Calculate inventory investment already used by the starting solution

    TotalCost = sum(

        s_ij[(i, j)] * cost_part[i]

        for i in P

        for j in L

    )

    print(f"Starting inventory cost: €{TotalCost:,.2f}")

    print(f"Remaining optimization budget: €{C - TotalCost:,.2f}")

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

                #normalized_cost = math.log1p(cost_part[i])

                urgency_weight = group_weight(group_part[i])

                if j != 0:

                    emergency_cost_penalty = (

                        theta_ij[(i, j)]

                        * c_em[j]

                    )

                else:

                    emergency_cost_penalty = 0

                Efficiency[(i, j)] = (

                    (DeltaEBO[(i, j)] 

                    * urgency_weight)

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

    # Sherbrooke METRIC system availability by base.
    # A_j = product_i (1 - EBO_ij / (N_j * Z_i)) ** Z_i
    SystemAvailability_j = {}
    for j, n_machines in N_j.items():
        availability = 1.0
        for i in P:
            component_availability = max(
                0.0, 1.0 - EBO_ij[(i, j)] / (n_machines * Z_i[i])
            )
            availability *= component_availability ** Z_i[i]
        SystemAvailability_j[j] = availability

    TotalSystemAvailability = (
        sum(N_j[j] * SystemAvailability_j[j] for j in N_j)
        / sum(N_j.values())
    )

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

        "SupplyAvailability": SupplyAvailability,  # legacy item-level metric
        "Z_i": Z_i,
        "N_j": N_j,
        "SystemAvailability_j": SystemAvailability_j,
        "TotalSystemAvailability": TotalSystemAvailability,

        "theta_ij": theta_ij,

        "emergencycost": TotalEmergencyCost,


        "TotalEBO_bases": TotalEBO_bases,

        "emergency": avg_theta,

        "group_part": group_part,

        "weight_part": {

            i: group_weight(group_part[i])

            for i in P

        },

    }

    return results