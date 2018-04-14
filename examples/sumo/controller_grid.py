"""
Example of a multi-lane network with human-driven vehicles.
"""
from flow.core.params import SumoParams, EnvParams, NetParams, InitialConfig, \
    InFlows
from flow.core.vehicles import Vehicles
from flow.core.traffic_lights import TrafficLights

from flow.scenarios.bridge_toll.gen import BBTollGenerator
from flow.scenarios.bridge_toll.scenario import BBTollScenario
from flow.controllers.lane_change_controllers import *
from flow.controllers.velocity_controllers import HandTunedVelocityController, FeedbackController
from flow.controllers.car_following_models import SumoCarFollowingController
from flow.controllers.routing_controllers import ContinuousRouter
from flow.core.params import SumoLaneChangeParams
from flow.envs.bottleneck_env import DesiredVelocityEnv
from flow.core.experiment import SumoExperiment

import numpy as np
import ray

def bottleneck(Kp=10, d=0.003, horizon=500, sumo_binary=None):

    SCALING = 1
    NUM_LANES = 4*SCALING  # number of lanes in the widest highway
    DISABLE_TB = True
    DISABLE_RAMP_METER = True
    AV_FRAC = .000001

    if sumo_binary is None:
        sumo_binary = "sumo-gui"
    sumo_params = SumoParams(sim_step = 0.5, sumo_binary=sumo_binary, overtake_right=False)

    vehicles = Vehicles()

    vehicles.add(veh_id="human",
                 speed_mode=31,
                 lane_change_controller=(SumoLaneChangeController, {}),
                 acceleration_controller=(SumoCarFollowingController, {}),
                 # routing_controller=(ContinuousRouter, {}),
                 lane_change_mode=1621,
                 sumo_lc_params=SumoLaneChangeParams(lcKeepRight=0),
                 num_vehicles=5)

    vehicles.add(veh_id="followerstopper",
                 speed_mode="custom_model",
                 lane_change_controller=(SumoLaneChangeController, {}),
                 # acceleration_controller=(HandTunedVelocityController, {"v_regions":[23, 5, 1, 60, 60, 60, 60, 60, 60]}),
                 acceleration_controller=(FeedbackController, \
                                          {"Kp":Kp, "desired_bottleneck_density":d, "danger_edges":["3", "4", "5"]}),
                 routing_controller=(ContinuousRouter, {}),
                 lane_change_mode=1621,
                 sumo_lc_params=SumoLaneChangeParams(lcKeepRight=0),
                 num_vehicles=5)

    num_segments = [("1", 1, False), ("2", 3, True), ("3", 3, True),
                    ("4", 1, True), ("5", 1, False)]

    additional_env_params = {"target_velocity": 40, "num_steps": horizon,
                             "disable_tb": True, "disable_ramp_metering": True,
                             "segments": num_segments}
    env_params = EnvParams(additional_params=additional_env_params,
                           lane_change_duration=1)

    # flow rate

    # MAX OF 3600 vehicles per lane per hour i.e. flow_rate <= 3600 *
    flow_rate = 2000 * SCALING
    # percentage of flow coming out of each lane
    # flow_dist = np.random.dirichlet(np.ones(NUM_LANES), size=1)[0]
    flow_dist = np.ones(NUM_LANES)/NUM_LANES

    inflow = InFlows()
    inflow.add(veh_type="human", edge="1", vehs_per_hour=flow_rate*(1-AV_FRAC),#vehsPerHour=veh_per_hour *0.8,
               departLane="random", departSpeed=10)
    inflow.add(veh_type="followerstopper", edge="1", vehs_per_hour=flow_rate*AV_FRAC,#vehsPerHour=veh_per_hour * 0.2,
               departLane="random", departSpeed=10)

    traffic_lights = TrafficLights()
    if not DISABLE_TB:
        traffic_lights.add(node_id="2")
    if not DISABLE_RAMP_METER:
        traffic_lights.add(node_id="3")

    additional_net_params = {"scaling": SCALING}
    net_params = NetParams(in_flows=inflow,
                           no_internal_links=False, additional_params=additional_net_params)

    initial_config = InitialConfig(spacing="random", min_gap=5,
                                   lanes_distribution=float("inf"),
                                   edges_distribution=["2", "3", "4", "5"])

    scenario = BBTollScenario(name="bay_bridge_toll",
                              generator_class=BBTollGenerator,
                              vehicles=vehicles,
                              net_params=net_params,
                              initial_config=initial_config,
                              traffic_lights=traffic_lights)

    env = DesiredVelocityEnv(env_params, sumo_params, scenario)

    return SumoExperiment(env, scenario)

@ray.remote
def run_bottleneck(Kp, ds, num_trials, num_steps):

    rewards = []
    for d in ds:
        exp = bottleneck(Kp, d, num_steps, sumo_binary="sumo")
        exp.run(num_trials, num_steps)
        rewards.append(np.mean(exp.rollout_total_rewards))
    return rewards

if __name__ == "__main__":

    # Kps = np.arange(10, 110, 10)
    Kps = np.arange(50, 160, 25)
    ds = np.arange(0.001, 0.005, 0.0005)

    # Kps = [10, 20]
    # ds = [0.002, 0.003, 0.004]

    rets = np.zeros((len(Kps), len(ds)))

    ray.init()
    bottleneck_outputs = [run_bottleneck.remote(Kp, ds, 5, 500) for Kp in Kps]
    for i, output in enumerate(ray.get(bottleneck_outputs)):  # len(Kps) iterations
        rets[i,:] = output

    print('Kp values:', Kps)
    print('desired density values:', ds)
    print('Rewards:', rets)
    indices = np.unravel_index(np.argmax(rets), rets.shape)
    print('best Kp:', Kps[indices[0]], 'best d:', ds[indices[1]])


# best Kp: 50 . best d: 0.0025