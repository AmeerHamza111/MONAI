# Copyright 2020 MONAI Consortium
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import logging
import numpy as np
import torch
from ignite.engine import create_supervised_evaluator, _prepare_batch
from torch.utils.data import DataLoader

# assumes the framework is found here, change as necessary
sys.path.append("..")
import monai
import monai.transforms.compose as transforms
from monai.data.nifti_reader import NiftiDataset
from monai.transforms import (AddChannel, Rescale, Resize)
from monai.handlers.stats_handler import StatsHandler
from monai.handlers.classification_saver import ClassificationSaver
from monai.handlers.checkpoint_loader import CheckpointLoader
from ignite.metrics import Accuracy

monai.config.print_config()

# demo dataset, user can easily change to own dataset
images = [
    "/workspace/data/medical/ixi/IXI-T1/IXI607-Guys-1097-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI175-HH-1570-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI385-HH-2078-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI344-Guys-0905-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI409-Guys-0960-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI584-Guys-1129-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI253-HH-1694-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI092-HH-1436-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI574-IOP-1156-T1.nii.gz",
    "/workspace/data/medical/ixi/IXI-T1/IXI585-Guys-1130-T1.nii.gz"
]
labels = np.array([
    0, 0, 1, 0, 1, 0, 1, 0, 1, 0
])

# Define transforms for image
val_transforms = transforms.Compose([
    Rescale(),
    AddChannel(),
    Resize((96, 96, 96))
])
# Define nifti dataset
val_ds = NiftiDataset(image_files=images, labels=labels, transform=val_transforms, image_only=False)
# Create DenseNet121
net = monai.networks.nets.densenet3d.densenet121(
    in_channels=1,
    out_channels=2,
)

device = torch.device("cuda:0")
metric_name = 'Accuracy'

# add evaluation metric to the evaluator engine
val_metrics = {metric_name: Accuracy()}


def prepare_batch(batch, device=None, non_blocking=False):
    return _prepare_batch((batch[0], batch[1]), device, non_blocking)


evaluator = create_supervised_evaluator(net, val_metrics, device, True, prepare_batch=prepare_batch)

# Add stats event handler to print validation stats via evaluator
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
val_stats_handler = StatsHandler()
val_stats_handler.attach(evaluator)

# for the arrary data format, assume the 3rd item of batch data is the meta_data
prediction_saver = ClassificationSaver(output_dir='tempdir', batch_transform=lambda batch: batch[2],
                                       output_transform=lambda output: output[0].argmax(1))
prediction_saver.attach(evaluator)

# the model was trained by "densenet_classification_3d_array" exmple
CheckpointLoader(load_path='./runs/net_checkpoint_40.pth', load_dict={'net': net}).attach(evaluator)

# create a validation data loader
val_loader = DataLoader(val_ds, batch_size=2, num_workers=4, pin_memory=torch.cuda.is_available())

state = evaluator.run(val_loader)
prediction_saver.finalize()
