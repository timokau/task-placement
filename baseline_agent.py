"""Simple semi-greedy baseline agent"""
from math import inf
import random
import numpy as np
from gym_environment import WSNEnvironment


def act(graph_tuple):
    """Take a semi-greedy action"""
    min_ts_actions = None
    possible_actions = []
    min_ts = inf
    i = 0
    for (_u, _v, d) in zip(
        graph_tuple.senders, graph_tuple.receivers, graph_tuple.edges
    ):
        possible = d[1] == 1
        if not possible:
            continue
        else:
            timeslot = int(d[2])
            possible_actions.append(i)
            if timeslot == min_ts:
                min_ts_actions.append(i)
            elif timeslot < min_ts:
                min_ts = timeslot
                min_ts_actions = [i]
            i += 1

    # break out of reset loops by acting random every once in a while
    if random.random() < 0.01:
        return random.choice(possible_actions)
    return random.choice(min_ts_actions)


def play_episode(env):
    """Play an entire episode and report the reward"""
    obs = env.reset()
    total_reward = 0
    while True:
        action = act(obs)
        new_obs, rew, done, _ = env.step(action)
        total_reward += rew
        obs = new_obs
        if done:
            print(total_reward)
            return total_reward


def evaluate(env, episodes=100):
    """Evaluate over many episodes"""
    rewards = []
    for _ in range(episodes):
        rewards.append(play_episode(env))
    return np.mean(rewards)


def main():
    """Run the experiment"""
    env = WSNEnvironment()
    print("=====")
    print(evaluate(env, 1000))


if __name__ == "__main__":
    main()
