import pulp as pl
import glob
from itertools import product
import random


def generate_random_capacities(num_periods, min_capacity, max_capacity):
    """
    Generate random capacities for each period.

    :param num_periods: Number of periods
    :param min_capacity: Minimum capacity value
    :param max_capacity: Maximum capacity value
    :return: Dictionary with random capacities for each period
    """
    return {t: random.randint(min_capacity, max_capacity) for t in range(1, num_periods + 1)}


class FileData:
    def __init__(self, tasks_count, durations, permutation, precedences, uncertain_tasks):
        self.tasks_count = tasks_count
        self.durations = durations
        self.permutation = permutation
        self.precedences = precedences
        self.uncertain_tasks = uncertain_tasks  # Ajout de la liste des tâches incertaines

# Charger les données des fichiers
def load_data(directory_path):
    file_data_list = []
    for file_path in glob.glob(directory_path + "*.IN2"):
        with open(file_path, "r") as file: 
            lines = file.readlines()
            tasks_count = int(lines[0].strip())
            durations = [int(line.strip().split()[0]) for line in lines[2:2+tasks_count]]
            permutation = list(map(int, lines[2+tasks_count].strip().split()))
            precedences = [tuple(map(int, pair.strip().split(','))) for pair in lines[3+tasks_count:] if pair.strip() != "-1,-1"]
            uncertain_tasks = set(permutation[:5]) # Supposons que les tâches incertaines sont celles dans 'permutation'
            file_data_list.append(FileData(tasks_count, durations, permutation, precedences, uncertain_tasks))
    return file_data_list

# Créer et résoudre le problème d'optimisation pour chaque instance de FileData
def solve_problems(file_data_list):
    results = []
    for file_data in file_data_list:
        # Initialisation du problème
        prob = pl.LpProblem("ReconfigurableAssemblyLineBalancing", pl.LpMinimize)

        # Données
        N = range(1, file_data.tasks_count + 1)
        U = range(1, 6)  # Supposition de 5 workstations
        T = range(1, 6)  # Période (par exemple, une semaine)
        c = generate_random_capacities(len(T), 30, 50)  # Generate random capacities between 10 and 30
        print("Capacities for each period:", c)
        R = 0.5  # Taux de robustesse de la configuration

        # Variables de décision
        x = {(i, k): pl.LpVariable(f"x_{i}_{k}", cat='Binary') for i, k in product(N, U)}
        yp = {(k, t): pl.LpVariable(f"yp_{k}_{t}", lowBound=0, cat=pl.LpInteger) for k, t in product(U, T)}
        yr = {(k, t): pl.LpVariable(f"yr_{k}_{t}", lowBound=0, cat=pl.LpInteger) for k, t in product(U, T)}

        # Objectif
        prob += pl.lpSum(yp[k, t] + yr[k, t] for k, t in product(U, T)), "TotalResourceUsage"

        # Contraintes
        # 1. Chaque tâche doit être affectée à une seule workstation
        for i in N:
            prob += pl.lpSum(x[i, k] for k in U) == 1, f"TaskAssignment_{i}"
        # Contrainte: Chaque workstation doit avoir au moins une tâche assignée
        for k in U:
            prob += pl.lpSum(x[i, k] for i in N) >= 1, f"AtLeastOneTask_{k}"

        # 2. Contrainte de précédence
        for (i, j) in file_data.precedences:
            prob += pl.lpSum((k * x[i, k]) for k in U) <= pl.lpSum((k * x[j, k]) for k in U), f"Precedence_{i}_{j}"

        # 3. Contrainte de charge quotidienne de productivité
        for t in T:
            for k in U:
                prob += pl.lpSum((file_data.durations[i - 1] * x[i, k]) for i in N) <= (1 + yp[k, t]) * c[t], f"DailyLoad_{t}_{k}"

        # 4. Contrainte de charge quotidienne de robustesse
        for t in T:
            for k in U:
                prob += pl.lpSum((file_data.durations[i-1] * x[i, k]) for i in N if i not in file_data.uncertain_tasks) + (1+R) * pl.lpSum((file_data.durations[j-1] * x[j, k]) for j in file_data.uncertain_tasks) <= (1 + yp[k, t] + yr[k, t]) * c[t], f"RobustDailyLoad_{t}_{k}"

        # Résolution
        prob.solve(pl.GUROBI())

        # Collecter les résultats
        assignments = {k: [] for k in U}
        task_times = {k: [] for k in U}
        total_time_per_station = {k: 0 for k in U}

        for i in N:
            for k in U:
                if pl.value(x[i, k]) == 1:
                    assignments[k].append(i)
                    task_times[k].append((i, file_data.durations[i - 1]))
                    total_time_per_station[k] += file_data.durations[i - 1]

        results.append({
            'status': pl.LpStatus[prob.status],
            'objective': pl.value(prob.objective),
            'assignments': assignments,
            'task_times': task_times,
            'total_time_per_station': total_time_per_station,
            'production_resources': {k: {t: pl.value(yp[k, t]) for t in T} for k in U},
            'robustness_resources': {k: {t: pl.value(yr[k, t]) for t in T} for k in U}
        })

    return results

 # Chemin vers le répertoire contenant les fichiers
directory_path = "./test/"
data_list = load_data(directory_path)
results = solve_problems(data_list)

for result in results:
    print("Statut de résolution:", result['status'])
    print("Valeur de la fonction objectif (TotalResourceUsage):", result['objective'])
    print("Assignments per Station and Task Times:")
    for k in result['assignments']:
        print(f"Station {k}:")
        for task_id, time in result['task_times'][k]:
            print(f"  Task {task_id} - Duration: {time}")
        print(f"Total Time at Station {k}: {result['total_time_per_station'][k]}")
    print("Production resources:", result['production_resources'])
    print("Robustness resources:", result['robustness_resources'])
