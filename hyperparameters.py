"""Commonly used hyperparameters and utility functions"""

import math
import numpy as np
import generator as g
from features import features_by_name

# reproducibility
STATE = np.random.RandomState(42)

GENERATOR_DEFAULTS = {
    "interm_nodes_dist": lambda r: round(g.truncnorm(r, mean=5, sd=3, low=0)),
    "pos_dist": lambda r: r.uniform(low=(0, 0), high=(25, 25)),
    "capacity_dist": lambda r: g.truncnorm(r, mean=35, sd=10, low=0),
    "power_dist": lambda r: r.normal(30, 2),
    "interm_blocks_dist": lambda r: round(g.truncnorm(r, mean=3, sd=2, low=0)),
    "pairwise_connection": lambda r: r.rand() < 0.1,
    "block_weight_dist": lambda r: g.truncnorm(r, mean=10, low=0, sd=7),
    # mean equivalent to a linear SINRth of 20, which is what marvelo uses
    "requirement_dist": lambda r: g.truncnorm(r, mean=4, low=0, sd=1),
    "num_sources_dist": lambda r: round(g.truncnorm(r, mean=2, sd=1, low=1)),
    "connection_choice": lambda r, a: r.choice(a),
}

MARVELO_DEFAULTS = {
    # 4-9 nodes total, including source+sink
    "interm_nodes_dist": lambda r: r.randint(2, 7 + 1),
    "pos_dist": lambda r: r.uniform(low=(0, 0), high=(25, 25)),
    "capacity_dist": lambda r: r.randint(21, 21 * (2 + r.rand())),
    # always 1 watt
    "power_dist": lambda r: 30,
    # 3-6 blocks total, including source+sink
    "interm_blocks_dist": lambda r: r.randint(1, 4 + 1),
    "pairwise_connection": lambda r: False,
    "block_weight_dist": lambda r: r.rand() * 20,
    # equivalent to a constant linear SINRth of 20
    "requirement_dist": lambda r: math.log(20 + 1, 2),
    "num_sources_dist": lambda r: 1,
    "connection_choice": lambda r, a: r.choice(a),
}

DEFAULT_FEATURES = [
    features_by_name()[name]
    for name in [
        "node_relay",
        "edge_additional_timeslot",
        "edge_datarate_fraction",
        "edge_capacity",
        "node_options_lost",
    ]
]

DEFAULT = {
    "learnsteps": 30000,
    "prioritized_replay_alpha": 0.6,
    "prioritized_replay_beta0": 0.4,
    "prioritized_replay_beta_iters": None,  # all steps
    "prioritized_replay_eps": 1e-6,
    "learning_starts": 1000,
    "buffer_size": 50000,
    "lr": 5e-4,
    "grad_norm_clipping": 5,
    "gamma": 0.9,
    "target_network_update_freq": 500,
    "train_freq": 4,
    "batch_size": 32,
    "early_exit_factor": np.infty,
    "num_processing_steps": 40,
    "latent_size": 16,
    "num_layers": 5,
    "seedgen": lambda: STATE.randint(0, 2 ** 32),
    "experiment_name": "default",
    "prioritized": True,
    "features": DEFAULT_FEATURES,
    "generator_args": GENERATOR_DEFAULTS,
    "restart_reward": 0,
    "success_reward": 0,
    "additional_timeslot_reward": -1,
    "exploration_fraction": 0.2,
    "rl_seed": STATE.randint(0, 2 ** 32),
}
