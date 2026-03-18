import numpy as np


def _mutation(x0, smallstep, bigstep, smallp, bigp, rng):
    result = x0.copy()
    for i in range(x0.size):
        p = rng.random()
        if p < bigp:
            result[i] += rng.integers(-bigstep, bigstep + 1)
        elif p < bigp + smallp:
            result[i] += rng.integers(-smallstep, smallstep + 1)
    return result


def _crossover(parent1, parent2, crossover_rate, rng):
    if rng.random() > crossover_rate:
        return parent1.copy()
    mask = rng.integers(0, 2, size=parent1.size, dtype=bool)
    return np.where(mask, parent1, parent2)


def _initialization(func, x0, population, smallstep, bigstep, smallp, bigp, rng):
    pool = [x0.copy()]
    pool += [
        _mutation(x0, smallstep, bigstep, smallp, bigp, rng)
        for _ in range(population - 1)
    ]
    pool = [(x, func(x)) for x in pool]
    pool.sort(key=lambda t: t[1])
    return pool


def _tournament(pool, tournament_size, rng):
    idx = rng.integers(0, len(pool), size=tournament_size)
    best_idx = min(idx, key=lambda i: pool[i][1])
    return pool[best_idx][0]


def local_search(func, x0, local_search_n, local_search_p, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    best_x = x0.copy()
    best_f = func(best_x)

    for _ in range(local_search_n):
        x = best_x.copy()
        for i in range(x.size):
            if rng.random() < local_search_p:
                x[i] += 1 if rng.random() < 0.5 else -1
        f = func(x)
        if f < best_f:
            best_x, best_f = x, f

    return best_x, best_f


def minimize(
        func,
        x0,
        generations=1000,
        population=100,
        elitism=2,
        tournament=3,
        crossover_rate=0.8,
        immigrants=10,
        smallstep=2,
        bigstep=10,
        smallp=None,
        bigp=None,
        local_search_n=100,
        local_search_p=0.1,
        random_state=1,
        verbose=False):
    x0 = np.asarray(x0, dtype=int)

    if elitism + immigrants > population:
        raise ValueError("elitism + immigrants must be <= population")

    if smallp is None:
        smallp = min(0.2, 2 / x0.size)
    if bigp is None:
        bigp = min(0.05, 0.2 / x0.size)

    rng = np.random.default_rng(seed=random_state)

    pool = _initialization(
        func, x0, population, smallstep, bigstep, smallp, bigp, rng
    )

    for gen in range(1, generations + 1):
        elites = [
            local_search(func, pool[i][0], local_search_n, local_search_p, rng)
            for i in range(elitism)
        ]

        crossovers = []
        for _ in range(population - elitism - immigrants):
            parent1 = _tournament(pool, tournament, rng)
            parent2 = _tournament(pool, tournament, rng)
            child = _crossover(parent1, parent2, crossover_rate, rng)
            child = _mutation(child, smallstep, bigstep, smallp, bigp, rng)
            crossovers.append((child, func(child)))

        immigrations = [
            _mutation(x0, smallstep, bigstep, smallp, bigp, rng)
            for _ in range(immigrants)
        ]
        immigrations = [(x, func(x)) for x in immigrations]

        pool = elites + crossovers + immigrations
        pool.sort(key=lambda t: t[1])
        pool = pool[:population]

        if verbose:
            print(f"gen {gen}: {pool[0][1]:f}    ", end="\r")

    if verbose:
        print()

    return pool[0][0], pool[0][1]


if __name__ == "__main__":
    xp = np.arange(100)

    def func(x):
        return np.sum(0.1*(x - xp)**2 - np.cos(x - xp))

    x0 = np.zeros_like(xp)
    xm, fm = minimize(func, x0, verbose=True)
    print("best x:", xm)
    print("best f:", fm)