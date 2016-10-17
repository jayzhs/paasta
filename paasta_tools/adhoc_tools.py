# Copyright 2015-2016 Yelp Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging

import choice
import service_configuration_lib

from paasta_tools.utils import deep_merge_dictionaries
from paasta_tools.utils import DEFAULT_SOA_DIR
from paasta_tools.utils import get_paasta_branch
from paasta_tools.utils import InstanceConfig
from paasta_tools.utils import load_v2_deployments_json
from paasta_tools.utils import NoConfigurationForServiceError


log = logging.getLogger(__name__)


def load_adhoc_job_config(service, instance, cluster, load_deployments=True, soa_dir=DEFAULT_SOA_DIR):
    general_config = service_configuration_lib.read_service_configuration(
        service,
        soa_dir=soa_dir
    )
    adhoc_conf_file = "adhoc-%s" % cluster
    log.info("Reading adhoc configuration file: %s.yaml", adhoc_conf_file)
    instance_configs = service_configuration_lib.read_extra_service_information(
        service,
        adhoc_conf_file,
        soa_dir=soa_dir
    )

    if instance not in instance_configs:
        raise NoConfigurationForServiceError(
            "%s not found in config file %s/%s/%s.yaml." % (instance, soa_dir, service, adhoc_conf_file)
        )

    general_config = deep_merge_dictionaries(overrides=instance_configs[instance], defaults=general_config)

    branch_dict = {}
    if load_deployments:
        deployments_json = load_v2_deployments_json(service, soa_dir=soa_dir)
        branch = general_config.get('branch', get_paasta_branch(cluster, instance))
        deploy_group = general_config.get('deploy_group', branch)
        branch_dict = deployments_json.get_branch_dict_v2(service, branch, deploy_group)

    return AdhocJobConfig(
        service=service,
        cluster=cluster,
        instance=instance,
        config_dict=general_config,
        branch_dict=branch_dict,
    )


class AdhocJobConfig(InstanceConfig):

    def __init__(self, service, instance, cluster, config_dict, branch_dict):
        super(AdhocJobConfig, self).__init__(
            cluster=cluster,
            instance=instance,
            service=service,
            config_dict=config_dict,
            branch_dict=branch_dict,
        )


def get_default_interactive_config(service, cluster, soa_dir):
    default_job_config = {
        'cpus': 1,
        'mem': 1024,
        'disk': 1024
    }

    try:
        job_config = load_adhoc_job_config(service=service, instance='interactive', cluster=cluster)
    except NoConfigurationForServiceError:
        job_config = AdhocJobConfig(
            service=service,
            instance='interactive',
            cluster=cluster,
            config_dict={},
            branch_dict={},
        )
        deployments_json = load_v2_deployments_json(service, soa_dir=soa_dir)
        deploy_groups = [(deploy_group, deploy_group) for deploy_group in deployments_json['deployments'].keys()]
        deploy_group = choice.Menu(deploy_groups).ask()

        job_config.config_dict['deploy_group'] = deploy_group
        job_config.branch_dict['docker_image'] = deployments_json.get_docker_image_for_deploy_group(deploy_group)

    for key, value in default_job_config.items():
        job_config.config_dict.setdefault(key, value)

    return job_config