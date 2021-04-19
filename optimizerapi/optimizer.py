from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.plots import plot_objective, plot_convergence
from ProcessOptimizer.utils import cook_estimator
from ProcessOptimizer.learning.gaussian_process.kernels import Matern
from numbers import Number
import numpy
numpy.random.seed(42)

def post_hyperparams(hyperparams: str) -> str:
    return 'Hello {name}'.format(name=hyperparams)

def run(params: str = None, Xi: [float] = [0.01], yi: [Number] = [1], kappa: float = 1.96) -> str:
    # TODO generate space, i.e., an array of either options for categories or tuples of (min, max) for value types
    space = [(0,1)]
    hyperparams = {
        'base_estimator': 'GP',
        'acq_func': 'gp_hedge',
        'n_initial_points': 3,
        'acq_func_kwargs': {'kappa': kappa, 'Xi': Xi, 'yi': yi}
    }
    optimizer = Optimizer(space, **hyperparams)
    # TODO call optimizer with proper Xi and Yi values
    result = optimizer.tell([Xi], yi)
    if params:
        return 'Run with {params} = {result}'.format(params=params, result=result)
    else:
        return 'Run with no parameters = {result}'.format(result=result)
        