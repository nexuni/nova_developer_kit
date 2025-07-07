# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import shutil
from typing import List

import isaac_ros_launch_utils as lu
import yaml

DEFAULT_CONTAINER = 'nova_recorder'
RECORDING_CONFIG = '/tmp/recording_config.yaml'


def nova_amr_launch_description(args: lu.ArgumentContainer) -> List[lu.Action]:
    actions = []

    config_path = Path(args.config)
    if not config_path.is_file():
        default_dir = lu.get_path('isaac_ros_nova', 'config')
        default_path = default_dir.joinpath(config_path)
        # append .yaml if there is no suffix
        if not default_path.suffix:
            default_path = default_path.with_suffix('.yaml')
        if not default_path.is_file():
            ls_configs = [entry.stem for entry in default_dir.iterdir() if entry.is_file()]
            ls_configs_str = ' '.join(ls_configs)
            raise ValueError(
                f'Tried to find YAML {args.config} but failed. Use a valid file '
                f'path or one of the available YAMLs: {ls_configs_str}'
            )
        config_path = default_path

    shutil.copyfile(config_path, RECORDING_CONFIG)

    # Launch sensors with specified camera configuration
    actions.append(
        lu.include(
            package='nova_developer_kit_bringup',
            path='launch/sensors.launch.py',
            launch_arguments={
                'enabled_stereo_cameras': args.enabled_stereo_cameras,
                'enabled_fisheye_cameras': args.enabled_fisheye_cameras,
                'mode': args.mode,
                'type_negotiation_duration_s': args.type_negotiation_duration_s,
            },
        )
    )

    sensors = {}
    topics = args.topics + [
        '/rosout',
        '/diagnostics',
        '/diagnostics_agg',
        '/tf',
        '/tf_static',
        '/robot_description',
        '/amr_motion',
        '/wdriver/low_level/output',
        '/back_2d_lidar/scan'
    ]
    
    with open(RECORDING_CONFIG, 'r') as file:
        config = yaml.safe_load(file)
        if config and 'sensors' in config and config['sensors']:
            for sensor in config['sensors']:
                if sensor.endswith('camera'):
                    sensors[sensor] = {
                        'width': 1920,
                        'height': 1200,
                    }
                    if '/correlated_timestamp' not in topics:
                        topics.append('/correlated_timestamp')
                else:
                    sensors[sensor] = {}

    if args.target_container == DEFAULT_CONTAINER:
        actions.append(
            lu.component_container(
                container_name=args.target_container,
            )
        )

    files = [
        RECORDING_CONFIG,
        '/etc/nova/systeminfo.yaml',
        '/etc/nova/metadata.json',
        '/etc/nova/calibration/isaac_nominals.urdf',
        '/etc/nova/calibration/isaac_calibration.urdf',
    ]

    # Add data recorder for logging topics
    actions.append(
        lu.include(
            package='isaac_ros_data_recorder',
            path='launch/data_recorder.launch.py',
            launch_arguments={
                'target_container': args.target_container,
                'sensors': sensors,
                'topics': topics,
                'files': files,
                'recording_directory': args.recording_directory,
                'enable_services': False,
                'event_recorder': args.event_recorder,
                'encoder_qp': args.encoder_qp,
            }
        )
    )

    return actions


def generate_launch_description():
    args = lu.ArgumentContainer()
    args.add_arg('target_container',
                 description='target container',
                 default=DEFAULT_CONTAINER,
                 cli=True)
    args.add_arg('config',
                 description='sensor configuration file',
                 default='/etc/nova/nxcar.yaml',
                 cli=True)
    args.add_arg('enabled_stereo_cameras',
                 description='enabled stereo cameras',
                 default='front_stereo_camera',
                 cli=True)
    args.add_arg('enabled_fisheye_cameras',
                 description='enabled fisheye cameras',
                 default='front_fisheye_camera',
                 cli=True)
    args.add_arg('mode',
                 description='sensor mode',
                 default='real_world',
                 cli=True)
    args.add_arg('type_negotiation_duration_s',
                 description='type negotiation duration in seconds',
                 default=5,
                 cli=True)
    args.add_arg('topics',
                 description='additional topics to record',
                 default=[],
                 cli=True)
    args.add_arg('recording_directory',
                 description='recording directory',
                 default='/mnt/nova_ssd/recordings',
                 cli=True)
    args.add_arg('s3_bucket',
                 description='S3 bucket',
                 default='',
                 cli=True)
    args.add_arg('headless',
                 description='record data without the UI',
                 default=False,
                 cli=True)
    args.add_arg('event_recorder',
                 description='enable event recording',
                 default=False,
                 cli=True)
    args.add_arg('webserver_port',
                 description='webserver port for the UI',
                 default=8080,
                 cli=True)
    args.add_arg('retry_count',
                 description='Number of retries if the server fails to start',
                 default=100,
                 cli=True)
    args.add_arg('retry_delay',
                 description='Delay in seconds between retries',
                 default=2.0,
                 cli=True)
    args.add_arg('encoder_qp',
                 description='H.264 encoder quality parameter',
                 default=20,
                 cli=True)
    args.add_opaque_function(nova_amr_launch_description)

    return lu.LaunchDescription(args.get_launch_actions()) 