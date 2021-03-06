"""Example of a merge network with human-driven vehicles.

In the absence of autonomous vehicles, the network exhibits properties of
convective instability, with perturbations propagating upstream from the merge
point before exiting the network.
"""

from flow.core.params import SumoParams, EnvParams, \
    NetParams, InitialConfig, InFlows
from flow.core.vehicles import Vehicles
from flow.core.experiment import SumoExperiment
from flow.scenarios.merge.gen import MergeGenerator
from flow.scenarios.merge.scenario import MergeScenario, \
    ADDITIONAL_NET_PARAMS
from flow.controllers import IDMController
from flow.envs.merge import WaveAttenuationMergePOEnv, ADDITIONAL_ENV_PARAMS

# inflow rate at the highway
FLOW_RATE = 2000
# percent of autonomous vehicles
RL_PENETRATION = 0.1


def merge_example(sumo_binary=None):
    sumo_params = SumoParams(sumo_binary="sumo-gui",
                             emission_path="./data/",
                             sim_step=0.2,
                             restart_instance=True)

    if sumo_binary is not None:
        sumo_params.sumo_binary = sumo_binary

    vehicles = Vehicles()
    vehicles.add(veh_id="human",
                 acceleration_controller=(IDMController, {"noise": 0.2}),
                 num_vehicles=5)

    env_params = EnvParams(additional_params=ADDITIONAL_ENV_PARAMS,
                           sims_per_step=5,
                           warmup_steps=0)

    inflow = InFlows()
    inflow.add(veh_type="human", edge="inflow_highway",
               vehs_per_hour=(1-RL_PENETRATION)*FLOW_RATE,
               departLane="free", departSpeed=10)
    inflow.add(veh_type="human", edge="inflow_merge",
               vehs_per_hour=100,
               departLane="free", departSpeed=7.5)

    additional_net_params = ADDITIONAL_NET_PARAMS.copy()
    additional_net_params["merge_lanes"] = 1
    additional_net_params["highway_lanes"] = 1
    additional_net_params["pre_merge_length"] = 500
    net_params = NetParams(in_flows=inflow,
                           no_internal_links=False,
                           additional_params=additional_net_params)

    initial_config = InitialConfig(spacing="uniform",
                                   perturbation=5.0,
                                   lanes_distribution=float("inf"))

    scenario = MergeScenario(name="merge-baseline",
                             generator_class=MergeGenerator,
                             vehicles=vehicles,
                             net_params=net_params,
                             initial_config=initial_config)

    env = WaveAttenuationMergePOEnv(env_params, sumo_params, scenario)

    return SumoExperiment(env, scenario)


if __name__ == "__main__":
    # import the experiment variable
    exp = merge_example()

    # run for a set number of rollouts / time steps
    exp.run(1, 3600, convert_to_csv=False)
