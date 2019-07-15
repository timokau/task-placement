"""Train a graph_nets DQN agent on the WSN environment"""

import subprocess
import datetime
from functools import partial

import tensorflow as tf

# needs this fork of baselines:
# https://github.com/timokau/baselines/tree/graph_nets-deepq
# see https://github.com/openai/baselines/pull/931
from baselines import logger
from baselines.deepq import learn
from networkx.drawing.nx_pydot import write_dot

from q_network import EncodeProcessDecode
import gym_environment
from generator import Generator, ParallelGenerator
from draw_embedding import succinct_representation
from tf_util import ragged_boolean_mask


def deepq_graph_network(inpt, num_processing_steps, latent_size, num_layers):
    """Takes an input_graph, returns q-values.

    graph_nets based model that takes an input graph and returns a
    (variable length) vector of q-values corresponding to the edges in
    the input graph that represent valid actions (according to the
    boolean edge attribute in second position)"""
    model = EncodeProcessDecode(
        edge_output_size=1,
        global_output_size=0,
        node_output_size=0,
        latent_size=latent_size,
        num_layers=num_layers,
    )
    out = model(inpt, num_processing_steps)[-1]

    q_vals = tf.cast(tf.reshape(out.edges, [-1]), tf.float32)
    ragged_q_vals = tf.RaggedTensor.from_row_lengths(
        q_vals, tf.cast(out.n_edge, tf.int64)
    )

    def edge_is_possible_action(edge):
        possible = edge[gym_environment.POSSIBLE_IDX]
        return tf.math.equal(possible, 1)

    viable_actions_mask = tf.map_fn(
        edge_is_possible_action, inpt.edges, dtype=tf.bool
    )
    ragged_mask = tf.RaggedTensor.from_row_lengths(
        viable_actions_mask, tf.cast(inpt.n_edge, tf.int64)
    )

    result = ragged_boolean_mask(ragged_q_vals, ragged_mask)

    return result.to_tensor(default_value=tf.float32.min)


def save_episode_result_callback(lcl, _glb):
    """Saves the result of a "solved" episode as a dot file"""
    if not lcl["done"]:
        return
    episode = len(lcl["episode_rewards"])
    total_reward = round(lcl["env"].env.used_timeslots)
    write_dot(
        succinct_representation(lcl["env"].env),
        f"{logger.get_dir()}/result-{episode}-{-total_reward}.dot",
    )


def _git_describe():
    try:
        return (
            subprocess.check_output(["git", "describe", "--always"])
            .strip()
            .decode()
        )
    except subprocess.CalledProcessError:
        return "nogit"


def run_training(
    # pylint: disable=too-many-arguments
    learnsteps,
    train_freq,
    batch_size,
    exploration_fraction,
    early_exit_factor,
    num_processing_steps,
    latent_size,
    num_layers,
    seedgen,
    rl_seed,
    experiment_name,
    prioritized,
    node_feat_whitelist,
    node_feat_blacklist,
    edge_feat_whitelist,
    edge_feat_blacklist,
    generator_args,
):
    """Trains the agent with the given hyperparameters"""
    assert frozenset(node_feat_blacklist).issubset(node_feat_whitelist)
    assert frozenset(edge_feat_blacklist).issubset(edge_feat_whitelist)

    node_feat = frozenset(node_feat_whitelist).difference(node_feat_blacklist)
    edge_feat = frozenset(edge_feat_whitelist).difference(edge_feat_blacklist)

    parallel_gen = ParallelGenerator(Generator(**generator_args), seedgen)
    env = gym_environment.WSNEnvironment(
        node_features=node_feat,
        edge_features=edge_feat,
        early_exit_factor=early_exit_factor,
        seedgen=seedgen,
        problem_generator=parallel_gen.new_instance,
    )

    git_label = _git_describe()
    time_label = datetime.datetime.now().isoformat()
    logger.configure(
        dir=f"logs/{time_label}-{git_label}-{experiment_name}",
        format_strs=["stdout", "csv", "tensorboard"],
    )

    learn(
        env,
        partial(
            deepq_graph_network,
            num_processing_steps=num_processing_steps,
            latent_size=latent_size,
            num_layers=num_layers,
        ),
        make_obs_ph=lambda name: env.observation_space.to_placeholders(),
        as_is=True,
        dueling=False,
        prioritized=prioritized,
        print_freq=1,
        train_freq=train_freq,
        batch_size=batch_size,
        exploration_fraction=exploration_fraction,
        checkpoint_freq=1000,
        seed=rl_seed,
        total_timesteps=learnsteps * train_freq,
        checkpoint_path=logger.get_dir(),
        after_step_callback=save_episode_result_callback,
    )


if __name__ == "__main__":
    from hyperparameters import DEFAULT

    run_training(**DEFAULT)
