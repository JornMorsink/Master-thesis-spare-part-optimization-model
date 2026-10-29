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
    C = 454000
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
        1: 0.2009,          #this is virtual hub in Rijssen
        2: 0.7991,          #this is VUSA
        3: 0.0,          #this is the regional hub in UK
        4: 0.0          #this is the regional hub in UAE
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
    #Initializing the inventory levels and setting them to zero
    depot_stock = [
        17, 21, 2, 2, 9, 4, 17, 37, 55, 26,
        10, 14, 76, 22, 4, 11, 12, 19, 5, 55,
        53, 50, 60, 83, 65, 1, 4, 12, 4, 54,
        18, 24, 10, 27, 92, 101, 1, 19, 12, 18,
        83, 45, 32, 22, 127, 62, 76, 56, 5, 43,
        26, 5, 6, 12, 5, 9, 81, 10, 73, 6, 4, 1
    ]
    base2_stock = [
        3, 3, 2, 1, 20, 12, 0, 3, 7, 3,
        0, 1, 11, 8, 12, 0, 4, 0, 2, 36,
        65, 33, 60, 40, 7, 4, 8, 5, 8, 8,
        17, 8, 4, 8, 79, 6, 33, 9, 9, 9,
        7, 3, 2, 7, 5, 10, 9, 7, 5, 2,
        3, 9, 5, 17, 7, 4, 28, 12, 7, 5,
        4, 1
    ]
    s_ij = {}


    for item_index, i in enumerate(P):
        for j in L:
            s_ij[(i, j)] = starting_values[item_index][j]

    #for i in P:
    #    for j in L:
    #        s_ij[(i, j)] = 0

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
                depot_fill_rate = poisson.cdf(s_ij[(i, 0)] - 1, mu_ij[(i, 0)])
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
                base_stockout_prob = 1 - poisson.cdf(s_ij[(i, j)] - 1, mu_regular)
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
#7. CALCULATE Waiting time REDUCTION
#-------------------------------------------------------------------
    # Waiting time per demand.
    def waiting_time_per_demand(i, j, theta, ebo):
        demand = lambda_ij[(i, j)]
        if demand <= 0:
            return 0.0
        return theta[(i, j)] * E_j[j] + ebo[(i, j)] / demand
    def evaluate_item_waiting_time(i, stock_levels):
        # Recalculate depot availability and all dependent base pipelines.
        depot_mu = lambda_ij[(i, 0)] * O_i0[i]
        depot_ebo = ebo_exact(depot_mu, stock_levels[0])
        depot_rate = lambda_ij[(i, 0)]
        if depot_rate <= 0:
            return {j: 0.0 for j in L if j != 0}
        depot_fill = poisson.cdf(stock_levels[0] - 1, depot_mu)
        regular_lead = {j: O_j[j] + depot_ebo / depot_rate for j in L if j != 0}
        waiting = {}
        for j in L:
            if j == 0:
                continue
            demand = lambda_ij[(i, j)]
            if demand <= 0:
                waiting[j] = 0.0
                continue
            stockout = 1 - poisson.cdf(stock_levels[j] - 1, demand * regular_lead[j])
            theta = stockout * depot_fill
            mu = demand * ((1 - theta) * regular_lead[j] + theta * E_j[j])
            ebo = ebo_exact(mu, stock_levels[j])
            waiting[j] = theta * E_j[j] + ebo / demand
        return waiting
#-------------------------------------------------------------------
#9. OPTIMIZATION PROCEDURE
#-------------------------------------------------------------------
#Calculating the optimization of spare parts til budget is exhausted
    #define parameters for optimization
    DeltaWaitingTime = {}
    Efficiency = {}
    # Calculate inventory investment already used by the starting solution
    TotalCost = sum(
        s_ij[(i, j)] * cost_part[i]
        for i in P
        for j in L
    )
    # Cache candidate gains: only the modified item needs updating.
    # heap ordering reproduces the original scan's tie-breaking (item, location).
    import heapq
    heap = []
    versions = {i: 0 for i in P}
    item_order = {i: n for n, i in enumerate(P)}
    def update_item_candidates(i):
        versions[i] += 1
        version = versions[i]
        current_stock = {j: s_ij[(i, j)] for j in L}
        current_wait = evaluate_item_waiting_time(i, current_stock)
        urgency_weight = group_weight(group_part[i])
        for j in L:
            candidate_stock = current_stock.copy()
            candidate_stock[j] += 1
            candidate_wait = evaluate_item_waiting_time(i, candidate_stock)
            # Marginal reduction in TOTAL demand-weighted waiting time.
            # A depot increment affects all bases; a base increment affects only that base.
            if j == 0:
                reduction = sum(
                    lambda_ij[(i, k)] * (current_wait[k] - candidate_wait[k])
                    for k in L if k != 0
                )
            else:
                reduction = lambda_ij[(i, j)] * (current_wait[j] - candidate_wait[j])
            DeltaWaitingTime[(i, j)] = reduction
            efficiency = (reduction * urgency_weight / cost_part[i]) if cost_part[i] > 0 else 0.0
            Efficiency[(i, j)] = efficiency
            if reduction > 1e-12 and efficiency > -1:
                heapq.heappush(heap, (-efficiency, item_order[i], j, version, i))
    for i in P:
        update_item_candidates(i)
    while heap:
        negative_eff, _, best_j, version, best_i = heapq.heappop(heap)
        if version != versions[best_i]:
            continue
        if TotalCost + cost_part[best_i] > C:
            continue
        s_ij[(best_i, best_j)] += 1
        TotalCost += cost_part[best_i]
        update_item_candidates(best_i)
    # Compute final values once, rather than after every inventory increment.
    mu_ij, theta_ij = compute_mu_ij()
    EBO_ij = compute_EBO(mu_ij)
    # Keep the depot-only EBO output consistent with the FINAL optimized stock.
    EBO_i0 = {i: EBO_ij[(i, 0)] for i in P}
# ---------------------------------------------------
# FILL RATE (FINAL STATE)
# ---------------------------------------------------
    # Item-location fill rates from the final optimized pipeline and stock levels.
    # P(Poisson pipeline demand <= stock - 1) is the local immediate fill rate.
    FillRate_ij = {}
    for i in P:
        for j in L:
            FillRate_ij[(i, j)] = float(poisson.cdf(s_ij[(i, j)] - 1, mu_ij[(i, j)])) if lambda_ij[(i, j)] > 0 else None
    # Demand-weighted fill rate: fraction of demand fulfilled directly from local stock.
    AverageFillRate_j = {}
    for j in L:
        total_demand_j = sum(lambda_ij[(i, j)] for i in P)
        AverageFillRate_j[j] = (
            sum(lambda_ij[(i, j)] * FillRate_ij[(i, j)] for i in P if FillRate_ij[(i, j)] is not None) / total_demand_j
            if total_demand_j > 0 else None
        )
    total_base_demand = sum(lambda_ij[(i, j)] for i in P for j in L if j != 0)
    TotalAverageFillRate = (
        sum(lambda_ij[(i, j)] * FillRate_ij[(i, j)] for i in P for j in L if j != 0 and FillRate_ij[(i, j)] is not None) / total_base_demand
        if total_base_demand > 0 else None
    )
    WaitingTime_ij = {(i, j): waiting_time_per_demand(i, j, theta_ij, EBO_ij)
                      for i in P for j in L if j != 0}
    TotalWeightedWaitingTime = sum(lambda_ij[(i, j)] * WaitingTime_ij[(i, j)]
                                   for i in P for j in L if j != 0)
    TotalBaseDemand = sum(lambda_ij[(i, j)] for i in P for j in L if j != 0)
    AverageWaitingTime = TotalWeightedWaitingTime / TotalBaseDemand if TotalBaseDemand > 0 else 0.0
    # Detailed demand-weighted waiting time (years of waiting per year of demand).
    WeightedWaitingTime_ij = {
        (i, j): lambda_ij[(i, j)] * WaitingTime_ij[(i, j)]
        for i in P for j in L if j != 0
    }
    TotalWeightedWaitingTime_j = {
        j: sum(WeightedWaitingTime_ij[(i, j)] for i in P)
        for j in L if j != 0
    }
    AverageWaitingTime_j = {
        j: (TotalWeightedWaitingTime_j[j] / sum(lambda_ij[(i, j)] for i in P)
            if sum(lambda_ij[(i, j)] for i in P) > 0 else 0.0)
        for j in L if j != 0
    }
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
#10. CALCULATING TOTAL EBO
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
        "WaitingTime_reduction": DeltaWaitingTime,  # Now demand-weighted marginal reduction
        "WeightedWaitingTime_reduction": DeltaWaitingTime,
        "WeightedWaitingTime_ij": WeightedWaitingTime_ij,
        "TotalWeightedWaitingTime_j": TotalWeightedWaitingTime_j,
        "AverageWaitingTime_j": AverageWaitingTime_j,
        "WaitingTime_ij": WaitingTime_ij,
        "TotalWeightedWaitingTime": TotalWeightedWaitingTime,
        "AverageWaitingTime": AverageWaitingTime,
        "AverageWaitingTime_days": AverageWaitingTime * 365,
        "total": TotalEBO,
        "TotalCost": TotalCost,
        "Z_i": Z_i,
        "N_j": N_j,
        "SystemAvailability_j": SystemAvailability_j,
        "FillRate_ij": FillRate_ij,
        "AverageFillRate_j": AverageFillRate_j,
        "TotalAverageFillRate": TotalAverageFillRate,
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


